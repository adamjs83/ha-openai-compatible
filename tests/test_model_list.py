"""Model discovery: turn an endpoint's GET /v1/models into a picker."""

from unittest.mock import AsyncMock, MagicMock

import openai
import pytest

from homeassistant.helpers.selector import SelectSelector

from custom_components.openai_compatible.model_list import (
    async_fetch_model_ids,
    model_field,
)


def _client(model_ids: list[str] | None = None, *, error: Exception | None = None):
    """Return a stub AsyncOpenAI whose models.list yields model_ids or raises."""
    client = MagicMock()
    # Production calls client.with_options(...).models.list(); returning the
    # same stub keeps the per-request options visible to assertions.
    client.with_options.return_value = client
    if error is not None:
        client.models.list = AsyncMock(side_effect=error)
    else:
        page = MagicMock()
        page.data = [MagicMock(id=model_id) for model_id in (model_ids or [])]
        client.models.list = AsyncMock(return_value=page)
    return client


async def test_fetch_returns_sorted_unique_ids() -> None:
    """A proxy can list the same alias twice; the picker should show it once."""
    client = _client(["gpt-4o-mini", "claude-sonnet", "gpt-4o-mini", "llama-3.3"])

    assert await async_fetch_model_ids(client) == [
        "claude-sonnet",
        "gpt-4o-mini",
        "llama-3.3",
    ]


async def test_fetch_ignores_entries_without_an_id() -> None:
    """Don't put a blank option in the dropdown."""
    page = MagicMock()
    page.data = [MagicMock(id="real-model"), MagicMock(id=None), MagicMock(id="")]
    client = MagicMock()
    client.with_options.return_value = client
    client.models.list = AsyncMock(return_value=page)

    assert await async_fetch_model_ids(client) == ["real-model"]


async def test_fetch_does_not_retry() -> None:
    """This runs while the user waits on a dialog; retries would stall it."""
    client = _client(["gpt-4o-mini"])

    await async_fetch_model_ids(client, timeout=3.0)

    client.with_options.assert_called_once_with(max_retries=0, timeout=3.0)


@pytest.mark.parametrize(
    "error",
    [
        openai.APIConnectionError(request=MagicMock()),
        openai.AuthenticationError(
            "nope", response=MagicMock(status_code=401), body=None
        ),
    ],
)
async def test_fetch_survives_an_endpoint_that_will_not_list(error: Exception) -> None:
    """Model discovery is a convenience; it must never break the config flow."""
    assert await async_fetch_model_ids(_client(error=error)) == []


async def test_fetch_survives_a_non_openai_error() -> None:
    """Discovery must never break the form it runs inside.

    A proxy can return a payload the SDK cannot parse, or a client can be
    wired in a way that raises something other than an OpenAIError; either way
    the dropdown should degrade to a text box, not take the dialog down.
    """
    client = MagicMock()
    client.with_options.return_value = client
    client.models.list = MagicMock(return_value="not awaitable")

    assert await async_fetch_model_ids(client) == []


async def test_field_is_a_dropdown_that_still_accepts_a_typed_name() -> None:
    """A proxy may serve a model it does not advertise, so allow free text."""
    field = model_field(["claude-sonnet", "gpt-4o-mini"])

    assert isinstance(field, SelectSelector)
    assert field.config["options"] == ["claude-sonnet", "gpt-4o-mini"]
    assert field.config["custom_value"] is True


async def test_field_falls_back_to_free_text_when_no_models_are_known() -> None:
    """An endpoint that won't list models must still be configurable by hand."""
    assert model_field([]) is str
