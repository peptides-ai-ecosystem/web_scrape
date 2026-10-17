"""Selector-free competitor discovery: a store URL in, priced variants out (AAD-1).

Given only a store's home, shop or product URL, find its products and read
one price per variant without any CSS selector. Sources are tried in order of
how much they can be trusted and how few requests they take:

1. **WooCommerce Store API** — ``/wp-json/wc/store/v1/products``, paginated
   (100 per page), variations fetched in batches with ``type=variation&include=``.
2. **Shopify** — ``/products.json``, paginated (250 per page).
3. **Sitemaps** — robots.txt ``Sitemap:`` lines, ``/sitemap_index.xml``,
   ``/sitemap.xml``, ``/wp-sitemap.xml``; product pages read for JSON-LD /
   microdata / OpenGraph.
4. **Rendering** — a page whose static HTML carries no structured price is
   loaded once more in the browser (scripts on) and read again.

A product URL is read on its own (the Store API by slug, Shopify's
``<handle>.json``, or the page itself) instead of crawling the whole store.

Everything goes through :class:`~app.infrastructure.polite_http.PoliteHttpClient`
(robots.txt, SSRF guard, per-host pacing, request budget, no retries), so this
module holds only the discovery logic and is tested on recorded responses.
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from typing import Any
from urllib.parse import quote

from app.core.vendor_models import ProductReading, ScrapeStatus
from app.extractors.store_api import (
    WOO_STORE_API_PATH,
    looks_like_product_url,
    origin_of,
    parse_sitemap,
    rank_child_sitemaps,
    same_host,
    shopify_product_handle,
    shopify_readings,
    woo_is_variable,
    woo_product_slug,
    woo_simple_reading,
    woo_variation_readings,
)
from app.extractors.structured_data import parse_product_page
from app.infrastructure.polite_http import (
    ACCEPT_HTML,
    ACCEPT_JSON,
    ACCEPT_XML,
    HttpResult,
    PoliteHttpClient,
)

logger = logging.getLogger(__name__)

WOO_PAGE_SIZE = 100
SHOPIFY_PAGE_SIZE = 250
#: Child sitemaps read from one index, at most.
MAX_CHILD_SITEMAPS = 4
_SITEMAP_PATHS = ("/sitemap_index.xml", "/sitemap.xml", "/wp-sitemap.xml", "/product-sitemap.xml")
#: A size/amount in a product name: "10mg", "5 mg", "500mcg", "10ml", "60 caps".
_SIZE_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|ug|g|ml|iu|units?|caps?|capsules|tabs?|tablets|vials?|kits?|pcs)\b",
    re.IGNORECASE,
)
#: Confidence for a reading with no size anywhere: the platform import matches
#: competitor prices by size, so a size-less price is held for review instead
#: of being accepted and then refused by the import (e.g. a JSON-LD Offer on a
#: multi-size page that only publishes the default size's price).
NO_SIZE_CONFIDENCE = 0.55


def has_size(reading: ProductReading) -> bool:
    return bool(reading.variant_label) or bool(_SIZE_RE.search(reading.product_name or ""))


def _hold_sizeless(result: DiscoveryResult) -> None:
    held = 0
    for index, reading in enumerate(result.readings):
        if reading.price is not None and not has_size(reading) and reading.confidence > NO_SIZE_CONFIDENCE:
            result.readings[index] = replace(reading, confidence=NO_SIZE_CONFIDENCE)
            held += 1
    if held:
        result.notes.append(
            f"{held} reading(s) name no size; held for review (the import matches prices by size)"
        )


@dataclass
class DiscoveryFailure:
    url: str
    status: ScrapeStatus
    detail: str


@dataclass
class DiscoveryResult:
    """What one discovery found, and how."""

    seed_url: str
    method: str | None = None
    readings: list[ProductReading] = field(default_factory=list)
    products_seen: int = 0
    requests_made: int = 0
    notes: list[str] = field(default_factory=list)
    failures: list[DiscoveryFailure] = field(default_factory=list)

    def to_dict(self, include_readings: bool = True) -> dict[str, Any]:
        out: dict[str, Any] = {
            "seed_url": self.seed_url,
            "method": self.method,
            "products_seen": self.products_seen,
            "variants_found": len(self.readings),
            "priced": sum(1 for r in self.readings if r.price is not None),
            "requests_made": self.requests_made,
            "notes": list(self.notes),
            "failures": [
                {"url": f.url, "status": f.status.value, "detail": f.detail} for f in self.failures
            ],
        }
        if include_readings:
            out["readings"] = [
                {
                    "url": r.url,
                    "page_url": r.page_url,
                    "product_name": r.product_name,
                    "variant_label": r.variant_label,
                    "sku": r.sku,
                    "price": str(r.price) if r.price is not None else None,
                    "currency": r.currency,
                    "stock_status": r.stock_status.value if r.stock_status else None,
                    "method": r.method,
                    "confidence": round(r.confidence, 4),
                }
                for r in self.readings
            ]
        return out


def _status_of(result: HttpResult) -> ScrapeStatus:
    if result.robots_disallowed:
        return ScrapeStatus.ROBOTS_DISALLOWED
    if result.refused or result.throttled:
        return ScrapeStatus.BLOCKED
    if result.budget_exhausted:
        return ScrapeStatus.SKIPPED
    return ScrapeStatus.ERROR


def _why(result: HttpResult) -> str:
    return result.error or f"HTTP {result.status}"


class UrlOnlyDiscovery:
    """Discovers and reads one store. Build one per target (one budget each)."""

    def __init__(
        self,
        client: PoliteHttpClient,
        *,
        renderer: Any = None,
        max_products: int = 200,
        currency: str | None = None,
    ):
        self._client = client
        #: Optional browser fetcher with ``fetch_rendered(url)`` (scripts on).
        self._renderer = renderer
        self._max_products = max(1, int(max_products))
        self._currency = currency

    # -- public ------------------------------------------------------------

    def discover(self, seed_url: str) -> DiscoveryResult:
        """A home/shop URL crawls the catalogue; a product URL reads that product."""
        if looks_like_product_url(seed_url):
            return self.read_product(seed_url)
        result = DiscoveryResult(seed_url=seed_url)
        origin = origin_of(seed_url)
        for strategy in (self._woo_catalog, self._shopify_catalog, self._sitemaps):
            if strategy(origin, result):
                break
            if self._client.budget_left <= 0:
                result.notes.append("request budget spent before a catalogue source was found")
                break
        else:
            # No catalogue source: read the seed page itself as a product page.
            self._read_pages([seed_url], result)
            if result.readings:
                result.method = result.method or "product_page"
            elif not result.failures:
                result.notes.append(
                    "no Store API, products.json, sitemap or structured price found; "
                    "add CSS selectors to this target"
                )
        _hold_sizeless(result)
        result.requests_made = self._client.requests_made
        return result

    def read_product(self, product_url: str) -> DiscoveryResult:
        result = DiscoveryResult(seed_url=product_url)
        origin = origin_of(product_url)
        slug = woo_product_slug(product_url)
        handle = shopify_product_handle(product_url)
        done = False
        if slug:
            done = self._woo_by_slug(origin, slug, result)
        if not done and handle:
            done = self._shopify_by_handle(origin, handle, result)
        if not done:
            self._read_pages([product_url], result)
            if result.readings:
                result.method = result.method or "product_page"
        _hold_sizeless(result)
        result.requests_made = self._client.requests_made
        return result

    # -- WooCommerce -------------------------------------------------------

    def _woo_catalog(self, origin: str, result: DiscoveryResult) -> bool:
        per_page = min(WOO_PAGE_SIZE, self._max_products)
        products: list[dict[str, Any]] = []
        page = 1
        while len(products) < self._max_products:
            url = f"{origin}{WOO_STORE_API_PATH}?per_page={per_page}&page={page}"
            res = self._client.get(url, ACCEPT_JSON)
            body = res.json()
            if page == 1:
                if res.robots_disallowed:
                    result.notes.append("WooCommerce Store API disallowed by robots.txt — not used")
                    return False
                if not isinstance(body, list) or not body:
                    return False
            elif not isinstance(body, list):
                if not res.ok:
                    result.notes.append(f"Store API page {page}: {_why(res)}")
                break
            products.extend(p for p in body if isinstance(p, dict))
            total_pages = _int(res.header("x-wp-totalpages"))
            if len(body) < per_page or (total_pages is not None and page >= total_pages):
                break
            page += 1
        products = products[: self._max_products]
        result.method = "woo_store_api"
        result.products_seen = len(products)
        self._woo_expand(origin, products, result)
        return True

    def _woo_by_slug(self, origin: str, slug: str, result: DiscoveryResult) -> bool:
        res = self._client.get(f"{origin}{WOO_STORE_API_PATH}?slug={quote(slug)}", ACCEPT_JSON)
        body = res.json()
        if not isinstance(body, list) or not body or not isinstance(body[0], dict):
            return False
        result.method = "woo_store_api"
        result.products_seen = 1
        self._woo_expand(origin, [body[0]], result)
        return True

    def _woo_expand(self, origin: str, products: list[dict[str, Any]], result: DiscoveryResult) -> None:
        """Simple products as they are; variable ones expanded to their sizes."""
        variable = [p for p in products if woo_is_variable(p)]
        variations_by_parent = self._woo_variations(origin, variable, result) if variable else {}
        for product in products:
            if woo_is_variable(product):
                items = variations_by_parent.get(int(product.get("id") or 0)) or []
                readings = woo_variation_readings(product, items)
                if readings:
                    result.readings.extend(readings)
                    continue
                result.notes.append(
                    f"{product.get('name')!s}: sizes not readable, kept the 'from' price for review"
                )
            reading = woo_simple_reading(product)
            if reading is not None:
                result.readings.append(reading)

    def _woo_variations(
        self, origin: str, parents: list[dict[str, Any]], result: DiscoveryResult
    ) -> dict[int, list[dict[str, Any]]]:
        wanted: dict[int, int] = {}
        for parent in parents:
            for variation in parent.get("variations") or []:
                vid = _int((variation or {}).get("id")) if isinstance(variation, dict) else None
                pid = _int(parent.get("id"))
                if vid is not None and pid is not None:
                    wanted[vid] = pid
        out: dict[int, list[dict[str, Any]]] = {}
        ids = list(wanted)
        for start in range(0, len(ids), WOO_PAGE_SIZE):
            chunk = ids[start:start + WOO_PAGE_SIZE]
            url = (
                f"{origin}{WOO_STORE_API_PATH}?type=variation&per_page={WOO_PAGE_SIZE}"
                f"&include={','.join(str(i) for i in chunk)}"
            )
            res = self._client.get(url, ACCEPT_JSON)
            body = res.json()
            if not isinstance(body, list):
                result.notes.append(f"Store API variations: {_why(res)}")
                break
            for item in body:
                if not isinstance(item, dict):
                    continue
                vid = _int(item.get("id"))
                parent_id = wanted.get(vid) if vid is not None else None
                if parent_id is None:
                    parent_id = _int(item.get("parent"))
                if parent_id is not None:
                    out.setdefault(parent_id, []).append(item)
        return out

    # -- Shopify -----------------------------------------------------------

    def _shopify_catalog(self, origin: str, result: DiscoveryResult) -> bool:
        per_page = min(SHOPIFY_PAGE_SIZE, self._max_products)
        products: list[dict[str, Any]] = []
        page = 1
        while len(products) < self._max_products:
            res = self._client.get(f"{origin}/products.json?limit={per_page}&page={page}", ACCEPT_JSON)
            body = res.json()
            items = body.get("products") if isinstance(body, dict) else None
            if page == 1:
                if res.robots_disallowed:
                    result.notes.append("Shopify products.json disallowed by robots.txt — not used")
                    return False
                if not isinstance(items, list) or not items:
                    return False
            elif not isinstance(items, list):
                if not res.ok:
                    result.notes.append(f"products.json page {page}: {_why(res)}")
                break
            products.extend(p for p in items if isinstance(p, dict))
            if len(items) < per_page:
                break
            page += 1
        products = products[: self._max_products]
        result.method = "shopify_json"
        result.products_seen = len(products)
        for product in products:
            result.readings.extend(shopify_readings(product, origin, self._currency))
        return True

    def _shopify_by_handle(self, origin: str, handle: str, result: DiscoveryResult) -> bool:
        res = self._client.get(f"{origin}/products/{quote(handle)}.json", ACCEPT_JSON)
        body = res.json()
        product = body.get("product") if isinstance(body, dict) else None
        if not isinstance(product, dict):
            return False
        result.method = "shopify_json"
        result.products_seen = 1
        result.readings.extend(shopify_readings(product, origin, self._currency))
        return True

    # -- Sitemaps ----------------------------------------------------------

    def _sitemaps(self, origin: str, result: DiscoveryResult) -> bool:
        product_urls = self._sitemap_product_urls(origin, result)
        if not product_urls:
            return False
        result.method = "sitemap"
        product_urls = product_urls[: self._max_products]
        result.products_seen = len(product_urls)
        self._read_pages(product_urls, result)
        return True

    def _sitemap_product_urls(self, origin: str, result: DiscoveryResult) -> list[str]:
        robots_maps = []
        try:
            robots_maps = [u for u in self._robots_sitemaps(origin) if same_host(u, origin)]
        except Exception:  # noqa: BLE001
            robots_maps = []
        candidates = robots_maps + [f"{origin}{p}" for p in _SITEMAP_PATHS if f"{origin}{p}" not in robots_maps]
        for candidate in candidates:
            kind, locs = self._fetch_sitemap(candidate)
            if kind is None:
                continue
            if kind == "urlset":
                urls = self._product_locs(locs, origin)
            else:
                urls = []
                for child in rank_child_sitemaps([u for u in locs if same_host(u, origin)])[:MAX_CHILD_SITEMAPS]:
                    child_kind, child_locs = self._fetch_sitemap(child)
                    if child_kind == "urlset":
                        urls.extend(u for u in self._product_locs(child_locs, origin) if u not in urls)
                    if len(urls) >= self._max_products:
                        break
            if urls:
                result.notes.append(f"product URLs from sitemap {candidate}")
                return urls
        return []

    def _robots_sitemaps(self, origin: str) -> list[str]:
        return list(self._client.robots_sitemaps(origin + "/"))

    def _fetch_sitemap(self, url: str) -> tuple[str | None, list[str]]:
        res = self._client.get(url, ACCEPT_XML)
        if not res.ok:
            return None, []
        return parse_sitemap(res.text)

    @staticmethod
    def _product_locs(locs: list[str], origin: str) -> list[str]:
        same = [u for u in locs if same_host(u, origin)]
        product = [u for u in same if looks_like_product_url(u)]
        return product

    # -- product pages -----------------------------------------------------

    def _read_pages(self, urls: list[str], result: DiscoveryResult) -> None:
        """Static HTML, ``concurrency`` at a time; a page without a structured
        price is rendered once (sequentially — the browser is single-threaded)."""
        def fetch(url: str) -> tuple[str, HttpResult]:
            return url, self._client.get(url, ACCEPT_HTML)

        with ThreadPoolExecutor(max_workers=self._client.concurrency) as pool:
            pages = list(pool.map(fetch, urls))

        needs_render: list[str] = []
        for url, res in pages:
            if not res.ok:
                result.failures.append(DiscoveryFailure(url, _status_of(res), _why(res)))
                continue
            readings = parse_product_page(res.text, url, self._currency)
            if readings:
                result.readings.extend(readings)
            else:
                needs_render.append(url)

        for url in needs_render:
            readings = self._render(url, result)
            if readings:
                result.readings.extend(readings)
            else:
                result.notes.append(f"{url}: no structured price on the page")

    def _render(self, url: str, result: DiscoveryResult) -> list[ProductReading]:
        rendered = getattr(self._renderer, "fetch_rendered", None)
        if not callable(rendered):
            return []
        refusal = self._client.acquire(url)
        if refusal is not None:
            return []
        try:
            fetched = rendered(url)
            html_of = getattr(getattr(fetched, "document", None), "html", None)
            html = html_of() if fetched.ok and callable(html_of) else None
            return parse_product_page(html or "", url, self._currency)
        except Exception:
            logger.exception("Rendered discovery failed for %s", url)
            return []
        finally:
            closer = getattr(self._renderer, "close_page", None)
            if callable(closer):
                try:
                    closer()
                except Exception:
                    logger.debug("close_page failed", exc_info=True)


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = ["DiscoveryFailure", "DiscoveryResult", "UrlOnlyDiscovery"]
