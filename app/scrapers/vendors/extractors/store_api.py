"""Readings from public store catalogue APIs and sitemaps (AAD-1).

* **WooCommerce Store API** (``/wp-json/wc/store/v1/products``) — the public,
  unauthenticated API the shop's own cart/checkout blocks use. Prices come in
  minor units with ``currency_minor_unit``; a variable product's sizes are
  separate ``variation`` products.
* **Shopify** ``/products.json`` and ``/products/<handle>.json`` — every
  variant with its own price and availability.
* **Sitemaps** — ``<urlset>`` / ``<sitemapindex>`` XML, to find product pages
  when neither API is there.

Pure functions over decoded JSON / XML text; no I/O.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.core.vendor_models import ProductReading, StockStatus
from app.scrapers.vendors.extractors.structured_data import CONFIDENCE
from app.scrapers.vendors.extractors.value_parsing import (
    clean_text,
    compose_name,
    to_currency,
    to_price,
    usable_label,
    variant_url,
)
from app.scrapers.vendors.extractors.vendor_listing import MAX_PLAUSIBLE_PRICE

logger = logging.getLogger(__name__)

WOO_STORE_API_PATH = "/wp-json/wc/store/v1/products"


# ---------------------------------------------------------------------------
# WooCommerce Store API
# ---------------------------------------------------------------------------


def woo_price(prices: Any) -> tuple[Decimal | None, str | None]:
    """``{"price": "3999", "currency_minor_unit": 2, ...}`` -> ``(Decimal('39.99'), 'USD')``."""
    if not isinstance(prices, dict):
        return None, None
    currency = to_currency(prices.get("currency_code"))
    raw = prices.get("price")
    if raw in (None, ""):
        return None, currency
    try:
        minor = int(prices.get("currency_minor_unit", 2))
        amount = Decimal(str(raw)).scaleb(-minor)
    except (InvalidOperation, TypeError, ValueError):
        return None, currency
    if amount <= 0 or amount > MAX_PLAUSIBLE_PRICE:
        return None, currency
    return amount, currency


def woo_price_range(prices: Any) -> tuple[Decimal, Decimal] | None:
    if not isinstance(prices, dict) or not isinstance(prices.get("price_range"), dict):
        return None
    rng = prices["price_range"]
    low, _ = woo_price({**prices, "price": rng.get("min_amount")})
    high, _ = woo_price({**prices, "price": rng.get("max_amount")})
    if low is None or high is None:
        return None
    return low, high


def woo_stock(item: dict[str, Any]) -> StockStatus | None:
    availability = item.get("stock_availability")
    css = str((availability or {}).get("class") or "").lower() if isinstance(availability, dict) else ""
    if item.get("is_on_backorder") is True or "backorder" in css:
        return StockStatus.ON_BACKORDER
    if item.get("is_in_stock") is False or "out-of-stock" in css:
        return StockStatus.OUT_OF_STOCK
    if item.get("is_in_stock") is True or "in-stock" in css:
        return StockStatus.IN_STOCK
    return None


def woo_is_variable(item: dict[str, Any]) -> bool:
    return str(item.get("type") or "") == "variable" and bool(item.get("variations"))


def woo_variation_labels(parent: dict[str, Any]) -> dict[int, str]:
    """``{variation_id: "10mg"}`` from the parent's ``variations`` list."""
    out: dict[int, str] = {}
    for variation in parent.get("variations") or []:
        if not isinstance(variation, dict) or variation.get("id") is None:
            continue
        values = [
            clean_text(a.get("value"))
            for a in variation.get("attributes") or []
            if isinstance(a, dict) and clean_text(a.get("value"))
        ]
        if values:
            try:
                out[int(variation["id"])] = " / ".join(v for v in values if v)
            except (TypeError, ValueError):
                continue
    return out


def _woo_label_from_variation_item(item: dict[str, Any]) -> str | None:
    # Store API variation items name their attributes in "variation" on some
    # versions ("Size: 10mg"), or only carry the parent name.
    text = clean_text(item.get("variation"))
    if text:
        parts = [p.split(":", 1)[-1].strip() for p in text.split(",")]
        return " / ".join(p for p in parts if p) or None
    return None


def woo_simple_reading(item: dict[str, Any]) -> ProductReading | None:
    """One reading for a simple product (or a variable one we could not expand)."""
    permalink = str(item.get("permalink") or "").strip()
    if not permalink:
        return None
    name = clean_text(item.get("name"))
    price, currency = woo_price(item.get("prices"))
    confidence = CONFIDENCE["woo_store_api"]
    if woo_is_variable(item):
        rng = woo_price_range(item.get("prices"))
        if rng is not None and rng[0] != rng[1]:
            # A "from" price across sizes: no single size costs this.
            price = rng[0]
            confidence = 0.5
    return ProductReading(
        url=permalink,
        page_url=permalink,
        product_name=name,
        price=price,
        currency=currency,
        stock_status=woo_stock(item),
        sku=clean_text(item.get("sku")),
        method="woo_store_api",
        confidence=confidence,
    )


def woo_variation_readings(
    parent: dict[str, Any], variations: list[dict[str, Any]]
) -> list[ProductReading]:
    """One reading per size of a variable product."""
    permalink = str(parent.get("permalink") or "").strip()
    base = clean_text(parent.get("name"))
    labels = woo_variation_labels(parent)
    readings: list[ProductReading] = []
    for item in variations:
        if not isinstance(item, dict) or item.get("id") is None:
            continue
        try:
            vid = int(item["id"])
        except (TypeError, ValueError):
            continue
        label = labels.get(vid) or _woo_label_from_variation_item(item)
        price, currency = woo_price(item.get("prices"))
        own_link = str(item.get("permalink") or "").strip()
        url = own_link if own_link and own_link != permalink and "?" in own_link else variant_url(permalink, str(vid))
        readings.append(
            ProductReading(
                url=url,
                page_url=permalink,
                product_name=compose_name(base, label),
                price=price,
                currency=currency,
                stock_status=woo_stock(item),
                variant_label=usable_label(label),
                sku=clean_text(item.get("sku")),
                method="woo_store_api",
                # A size we cannot name cannot be matched to a size.
                confidence=CONFIDENCE["woo_store_api"] if label else 0.5,
            )
        )
    return readings


# ---------------------------------------------------------------------------
# Shopify
# ---------------------------------------------------------------------------


def shopify_readings(
    product: dict[str, Any], origin: str, currency: str | None = None
) -> list[ProductReading]:
    handle = str(product.get("handle") or "").strip()
    if not handle:
        return []
    page_url = f"{origin.rstrip('/')}/products/{handle}"
    base = clean_text(product.get("title"))
    variants = [v for v in product.get("variants") or [] if isinstance(v, dict)]
    many = len(variants) > 1
    readings: list[ProductReading] = []
    for variant in variants:
        label = usable_label(variant.get("title"))
        available = variant.get("available")
        stock = (
            StockStatus.IN_STOCK if available is True
            else StockStatus.OUT_OF_STOCK if available is False
            else None
        )
        url = f"{page_url}?variant={variant.get('id')}" if many and variant.get("id") is not None else page_url
        readings.append(
            ProductReading(
                url=url,
                page_url=page_url,
                product_name=compose_name(base, label),
                price=to_price(variant.get("price")),
                currency=currency,
                stock_status=stock,
                variant_label=label,
                sku=clean_text(variant.get("sku")),
                method="shopify_json",
                confidence=CONFIDENCE["shopify_json"] if (label or not many) else 0.5,
            )
        )
    return readings


# ---------------------------------------------------------------------------
# Sitemaps and URL shapes
# ---------------------------------------------------------------------------

_PRODUCT_PATH_RE = re.compile(r"/(product|products|shop|p|item|peptides?)/[^/]+/?$", re.IGNORECASE)
_NOT_PRODUCT_RE = re.compile(
    r"/(product-category|product-tag|product_cat|product_tag|collections|category|tag|cart|checkout|"
    r"my-account|account|blog|wp-json)(/|$)|\.(json|xml|jpg|jpeg|png|webp|gif|pdf)$",
    re.IGNORECASE,
)


def looks_like_product_url(url: str) -> bool:
    path = urlsplit(url).path or "/"
    if _NOT_PRODUCT_RE.search(path):
        return False
    return bool(_PRODUCT_PATH_RE.search(path))


def woo_product_slug(url: str) -> str | None:
    match = re.search(r"/product/([^/?#]+)/?$", urlsplit(url).path or "", re.IGNORECASE)
    return match.group(1) if match else None


def shopify_product_handle(url: str) -> str | None:
    match = re.search(r"/products/([^/?#.]+)/?$", urlsplit(url).path or "", re.IGNORECASE)
    return match.group(1) if match else None


def origin_of(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def parse_sitemap(xml_text: str) -> tuple[str | None, list[str]]:
    """``("index" | "urlset" | None, [loc, ...])`` from sitemap XML."""
    if not xml_text or "<" not in xml_text:
        return None, []
    text = xml_text.lstrip("﻿").strip()
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        # Sitemaps never need a DTD; refusing one rules out entity expansion.
        return None, []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None, []
    tag = root.tag.rsplit("}", 1)[-1].lower()
    kind = "index" if tag == "sitemapindex" else "urlset" if tag == "urlset" else None
    if kind is None:
        return None, []
    locs: list[str] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].lower() == "loc" and element.text:
            loc = element.text.strip()
            if loc.startswith(("http://", "https://")):
                locs.append(loc)
    return kind, locs


def rank_child_sitemaps(locs: list[str]) -> list[str]:
    """Product sitemaps first; post/page/category/author sitemaps dropped."""
    product = [u for u in locs if "product" in urlsplit(u).path.lower() and "cat" not in urlsplit(u).path.lower()]
    if product:
        return product
    skip = ("post", "page", "categor", "tag", "author", "attachment", "image", "video", "news", "blog")
    return [u for u in locs if not any(s in urlsplit(u).path.lower() for s in skip)]


def same_host(url: str, origin: str) -> bool:
    a = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    b = (urlsplit(origin).hostname or "").lower().removeprefix("www.")
    return bool(a) and a == b


__all__ = [
    "WOO_STORE_API_PATH",
    "looks_like_product_url",
    "origin_of",
    "parse_sitemap",
    "rank_child_sitemaps",
    "same_host",
    "shopify_product_handle",
    "shopify_readings",
    "woo_is_variable",
    "woo_price",
    "woo_product_slug",
    "woo_simple_reading",
    "woo_stock",
    "woo_variation_labels",
    "woo_variation_readings",
]
