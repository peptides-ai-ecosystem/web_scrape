"""Selector-free price extraction from a product page's structured data (AAD-1).

Most shops already publish their prices machine-readably for search engines.
Reading that is far sturdier than a CSS selector, because it does not move
when the theme changes. In order of trust:

1. **schema.org JSON-LD** — ``Product`` / ``ProductGroup`` with ``Offer``,
   a list of offers, or ``AggregateOffer``; ``hasVariant`` products. One
   reading per variant, carrying its size label.
2. **Microdata** — ``itemprop="price"`` / ``priceCurrency`` / ``availability``.
3. **OpenGraph / product meta** — ``product:price:amount`` and friends.

The same conservative rules as the selector extractor apply: an amount that
is not a plausible price is dropped (never ``0``), unknown availability stays
``None`` (never "in stock"), and a reading we cannot tie to a size is scored
below the acceptance threshold so a human looks at it before it is used.

Pure functions over strings — no I/O — so they are tested on recorded pages.
"""
from __future__ import annotations

import html as html_lib
import json
import logging
import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from app.core.vendor_models import ProductReading, StockStatus
from app.scrapers.vendors.extractors.page_scan import PageScan
from app.scrapers.vendors.extractors.value_parsing import (
    availability_of,
    clean_text,
    compose_name,
    label_from_names,
    strip_fragment,
    to_currency,
    to_price,
    usable_label,
    variant_url,
)
from app.scrapers.vendors.extractors.vendor_listing import MAX_PLAUSIBLE_PRICE

logger = logging.getLogger(__name__)

#: Confidence per source. 0.6 is the default acceptance threshold
#: (VENDOR_MIN_CONFIDENCE): anything below it is stored flagged for review.
CONFIDENCE = {
    "woo_store_api": 0.95,
    "shopify_json": 0.95,
    "json_ld": 0.9,
    "microdata": 0.75,
    "opengraph": 0.65,
}
#: Several prices on one page that we cannot tell apart by size, or only a
#: price range: kept, but flagged for a human.
AMBIGUOUS_CONFIDENCE = 0.5

def _load_ld(block: str) -> list[Any]:
    text = block.strip()
    text = text.removeprefix("<!--")
    text = text.removesuffix("-->")
    text = text.strip().removeprefix("//<![CDATA[").removesuffix("//]]>").strip()
    if not text:
        return []
    try:
        data = json.loads(text, strict=False)
    except ValueError:
        logger.debug("Unparseable JSON-LD block skipped")
        return []
    return data if isinstance(data, list) else [data]


def _types(node: dict[str, Any]) -> list[str]:
    raw = node.get("@type")
    values = raw if isinstance(raw, list) else [raw]
    return [str(v).rsplit("/", 1)[-1] for v in values if v]


def _walk(nodes: Iterable[Any]) -> Iterable[dict[str, Any]]:
    stack = list(nodes)
    while stack:
        node = stack.pop(0)
        if isinstance(node, list):
            stack[:0] = node
            continue
        if not isinstance(node, dict):
            continue
        yield node
        if "@graph" in node:
            stack[:0] = node["@graph"] if isinstance(node["@graph"], list) else [node["@graph"]]
        # Products are sometimes nested (mainEntity of a WebPage, itemListElement).
        for key in ("mainEntity", "itemListElement", "item"):
            child = node.get(key)
            if isinstance(child, (dict, list)):
                stack.append(child)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _offer_price(offer: dict[str, Any]) -> Decimal | None:
    price = to_price(offer.get("price"))
    if price is not None:
        return price
    for spec in _as_list(offer.get("priceSpecification")):
        if isinstance(spec, dict):
            price = to_price(spec.get("price"))
            if price is not None:
                return price
    return None


def _offer_currency(offer: dict[str, Any]) -> str | None:
    currency = to_currency(offer.get("priceCurrency"))
    if currency:
        return currency
    for spec in _as_list(offer.get("priceSpecification")):
        if isinstance(spec, dict) and to_currency(spec.get("priceCurrency")):
            return to_currency(spec.get("priceCurrency"))
    return None


def _flatten_offers(offers: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """``(concrete offers, aggregate offers without a concrete list)``."""
    concrete: list[dict[str, Any]] = []
    aggregates: list[dict[str, Any]] = []
    for offer in _as_list(offers):
        if not isinstance(offer, dict):
            continue
        if "AggregateOffer" in _types(offer):
            inner = [o for o in _as_list(offer.get("offers")) if isinstance(o, dict)]
            if inner:
                more, aggs = _flatten_offers(inner)
                concrete.extend(more)
                aggregates.extend(aggs)
            else:
                aggregates.append(offer)
        else:
            concrete.append(offer)
    return concrete, aggregates


def _product_readings(
    product: dict[str, Any],
    page_url: str,
    default_currency: str | None,
    *,
    base_name: str | None = None,
    variant_key: str | None = None,
    variant_label: str | None = None,
) -> list[ProductReading]:
    name = clean_text(product.get("name"))
    base = base_name or name
    label = variant_label
    if label is None and base_name:
        label = usable_label(product.get("size")) or label_from_names(base_name, name)
    sku = clean_text(product.get("sku"))
    product_url = page_url
    concrete, aggregates = _flatten_offers(product.get("offers"))

    readings: list[ProductReading] = []
    priced = [o for o in concrete if _offer_price(o) is not None]
    many = len(priced) > 1
    for index, offer in enumerate(priced):
        offer_label = label
        if many and offer_label is None:
            offer_label = (
                label_from_names(base, clean_text(offer.get("name")))
                or label_from_names(base, clean_text((offer.get("itemOffered") or {}).get("name"))
                                    if isinstance(offer.get("itemOffered"), dict) else None)
                or usable_label(offer.get("size"))
            )
        offer_sku = clean_text(offer.get("sku")) or sku
        key = variant_key
        if many:
            key = offer_sku or (offer_label and re.sub(r"\s+", "-", offer_label.lower())) or str(index + 1)
        confidence = CONFIDENCE["json_ld"]
        if many and not offer_label:
            confidence = AMBIGUOUS_CONFIDENCE
        readings.append(
            ProductReading(
                url=variant_url(product_url, key),
                page_url=product_url,
                product_name=compose_name(base, offer_label),
                price=_offer_price(offer),
                currency=_offer_currency(offer) or default_currency,
                stock_status=availability_of(offer.get("availability")),
                variant_label=usable_label(offer_label),
                sku=offer_sku,
                method="json_ld",
                confidence=confidence,
            )
        )
    if readings:
        return readings

    for aggregate in aggregates:
        low = to_price(aggregate.get("lowPrice")) or _offer_price(aggregate)
        high = to_price(aggregate.get("highPrice"))
        if low is None:
            continue
        ranged = high is not None and high != low
        readings.append(
            ProductReading(
                url=variant_url(product_url, variant_key),
                page_url=product_url,
                product_name=compose_name(base, label),
                price=low,
                currency=_offer_currency(aggregate) or default_currency,
                stock_status=availability_of(aggregate.get("availability")),
                variant_label=usable_label(label),
                sku=sku,
                method="json_ld",
                # "from $X" across sizes is not the price of any one size.
                confidence=AMBIGUOUS_CONFIDENCE if ranged else CONFIDENCE["json_ld"],
            )
        )
        break
    return readings


def json_ld_readings(
    ld_blocks: Iterable[str], page_url: str, default_currency: str | None = None
) -> list[ProductReading]:
    nodes: list[Any] = []
    for block in ld_blocks:
        nodes.extend(_load_ld(block))
    readings: list[ProductReading] = []
    consumed: set = set()
    all_nodes = list(_walk(nodes))
    for node in all_nodes:
        types = _types(node)
        if "ProductGroup" in types:
            group_name = clean_text(node.get("name"))
            variants = [v for v in _as_list(node.get("hasVariant")) if isinstance(v, dict)]
            for variant in variants:
                consumed.add(id(variant))
                key = clean_text(variant.get("sku")) or clean_text(variant.get("@id"))
                variant_page = page_url
                if isinstance(variant.get("url"), str) and variant["url"].strip():
                    candidate = urljoin(page_url, variant["url"].strip())
                    if urlsplit(candidate).netloc == urlsplit(page_url).netloc:
                        variant_page = candidate
                found = _product_readings(
                    variant, variant_page, default_currency, base_name=group_name,
                    variant_key=key if variant_page == page_url else None,
                )
                readings.extend(found)
            if not variants:
                readings.extend(_product_readings(node, page_url, default_currency))
            consumed.add(id(node))
    for node in all_nodes:
        if id(node) in consumed or "Product" not in _types(node):
            continue
        readings.extend(_product_readings(node, page_url, default_currency))
    # The same offer is sometimes published twice (theme + SEO plugin).
    unique: dict[str, ProductReading] = {}
    for reading in readings:
        unique.setdefault(reading.url, reading)
    return list(unique.values())


def parse_product_page(
    html: str, page_url: str, default_currency: str | None = None
) -> list[ProductReading]:
    """Every price reading a product page publishes, best source first."""
    if not html:
        return []
    scan = PageScan()
    try:
        scan.feed(html)
        scan.close()
    except Exception:
        logger.debug("HTML scan failed for %s", page_url, exc_info=True)

    readings = json_ld_readings(scan.ld_blocks, page_url, default_currency)
    if readings:
        return readings

    fallback_name = clean_text(scan.microdata.get("name")) or clean_text(scan.h1) or clean_text(
        scan.meta.get("og:title")
    ) or clean_text(scan.title)

    price = to_price(scan.microdata.get("price")) or to_price(scan.microdata.get("lowPrice"))
    if price is not None:
        return [
            ProductReading(
                url=page_url,
                page_url=page_url,
                product_name=fallback_name,
                price=price,
                currency=to_currency(scan.microdata.get("priceCurrency")) or default_currency,
                stock_status=availability_of(scan.microdata.get("availability")),
                sku=clean_text(scan.microdata.get("sku")),
                method="microdata",
                confidence=CONFIDENCE["microdata"],
            )
        ]

    for amount_key, currency_key in (
        ("product:price:amount", "product:price:currency"),
        ("og:price:amount", "og:price:currency"),
    ):
        price = to_price(scan.meta.get(amount_key))
        if price is not None:
            return [
                ProductReading(
                    url=page_url,
                    page_url=page_url,
                    product_name=clean_text(scan.meta.get("og:title")) or fallback_name,
                    price=price,
                    currency=to_currency(scan.meta.get(currency_key)) or default_currency,
                    stock_status=availability_of(
                        scan.meta.get("product:availability") or scan.meta.get("og:availability")
                    ),
                    method="opengraph",
                    confidence=CONFIDENCE["opengraph"],
                )
            ]
    return []


__all__ = [
    "AMBIGUOUS_CONFIDENCE",
    "CONFIDENCE",
    "availability_of",
    "clean_text",
    "compose_name",
    "json_ld_readings",
    "label_from_names",
    "parse_product_page",
    "strip_fragment",
    "to_currency",
    "to_price",
    "usable_label",
    "variant_url",
]
