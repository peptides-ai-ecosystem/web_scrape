"""SSRF guard for competitor scrape targets.

Targets are admin-managed URLs that this service then fetches from inside our
network (robots.txt with ``requests``, pages with a headless browser). Without
a guard an admin — or anyone holding an admin credential — could point a
"competitor" at ``http://127.0.0.1:…``, a private-range service, or the cloud
metadata endpoint ``http://169.254.169.254/`` and have the scraper read it.

The rule: a target URL must be ``http(s)`` and every address its host resolves
to must be a public (globally routable, unicast) address. Loopback, private
(RFC 1918 / ULA), link-local (incl. 169.254.169.254), shared/CGNAT,
multicast, reserved, unspecified and IPv4-mapped forms of those are refused,
and so is ``localhost`` / ``*.localhost``.

It is applied twice, on purpose:

* **save time** (API create/update, and literal addresses on every parse), so
  a bad target is refused with a clear 422 instead of failing later;
* **fetch time** (every robots.txt request, every page navigation, every
  redirect hop and every browser sub-request), with a fresh DNS lookup, so a
  hostname that resolved publicly when it was saved but resolves internally
  now (DNS rebinding, or a record simply changed) is still refused.

Residual risk, stated plainly: the fetch-time lookup here and the lookup the
HTTP client / browser then does are two separate resolutions, so a hostile
DNS server with a near-zero TTL can still race them. Closing that completely
needs network-level egress rules (no route from the scraper to internal
ranges), which this check complements rather than replaces.

``VENDOR_SCRAPE_ALLOW_PRIVATE_TARGETS=true`` disables the address check (the
scheme check stays) for local testing against a fixture site on 127.0.0.1.
It is off by default and must never be set in a deployed environment.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Callable, Iterable, List, Optional, Union
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
Resolver = Callable[[str], Iterable[str]]


class UnsafeTargetURLError(ValueError):
    """The URL points somewhere the scraper must never fetch."""


def private_targets_allowed() -> bool:
    """``VENDOR_SCRAPE_ALLOW_PRIVATE_TARGETS``, read on every call so tests
    (and an operator flipping it) take effect without a re-import."""
    from src.config import settings

    return bool(getattr(settings, "VENDOR_SCRAPE_ALLOW_PRIVATE_TARGETS", False))


def _system_resolver(host: str) -> List[str]:
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return [info[4][0] for info in infos]


def is_public_address(address: Union[str, IPAddress]) -> bool:
    """True only for a globally routable unicast address."""
    try:
        ip = ipaddress.ip_address(str(address).split("%", 1)[0]) if isinstance(address, str) else address
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        # ::ffff:127.0.0.1 and friends are judged by the IPv4 inside them.
        mapped = ip.ipv4_mapped or ip.sixtofour
        if mapped is not None:
            return is_public_address(mapped)
        if ip.teredo is not None:
            return False
    return bool(
        ip.is_global
        and not ip.is_multicast
        and not ip.is_reserved
        and not ip.is_loopback
        and not ip.is_link_local
        and not ip.is_private
        and not ip.is_unspecified
    )


def _normalise_host(host: str) -> str:
    return host.strip().strip("[]").rstrip(".").lower()


def check_host(host: Optional[str], *, resolve: bool = True, resolver: Optional[Resolver] = None) -> None:
    """Raise :class:`UnsafeTargetURLError` unless ``host`` is public.

    Args:
        resolve: also resolve a hostname and check every address it returns.
            ``False`` checks only what can be decided without DNS (IP literals
            and ``localhost``).
        resolver: ``host -> [address, ...]``; defaults to ``getaddrinfo``.
            A resolution failure raises too: an address we cannot see is not
            one we can vouch for.
    """
    name = _normalise_host(host or "")
    if not name:
        raise UnsafeTargetURLError("URL has no host")
    if private_targets_allowed():
        return
    if name == "localhost" or name.endswith(".localhost"):
        raise UnsafeTargetURLError(f"host '{name}' is a loopback name")
    try:
        literal: Optional[IPAddress] = ipaddress.ip_address(name.split("%", 1)[0])
    except ValueError:
        literal = None
    if literal is not None:
        if not is_public_address(literal):
            raise UnsafeTargetURLError(f"host '{name}' is not a public address")
        return
    if not resolve:
        return
    try:
        addresses = list((resolver or _system_resolver)(name))
    except (OSError, UnicodeError) as exc:
        raise UnsafeTargetURLError(f"host '{name}' does not resolve ({type(exc).__name__})") from None
    if not addresses:
        raise UnsafeTargetURLError(f"host '{name}' does not resolve")
    for address in addresses:
        if not is_public_address(address):
            raise UnsafeTargetURLError(f"host '{name}' resolves to a non-public address")


def check_url(url: str, *, resolve: bool = True, resolver: Optional[Resolver] = None) -> None:
    """Raise :class:`UnsafeTargetURLError` unless ``url`` is a public http(s) URL."""
    try:
        parts = urlsplit(url)
        host = parts.hostname
        parts.port  # noqa: B018 — raises ValueError on a malformed port
    except ValueError as exc:
        raise UnsafeTargetURLError(f"malformed URL: {exc}") from None
    if parts.scheme not in ("http", "https"):
        raise UnsafeTargetURLError(f"scheme '{parts.scheme}' is not http(s)")
    check_host(host, resolve=resolve, resolver=resolver)


__all__ = [
    "UnsafeTargetURLError",
    "check_host",
    "check_url",
    "is_public_address",
    "private_targets_allowed",
]
