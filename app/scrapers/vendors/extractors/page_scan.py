"""HTML scan for structured data: JSON-LD blocks, microdata, meta tags, title and h1.

Split from structured_data.py to keep both files under 400 lines.
"""
from __future__ import annotations

from html.parser import HTMLParser


class PageScan(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ld_blocks: list[str] = []
        self.meta: dict[str, str] = {}
        self.microdata: dict[str, str] = {}
        self.title: str | None = None
        self.h1: str | None = None
        self._in_ld = False
        self._ld_buf: list[str] = []
        self._capture: str | None = None
        self._capture_buf: list[str] = []
        self._in_title = False
        self._in_h1 = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "script" and "ld+json" in a.get("type", "").lower():
            self._in_ld = True
            self._ld_buf = []
            return
        if tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key and "content" in a and key not in self.meta:
                self.meta[key] = a["content"]
        if tag == "title":
            self._in_title = True
        if tag == "h1" and self.h1 is None:
            self._in_h1 = True
            self._capture_buf = []
        prop = a.get("itemprop", "").strip()
        if prop in ("price", "priceCurrency", "availability", "name", "sku", "lowPrice"):
            value = a.get("content") or (a.get("href") if prop == "availability" else None)
            if value:
                self.microdata.setdefault(prop, value)
            elif prop not in self.microdata and tag != "meta":
                self._capture = prop
                self._capture_buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_ld:
            self._in_ld = False
            self.ld_blocks.append("".join(self._ld_buf))
        if tag == "title":
            self._in_title = False
        if self._capture is not None:
            text = " ".join("".join(self._capture_buf).split())
            if text:
                self.microdata.setdefault(self._capture, text)
            self._capture = None
        if tag == "h1" and self._in_h1:
            self._in_h1 = False
            self.h1 = " ".join("".join(self._capture_buf).split()) or None

    def handle_data(self, data: str) -> None:
        if self._in_ld:
            self._ld_buf.append(data)
        elif self._capture is not None or self._in_h1:
            self._capture_buf.append(data)
        elif self._in_title:
            self.title = ((self.title or "") + data).strip() or None
