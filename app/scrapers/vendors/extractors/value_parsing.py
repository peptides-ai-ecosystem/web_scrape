"""Value parsing helpers shared by the structured-data and store-API extractors.

Pure functions over strings (price, currency, availability, size labels, URLs).
Split from structured_data.py to keep both files under 400 lines.
"""
from __future__ import annotations

import html as html_lib
import re
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.core.vendor_models import StockStatus
from app.scrapers.vendors.extractors.vendor_listing import MAX_PLAUSIBLE_PRICE

_PLACEHOLDER_LABELS = {"default title", "default", "title", "-"}

_AVAILABILITY = {
    "instock": StockStatus.IN_STOCK,
    "instoreonly": StockStatus.IN_STOCK,
    "onlineonly": StockStatus.IN_STOCK,
    "limitedavailability": StockStatus.IN_STOCK,
    "outofstock": StockStatus.OUT_OF_STOCK,
    "soldout": StockStatus.OUT_OF_STOCK,
    "discontinued": StockStatus.OUT_OF_STOCK,
    "backorder": StockStatus.ON_BACKORDER,
    "preorder": StockStatus.ON_BACKORDER,
    "presale": StockStatus.ON_BACKORDER,
}


# ---------------------------------------------------------------------------
# Small shared helpers (also used by the store API parsers)
# ---------------------------------------------------------------------------


def clean_text(value: Any) -> str | None:
    if value is None or isinstance(value, (dict, list)):
        return None
    text = html_lib.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = " ".join(text.split())
    return text or None


def to_price(value: Any) -> Decimal | None:
    """A plausible positive price from a number or a machine-readable string."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        raw = str(value)
    else:
        raw = str(value).strip().replace(" ", "").replace(" ", "")
        raw = re.sub(r"[^\d.,]", "", raw)
        if "," in raw and "." in raw:
            # 1,234.56 vs 1.234,56: the last separator is the decimal one.
            raw = raw.replace(",", "") if raw.rfind(".") > raw.rfind(",") else raw.replace(".", "").replace(",", ".")
        elif "," in raw:
            head, _, tail = raw.rpartition(",")
            raw = f"{head.replace(',', '')}.{tail}" if len(tail) in (1, 2) else raw.replace(",", "")
    try:
        price = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    if not price.is_finite() or price <= 0 or price > MAX_PLAUSIBLE_PRICE:
        return None
    exponent = price.as_tuple().exponent
    return price.quantize(Decimal("0.01")) if isinstance(exponent, int) and exponent < -2 else price


def to_currency(value: Any) -> str | None:
    text = clean_text(value)
    if text and re.fullmatch(r"[A-Za-z]{3}", text):
        return text.upper()
    return None


def availability_of(value: Any) -> StockStatus | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.rstrip("/").rsplit("/", 1)[-1].replace(" ", "").replace("_", "").lower()
    return _AVAILABILITY.get(key)


def usable_label(label: Any) -> str | None:
    text = clean_text(label)
    if not text or text.lower() in _PLACEHOLDER_LABELS:
        return None
    return text


def compose_name(base: str | None, label: str | None) -> str | None:
    """``"Retatrutide" + "10mg" -> "Retatrutide 10mg"``; no repeat if already in the name.

    The platform import parses the size out of the product name, so the size
    has to be in it.
    """
    base = clean_text(base)
    label = usable_label(label)
    if not label:
        return base
    if not base:
        return label
    if label.lower() in base.lower():
        return base
    return f"{base} {label}"


def label_from_names(base: str | None, variant_name: str | None) -> str | None:
    """What a variant's name adds to the product's: ``"Reta - 10mg"`` -> ``"10mg"``."""
    base = clean_text(base) or ""
    name = clean_text(variant_name)
    if not name:
        return None
    if base and name.lower().startswith(base.lower()):
        rest = name[len(base):].strip(" -–—:|,/()")
        return rest or None
    if base and name.lower() == base.lower():
        return None
    return name


def variant_url(page_url: str, key: str | None) -> str:
    """The page URL keyed by variant (``#variant=``), so sizes stay separate."""
    if not key:
        return page_url
    parts = urlsplit(page_url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, f"variant={key}"))


def strip_fragment(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
