"""Each endpoint type picks its model from what the provider advertises.

Upstream defaults every model field to an OpenAI name and offers no way to see
what the endpoint actually serves, so configuring a proxy meant typing exact
model ids from memory -- and for conversation/AI Task the field was skipped
entirely unless you knew to untick "recommended" first.
"""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.selector import SelectSelector

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openai_compatible.const import (
    CONF_CHAT_MODEL,
    CONF_RECOMMENDED,
)

PROVIDER_MODELS = ["claude-sonnet-4-6", "gpt-4o-mini", "whisper-1"]
DISCOVERY = "custom_components.openai_compatible.config_flow.async_fetch_model_ids"


def _field(result: dict, key: str):
    """Return the schema field for key in a shown form."""
    schema = result["data_schema"].schema
    return next(value for marker, value in schema.items() if marker == key)


def _marker(result: dict, key: str):
    """Return the schema marker (which carries the default) for key."""
    schema = result["data_schema"].schema
    return next(marker for marker in schema if marker == key)


async def _model_step(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    subentry_type: str,
    models: list[str],
) -> dict:
    """Return the form that asks for the model, for any endpoint type.

    stt and tts are single-step flows that ask on init; conversation and
    ai_task_data ask on the step after it.
    """
    with patch(DISCOVERY, return_value=models):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, subentry_type),
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        if subentry_type in ("stt", "tts"):
            return result

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_NAME: "An endpoint", CONF_RECOMMENDED: False},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "additional"
        return result


@pytest.mark.parametrize(
    "subentry_type", ["conversation", "ai_task_data", "stt", "tts"]
)
async def test_every_type_offers_the_providers_models(
    hass: HomeAssistant,
    mock_init_component: None,
    mock_config_entry: MockConfigEntry,
    subentry_type: str,
) -> None:
    """All four endpoint types get a dropdown, not a free-text box."""
    result = await _model_step(
        hass, mock_config_entry, subentry_type, PROVIDER_MODELS
    )

    field = _field(result, CONF_CHAT_MODEL)
    assert isinstance(field, SelectSelector)
    assert field.config["options"] == PROVIDER_MODELS
    # A provider may route a model it does not advertise.
    assert field.config["custom_value"] is True


@pytest.mark.parametrize(
    "subentry_type", ["conversation", "ai_task_data", "stt", "tts"]
)
async def test_falls_back_to_free_text_when_provider_lists_nothing(
    hass: HomeAssistant,
    mock_init_component: None,
    mock_config_entry: MockConfigEntry,
    subentry_type: str,
) -> None:
    """An endpoint without /v1/models must still be configurable by hand."""
    result = await _model_step(hass, mock_config_entry, subentry_type, [])

    assert _field(result, CONF_CHAT_MODEL) is str


async def test_new_endpoint_starts_with_recommended_unticked(
    hass: HomeAssistant,
    mock_init_component: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ticked, the flow ends on the first step and never asks for a model."""
    with patch(DISCOVERY, return_value=PROVIDER_MODELS):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )

    assert _marker(result, CONF_RECOMMENDED).default() is False


async def test_a_non_openai_model_name_survives_the_flow(
    hass: HomeAssistant,
    mock_init_component: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The point of the fork: the stored model is the provider's, and none of
    upstream's OpenAI-specific model gates reject it."""
    with patch(DISCOVERY, return_value=PROVIDER_MODELS):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_NAME: "Sonnet via LiteLLM", CONF_RECOMMENDED: False},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_CHAT_MODEL: "claude-sonnet-4-6"}
        )
        # remaining steps take their defaults
        while result["type"] is FlowResultType.FORM:
            result = await hass.config_entries.subentries.async_configure(
                result["flow_id"], {}
            )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sonnet via LiteLLM"
    assert result["data"][CONF_CHAT_MODEL] == "claude-sonnet-4-6"
