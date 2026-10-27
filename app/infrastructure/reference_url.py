"""Allow-list guard for the reference-site peek (AWD-17, SSRF).

``POST /sync/peek`` makes a headless browser open a URL the admin tab asks for.
Unlike competitor targets (any public store), the peek has one legitimate
source, the reference site, so the rule is an allow-list, not a deny-list:

* ``https`` only, no ``user:pass@``, no port other than 443;
* the host must be exactly one of ``PEEK_ALLOWED_HOSTS`` (no sub-domain or
  suffix matching: ``pep-pedia.org.evil.com`` and ``evil.com/pep-pedia.org``
  are both refused);
* the host must still pass the public-address check of ``url_safety`` (a fresh
  DNS lookup), so an allowed name that has been re-pointed at an internal
  address is refused too;
* after the page loaded, the URL the browser ended on must be on the list too
  (``final_url_allowed``): a redirect off the list discards the result.

Residual risk, stated plainly: a browser follows redirects itself, so the check
on the final URL happens after the request. The page is never read or returned
in that case, but the redirect target was contacted once. Closing that fully
needs egress rules on the box; this guard complements them.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from app.core.config import settings
from app.infrastructure.url_safety import UnsafeTargetURLError, check_url

_MAX_URL_LENGTH = 2048


def allowed_hosts() -> frozenset[str]:
    """The configured reference hosts, lower-cased."""
    raw = str(settings.PEEK_ALLOWED_HOSTS or "")
    return frozenset(h.strip().strip(".").lower() for h in raw.split(",") if h.strip())


def _host_on_list(host: str | None) -> bool:
    if not host:
        return False
    return host.strip(".").lower() in allowed_hosts()


def check_reference_url(url: str) -> str:
    """Return the URL to fetch, or raise :class:`UnsafeTargetURLError`."""
    candidate = (url or "").strip()
    if not candidate or len(candidate) > _MAX_URL_LENGTH or any(ord(ch) < 33 for ch in candidate):
        raise UnsafeTargetURLError("URL is empty, too long or contains whitespace or control characters")
    try:
        parts = urlsplit(candidate)
        host = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise UnsafeTargetURLError(f"malformed URL: {exc}") from None
    if parts.scheme != "https":
        raise UnsafeTargetURLError("only https URLs can be read")
    if parts.username or parts.password:
        raise UnsafeTargetURLError("URLs with credentials are not allowed")
    if port not in (None, 443):
        raise UnsafeTargetURLError("only the default https port is allowed")
    if not _host_on_list(host):
        raise UnsafeTargetURLError("host is not one of the configured reference sites")
    check_url(candidate)  # public addresses only, fresh DNS lookup
    return parts._replace(fragment="").geturl()


def final_url_allowed(url: str | None) -> bool:
    """True when the URL the browser ended on is https on an allowed host."""
    try:
        parts = urlsplit(url or "")
        return parts.scheme == "https" and _host_on_list(parts.hostname)
    except ValueError:
        return False


__all__ = ["allowed_hosts", "check_reference_url", "final_url_allowed"]
