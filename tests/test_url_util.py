"""URL hygiene: normalize input, never log credentials."""

import pytest

from custom_components.openai_compatible.url_util import (
    CredentialsInBaseURL,
    InvalidBaseURL,
    normalize_base_url,
    sanitize_url_for_logging,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://192.0.2.10:4000/v1", "http://192.0.2.10:4000/v1"),
        ("http://192.0.2.10:4000/v1/", "http://192.0.2.10:4000/v1"),
        ("  https://api.openai.com/v1  ", "https://api.openai.com/v1"),
        ("http://host:4000/v1///", "http://host:4000/v1"),
    ],
)
def test_normalize(raw, expected):
    assert normalize_base_url(raw) == expected


@pytest.mark.parametrize("raw", ["ftp://host/v1", "not-a-url", "", "   "])
def test_normalize_rejects(raw):
    with pytest.raises(InvalidBaseURL):
        normalize_base_url(raw)


@pytest.mark.parametrize(
    "raw",
    [
        "https://user:secret@host:4000/v1",
        "https://user@host:4000/v1",
        "https://:secret@host:4000/v1",
    ],
)
def test_normalize_rejects_embedded_credentials(raw):
    """Authentication belongs in the API key field, never in base_url."""
    with pytest.raises(CredentialsInBaseURL):
        normalize_base_url(raw)


def test_credentials_in_base_url_is_an_invalid_base_url():
    """CredentialsInBaseURL must still be catchable as InvalidBaseURL."""
    with pytest.raises(InvalidBaseURL):
        normalize_base_url("https://user:secret@host:4000/v1")


def test_sanitize_strips_credentials():
    assert (
        sanitize_url_for_logging("https://user:secret@host:4000/v1")
        == "https://***@host:4000/v1"
    )


def test_sanitize_leaves_clean_urls_alone():
    assert sanitize_url_for_logging("http://host:4000/v1") == "http://host:4000/v1"
