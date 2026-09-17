"""Base-URL normalization and safe logging.

This module is intentionally separate from the vendored upstream files so that
re-syncing with home-assistant/core never conflicts with it.
"""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

ALLOWED_SCHEMES = frozenset({"http", "https"})


class InvalidBaseURL(ValueError):
    """Raised when a base URL is unusable."""


def normalize_base_url(url: str) -> str:
    """Strip whitespace and trailing slashes, and validate the scheme."""
    cleaned = (url or "").strip()
    if not cleaned:
        raise InvalidBaseURL("base URL is empty")

    parsed = urlparse(cleaned)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise InvalidBaseURL(f"unsupported scheme: {parsed.scheme or '(none)'}")
    if not parsed.netloc:
        raise InvalidBaseURL("base URL has no host")

    return urlunparse(parsed._replace(path=parsed.path.rstrip("/")))


def sanitize_url_for_logging(url: str) -> str:
    """Return the URL with any embedded credentials replaced by ***."""
    parsed = urlparse(url)
    if not parsed.username and not parsed.password:
        return url

    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunparse(parsed._replace(netloc=f"***@{host}"))
