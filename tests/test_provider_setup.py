"""Setup creates a provider, not a pile of guessed endpoints.

One config entry per server/provider (LiteLLM, OpenAI, anything else): the
flow asks for a URL and a key and stops there. Entities are added afterwards,
one per type and model, by the subentry flows.
"""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from homeassistant.const import CONF_NAME

from custom_components.openai_compatible.const import CONF_BASE_URL, DOMAIN

LITELLM = "http://192.0.2.10:4000/v1"


async def _run_user_step(
    hass: HomeAssistant, base_url: str, api_key: str, name: str | None = None
) -> dict:
    """Drive the user step to completion and return the flow result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with (
        patch(
            "custom_components.openai_compatible.config_flow.openai.resources.models.AsyncModels.list",
            new_callable=AsyncMock,
        ),
        patch(
            "custom_components.openai_compatible.async_setup_entry",
            return_value=True,
        ),
    ):
        user_input = {CONF_BASE_URL: base_url, "api_key": api_key}
        if name is not None:
            user_input[CONF_NAME] = name
        done = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
        await hass.async_block_till_done()
    return done


async def test_setup_creates_no_subentries(hass: HomeAssistant) -> None:
    """Auto-created stt/tts entities pointed at OpenAI-only model names were
    dead on arrival against a third-party endpoint."""
    done = await _run_user_step(hass, LITELLM, "sk-test")

    assert done["type"] is FlowResultType.CREATE_ENTRY
    assert list(done["subentries"]) == []


async def test_entry_is_titled_after_the_endpoint(hass: HomeAssistant) -> None:
    """The title said "ChatGPT" regardless of which provider it pointed at."""
    done = await _run_user_step(hass, LITELLM, "sk-test")

    assert done["title"] == "192.0.2.10:4000"


async def test_a_second_entry_for_the_same_provider_is_allowed(
    hass: HomeAssistant,
) -> None:
    """Upstream aborts as already_configured on matching url+key; several
    entries against one server have to be possible here."""
    first = await _run_user_step(hass, LITELLM, "sk-test")
    assert first["type"] is FlowResultType.CREATE_ENTRY

    second = await _run_user_step(hass, LITELLM, "sk-test")
    assert second["type"] is FlowResultType.CREATE_ENTRY
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("http://192.0.2.10:4000/v1", "192.0.2.10:4000"),
        ("https://api.openai.com/v1", "api.openai.com"),
        ("https://openrouter.ai/api/v1", "openrouter.ai"),
    ],
)
async def test_title_from_base_url(base_url: str, expected: str) -> None:
    """The host distinguishes one provider entry from another."""
    from custom_components.openai_compatible.url_util import title_from_base_url

    assert title_from_base_url(base_url) == expected


async def test_name_becomes_the_entry_title(hass: HomeAssistant) -> None:
    """With one entry per provider, the user names the provider."""
    done = await _run_user_step(hass, LITELLM, "sk-test", name="LiteLLM")

    assert done["title"] == "LiteLLM"


async def test_name_is_not_stored_as_connection_data(hass: HomeAssistant) -> None:
    """The name is the entry title; it is not part of how we reach the API."""
    done = await _run_user_step(hass, LITELLM, "sk-test", name="LiteLLM")

    assert done["data"] == {CONF_BASE_URL: LITELLM, "api_key": "sk-test"}
    assert CONF_NAME not in done["data"]


async def test_blank_name_falls_back_to_the_endpoint_host(
    hass: HomeAssistant,
) -> None:
    """Leaving it empty should not produce an entry titled ""."""
    done = await _run_user_step(hass, LITELLM, "sk-test", name="   ")

    assert done["title"] == "192.0.2.10:4000"
