"""Extracts price, stock and COA link from a competitor product page (#288).

Everything here runs against :class:`~src.infrastructure.playwright_fetcher.PageDocument`,
so it is pure with respect to the browser and fully unit-testable.

The parsing is intentionally conservative. A vendor's layout can change
silently, and a *wrong* price that looks authoritative is worse than no price
at all, so every parser here returns ``None`` rather than a best guess:

* a price element whose text holds no recognisable amount yields ``None``,
  never ``0``;
* an implausible amount (``<= 0``, or above :data:`MAX_PLAUSIBLE_PRICE`) is
  rejected — it is almost always a phone number, a SKU or a "1000 mcg";
* stock text we do not recognise yields ``None``, never ``instock``;
* a COA href that is not http(s) after resolution yields ``None``.

Which selector produced each value is recorded, because that — not "the run
finished" — is what the confidence score is computed from.
"""
from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Optional, Sequence, Tuple
from urllib.parse import urljoin, urlsplit

from src.core.vendor_models import (
    ExtractedFields,
    FieldMatch,
    FieldSelectors,
    StockStatus,
    VendorTarget,
)
from src.infrastructure.playwright_fetcher import PageDocument

logger = logging.getLogger(__name__)

#: Above this, the "price" is a phone number, a molecular weight or a typo.
MAX_PLAUSIBLE_PRICE = Decimal("100000")

_CURRENCY_SYMBOLS = {
    "$": "USD",
    "US$": "USD",
    "usd": "USD",
    "€": "EUR",
    "eur": "EUR",
    "£": "GBP",
    "gbp": "GBP",
    "c$": "CAD",
    "cad": "CAD",
    "a$": "AUD",
    "aud": "AUD",
}

# 1.234,56 | 1,234.56 | 1234.56 | 1234
_AMOUNT_RE = re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,\s]\d{3})+|\d+)(?:[.,](\d{1,2}))?(?![\d])")

_OUT_OF_STOCK_PATTERNS = (
    "out of stock",
    "out-of-stock",
    "outofstock",
    "sold out",
    "soldout",
    "unavailable",
    "currently unavailable",
    "notify me when",
)
_BACKORDER_PATTERNS = (
    "backorder",
    "back order",
    "back-order",
    "pre-order",
    "preorder",
    "on backorder",
)
_IN_STOCK_PATTERNS = (
    "in stock",
    "in-stock",
    "instock",
    "available",
    "add to cart",
    "add to basket",
    "buy now",
)


# ---------------------------------------------------------------------------
# Field parsers
# ---------------------------------------------------------------------------


def parse_currency(text: str) -> Optional[str]:
    """ISO-4217 code stated by the page, or ``None`` if it states none."""
    lowered = text.lower()
    # Longest tokens first so "US$" wins over "$" and "CAD" over "cad" substrings.
    for token in sorted(_CURRENCY_SYMBOLS, key=len, reverse=True):
        if token.lower() in lowered:
            return _CURRENCY_SYMBOLS[token]
    for code in ("USD", "EUR", "GBP", "CAD", "AUD"):
        if re.search(rf"\b{code}\b", text, re.IGNORECASE):
            return code
    return None


def _is_hyphen_run(before: str, after: str) -> bool:
    """True when the amount sits inside a ``digit-digit`` hyphen run.

    Phone numbers, SKUs and CAS registry numbers all look like prices to a
    naive number scan; the hyphen between digit groups is what gives them
    away. A price range written ``$99-$189`` is unaffected, because the
    character after the hyphen is a currency symbol, not a digit.
    """
    return bool(re.search(r"\d-$", before)) or bool(re.match(r"^-\d", after))


def parse_price(text: Optional[str]) -> Tuple[Optional[Decimal], Optional[str]]:
    """Parse ``"$129.99 USD"`` into ``(Decimal('129.99'), 'USD')``.

    Returns ``(None, currency_or_None)`` when no plausible amount is present.
    A price range ("$99 – $189") yields the **lowest** amount, which is the
    "from" price a shopper is quoted; taking the highest would overstate a
    competitor and taking the middle would invent a number nobody published.
    """
    if not text:
        return None, None

    currency = parse_currency(text)

    candidates: list[Decimal] = []
    symbol_anchored: list[Decimal] = []
    for match in _AMOUNT_RE.finditer(text):
        whole, frac = match.group(1), match.group(2)
        normalised = re.sub(r"[\s,.]", "", whole)
        if not normalised:
            continue
        raw = f"{normalised}.{frac}" if frac else normalised
        try:
            value = Decimal(raw)
        except InvalidOperation:
            continue
        if value <= 0 or value > MAX_PLAUSIBLE_PRICE:
            continue

        before = text[max(0, match.start() - 3):match.start()]
        after = text[match.end():match.end() + 2]
        symbol_anchored_here = before.strip().endswith(("$", "€", "£", "¥"))

        # "1-800-555-0100" is a phone number, not four prices. A digit-hyphen
        # run that no currency symbol touches is never money.
        if not symbol_anchored_here and _is_hyphen_run(before, after):
            continue

        candidates.append(value)
        # "$250" is a price; the "10" in "10 x 5mg vials" is not. When the
        # page anchors any amount to a currency symbol, only those count.
        if symbol_anchored_here:
            symbol_anchored.append(value)

    pool = symbol_anchored or candidates
    if not pool:
        return None, currency
    return min(pool), currency


def parse_stock(text: Optional[str]) -> Optional[StockStatus]:
    """Map stock wording to the platform's vocabulary, or ``None``.

    Order matters: "out of stock" contains "stock", and a backorder notice
    often sits next to an "Add to cart" button, so the negative and the
    backorder readings are tested first.
    """
    if not text:
        return None
    lowered = " ".join(text.lower().split())
    if any(p in lowered for p in _OUT_OF_STOCK_PATTERNS):
        return StockStatus.OUT_OF_STOCK
    if any(p in lowered for p in _BACKORDER_PATTERNS):
        return StockStatus.ON_BACKORDER
    if any(p in lowered for p in _IN_STOCK_PATTERNS):
        return StockStatus.IN_STOCK
    return None


def resolve_coa_url(href: Optional[str], page_url: str) -> Optional[str]:
    """Absolutise a COA href; reject anything that is not http(s)."""
    if not href:
        return None
    candidate = urljoin(page_url, href.strip())
    parts = urlsplit(candidate)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return candidate


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


def _first_text(
    document: PageDocument, selectors: Sequence[str]
) -> Tuple[Optional[str], int, Optional[str]]:
    """First selector that yields text. Returns ``(text, index, selector)``."""
    for index, selector in enumerate(selectors):
        text = document.query_text(selector)
        if text:
            return text, index, selector
    return None, -1, None


def _first_attr(
    document: PageDocument, selectors: Sequence[str], attr: str
) -> Tuple[Optional[str], int, Optional[str]]:
    for index, selector in enumerate(selectors):
        value = document.query_attr(selector, attr)
        if value:
            return value, index, selector
    return None, -1, None


class VendorListingExtractor:
    """Reads one product page into :class:`ExtractedFields`."""

    def extract(
        self, document: PageDocument, target: VendorTarget, page_url: str
    ) -> ExtractedFields:
        selectors: FieldSelectors = target.selectors
        fields = ExtractedFields()

        # -- product name --------------------------------------------------
        name_text, name_idx, name_sel = _first_text(document, selectors.product_name)
        if name_text:
            fields.product_name = " ".join(name_text.split())
            fields.matches["product_name"] = FieldMatch(name_idx, name_sel or "", name_text)

        # -- price ---------------------------------------------------------
        price_text, price_idx, price_sel = _first_text(document, selectors.price)
        price, currency = parse_price(price_text)
        if price is not None:
            fields.price = price
            # Page-stated currency wins; the target's configured currency is
            # only a fallback for a page that prints a bare number.
            fields.currency = currency or target.currency
            fields.matches["price"] = FieldMatch(price_idx, price_sel or "", price_text)
        elif price_text:
            logger.info(
                "Vendor %s: price selector %r matched %r but held no plausible amount.",
                target.slug,
                price_sel,
                price_text[:120],
            )

        # -- stock ---------------------------------------------------------
        stock_text, stock_idx, stock_sel = _first_text(document, selectors.stock)
        stock = parse_stock(stock_text)
        if stock is not None:
            fields.stock_status = stock
            fields.matches["stock"] = FieldMatch(stock_idx, stock_sel or "", stock_text)

        # -- COA link ------------------------------------------------------
        coa_href, coa_idx, coa_sel = _first_attr(document, selectors.coa, "href")
        coa_url = resolve_coa_url(coa_href, page_url)
        if coa_url:
            fields.coa_url = coa_url
            fields.matches["coa"] = FieldMatch(coa_idx, coa_sel or "", coa_href)

        return fields
