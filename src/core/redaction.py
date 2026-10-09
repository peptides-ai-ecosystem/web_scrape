"""Credential redaction for the Sentry scrubber (FEEDBACK-3 G15).

Two layers, applied to any free text:

1. **Literal match** against the secret values this process actually holds:
   API_TOKEN, DATABASE_URL (and the password inside it), the Sentry DSN, and
   every environment variable whose *name* marks it as a credential
   (``*TOKEN*``, ``*SECRET*``, ``*PASSWORD*``, ``*API_KEY*``, ``*DATABASE_URL*``).
   Read on every call, so rotation and test monkeypatching take effect.
2. **Shape match** for credentials that are not ours but still must not be
   written down: ``Bearer …`` values, JWTs, ``sk-…`` keys, and the password in
   any ``scheme://user:password@host`` URL.
"""
from __future__ import annotations

import os
import re
from urllib.parse import urlsplit

from src.config import settings

MASK = "[redacted]"

_SHAPES = re.compile(
    r"""(
        \bsk-[A-Za-z0-9_\-]{8,}                 # OpenAI-style keys
        | \btvly-[A-Za-z0-9_\-]{8,}             # Tavily keys
        | \b[Bb]earer\s+[A-Za-z0-9._~+/=\-]{8,}  # inline bearer tokens
        | \beyJ[A-Za-z0-9._\-]{16,}             # JWTs
    )""",
    re.VERBOSE,
)

# scheme://user:password@host -> scheme://user:[redacted]@host
_URL_PASSWORD = re.compile(r"(?P<head>[A-Za-z][A-Za-z0-9+.\-]*://[^\s:/@]*:)(?P<pw>[^\s@/]+)@")

_SECRET_SETTINGS = ("API_TOKEN", "DATABASE_URL", "SENTRY_DSN")
_SECRET_ENV_MARKERS = ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "APIKEY", "DATABASE_URL", "DSN")

# The documented placeholder in src/config.py. Masking the word "password"
# everywhere would mangle unrelated text without protecting anything.
_PLACEHOLDERS = frozenset({"postgresql://user:password@localhost:5432/peptides_db", "password"})


def _candidate_values() -> list[tuple[str, str]]:
    pairs = [(name, str(getattr(settings, name, "") or "")) for name in _SECRET_SETTINGS]
    for name, value in os.environ.items():
        upper = name.upper()
        if any(marker in upper for marker in _SECRET_ENV_MARKERS):
            pairs.append((upper, value))
    return pairs


def secret_literals() -> list[str]:
    """Secret values currently configured, longest first."""
    values: list[str] = []
    for name, value in _candidate_values():
        value = value.strip()
        if not value:
            continue
        values.append(value)
        if "://" in value:
            try:
                parts = urlsplit(value)
                if parts.password:
                    values.append(parts.password)
                if "DSN" in name and parts.username:
                    values.append(parts.username)  # the DSN public key
            except ValueError:
                pass
    # Very short values would match everywhere and mangle unrelated text.
    uniq = {v for v in values if len(v) >= 6 and v not in _PLACEHOLDERS}
    return sorted(uniq, key=len, reverse=True)


def redact(text: str, literals: list[str] | None = None) -> str:
    """Return ``text`` with every known and credential-shaped secret masked."""
    if not text:
        return text
    for literal in literals if literals is not None else secret_literals():
        if literal in text:
            text = text.replace(literal, MASK)
    text = _URL_PASSWORD.sub(lambda m: f"{m.group('head')}{MASK}@", text)
    return _SHAPES.sub(MASK, text)
