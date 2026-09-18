"""Base-URL normalization and safe logging.

This module is intentionally separate from the vendored upstream files so that
re-syncing with home-assistant/core never conflicts with it.
"""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

ALLOWED_SCHEMES = frozenset({"http", "https"})


class InvalidBaseURL(ValueError):
    """Raised when a base URL is unusable."""


class CredentialsInBaseURL(InvalidBaseURL):
    """Raised when a base URL embeds a username or password.

    A distinct subclass (rather than reusing the generic InvalidBaseURL
    message) so the config flow can show a specific, actionable error
    instead of the generic "not a valid URL" one.
    """


def normalize_base_url(url: str) -> str:
    """Strip whitespace and trailing slashes, and validate the scheme.

    Rejects a URL carrying a username or password component: authentication
    belongs in the API key field, which is handled (and never logged) safely
    on its own — a base_url is user-suppliable and read back into log/error
    text by vendored code this fork does not touch, so credentials must never
    be accepted here in the first place.
    """
    cleaned = (url or "").strip()
    if not cleaned:
        raise InvalidBaseURL("base URL is empty")

    parsed = urlparse(cleaned)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise InvalidBaseURL(f"unsupported scheme: {parsed.scheme or '(none)'}")
    if not parsed.netloc:
        raise InvalidBaseURL("base URL has no host")
    if parsed.username or parsed.password:
        raise CredentialsInBaseURL(
            "base URL must not contain a username or password; "
            "use the API key field for authentication"
        )

    return urlunparse(parsed._replace(path=parsed.path.rstrip("/")))


def sanitize_url_for_logging(url: str) -> str:
    """Return the URL with any embedded credentials replaced by ***.

    This only recognizes credentials urlparse places in an authority
    (``user:pass@host``) component of an absolute http(s)/-scheme URL. It is
    not a general-purpose credential scrubber: a scheme-less or relative
    string with an embedded ``user:pass@`` substring passes through
    unmasked, since urlparse won't parse it as a netloc. Safe today because
    every caller normalizes with normalize_base_url() first (which both
    requires an absolute http(s) URL and rejects embedded credentials
    outright) before this is ever called on it; do not rely on this function
    alone to sanitize an arbitrary, unvalidated string.
    """
    parsed = urlparse(url)
    if not parsed.username and not parsed.password:
        return url

    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunparse(parsed._replace(netloc=f"***@{host}"))


def title_from_base_url(url: str) -> str:
    """Return a config entry title identifying the provider.

    Upstream titles every entry "ChatGPT", which is wrong the moment the
    endpoint is not OpenAI's and useless when there is one entry per provider.
    The host (with port, when given) is what actually distinguishes them.
    Falls back to the whole string if it cannot be parsed, so this never
    raises in the middle of creating an entry.
    """
    try:
        netloc = urlparse(url).netloc
    except ValueError:
        return url
    return netloc or url
