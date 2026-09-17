"""base_url must reach the OpenAI client, not just the config entry."""

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openai_compatible.const import CONF_BASE_URL, DOMAIN


async def test_client_built_with_base_url(hass: HomeAssistant) -> None:
    """async_setup_entry must pass base_url to AsyncOpenAI."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "sk-test", CONF_BASE_URL: "http://192.0.2.10:4000/v1"},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.openai_compatible.openai.AsyncOpenAI"
    ) as mock_client:
        mock_client.return_value.platform_headers = lambda: {}
        mock_client.return_value.with_options.return_value.models.list = AsyncMock()
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert mock_client.call_args.kwargs["base_url"] == "http://192.0.2.10:4000/v1"


async def test_api_key_optional(hass: HomeAssistant) -> None:
    """An endpoint needing no auth should still set up."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_BASE_URL: "http://192.0.2.10:4000/v1"},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.openai_compatible.openai.AsyncOpenAI"
    ) as mock_client:
        mock_client.return_value.platform_headers = lambda: {}
        mock_client.return_value.with_options.return_value.models.list = AsyncMock()
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert mock_client.call_args.kwargs["api_key"] == "not-required"
