"""Test AI Task platform of OpenAI Conversation integration."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from openai import PermissionDeniedError
import pytest
import voluptuous as vol

from homeassistant.components import ai_task, media_source
from custom_components.openai_compatible import DOMAIN
from custom_components.openai_compatible.const import CONF_STORE_RESPONSES
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir, selector

from . import (
    LITELLM_COMPLETED_INCOMPLETE,
    create_image_gen_call_item,
    create_message_item,
    create_reasoning_item,
)

from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize("expected_store", [False, True])
async def test_generate_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
    expected_store: bool,
) -> None:
    """Test AI Task data generation."""
    entity_id = "ai_task.openai_ai_task"

    # Ensure entity is linked to the subentry
    entity_entry = entity_registry.async_get(entity_id)
    ai_task_entry = next(
        iter(
            entry
            for entry in mock_config_entry.subentries.values()
            if entry.subentry_type == "ai_task_data"
        )
    )
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        ai_task_entry,
        data={**ai_task_entry.data, CONF_STORE_RESPONSES: expected_store},
    )
    await hass.async_block_till_done()
    assert entity_entry is not None
    assert entity_entry.config_entry_id == mock_config_entry.entry_id
    assert entity_entry.config_subentry_id == ai_task_entry.subentry_id

    # Mock the OpenAI response stream
    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="The test data", output_index=0)
    ]

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id=entity_id,
        instructions="Generate test data",
    )

    assert result.data == "The test data"
    assert mock_create_stream.call_args is not None
    assert mock_create_stream.call_args.kwargs["store"] is expected_store


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_structured_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task structured data generation."""
    # Mock the OpenAI response stream with JSON data
    mock_create_stream.return_value = [
        create_message_item(
            id="msg_A", text='{"characters": ["Mario", "Luigi"]}', output_index=0
        )
    ]

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id="ai_task.openai_ai_task",
        instructions="Generate test data",
        structure=vol.Schema(
            {
                vol.Required("characters"): selector.selector(
                    {
                        "text": {
                            "multiple": True,
                        }
                    }
                )
            },
        ),
    )

    assert result.data == {"characters": ["Mario", "Luigi"]}

    text_format = mock_create_stream.call_args.kwargs["text"]["format"]
    # Strict mode is requested on the format (OpenAI's switch), not inside the
    # JSON schema: Anthropic via LiteLLM rejects `strict` on an object schema.
    assert text_format["strict"] is True

    def _objects(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                yield node
            for value in node.values():
                yield from _objects(value)
        elif isinstance(node, list):
            for value in node:
                yield from _objects(value)

    objects = list(_objects(text_format["schema"]))
    assert objects
    for obj in objects:
        assert "strict" not in obj
        assert obj["additionalProperties"] is False


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_invalid_structured_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task with invalid JSON response."""
    # Mock the OpenAI response stream with invalid JSON
    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="INVALID JSON RESPONSE", output_index=0)
    ]

    with pytest.raises(
        HomeAssistantError, match="Error with OpenAI structured response"
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.openai_ai_task",
            instructions="Generate test data",
            structure=vol.Schema(
                {
                    vol.Required("characters"): selector.selector(
                        {
                            "text": {
                                "multiple": True,
                            }
                        }
                    )
                },
            ),
        )


GRILL_STRUCTURE = vol.Schema(
    {
        vol.Optional("food"): selector.selector({"text": {}}),
        vol.Optional("eta_minutes"): selector.selector({"number": {}}),
        vol.Optional("stalled"): selector.selector({"boolean": {}}),
    }
)


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize("structure", [None, GRILL_STRUCTURE])
async def test_generate_data_thinking_cut_off_by_litellm(
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
    structure: vol.Schema | None,
) -> None:
    """A thinking model that hits max tokens before writing text raises.

    LiteLLM ends such a reply with response.completed, status "incomplete".
    """
    mock_create_stream.return_value = [
        [
            *create_reasoning_item(
                id="rs_A", output_index=0, reasoning_summary="Thinking hard"
            ),
            LITELLM_COMPLETED_INCOMPLETE,
        ]
    ]

    with pytest.raises(HomeAssistantError, match="response incomplete"):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.openai_ai_task",
            instructions="Generate test data",
            structure=structure,
        )


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_structured_data_cut_off_by_litellm(
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
) -> None:
    """Cut-off JSON is reported as an incomplete reply, never parsed."""
    mock_create_stream.return_value = [
        [
            *create_message_item(id="msg_A", text='{"food": "bri', output_index=0),
            LITELLM_COMPLETED_INCOMPLETE,
        ]
    ]

    with pytest.raises(HomeAssistantError, match="response incomplete"):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.openai_ai_task",
            instructions="Generate test data",
            structure=GRILL_STRUCTURE,
        )


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize("structure", [None, GRILL_STRUCTURE])
async def test_generate_data_no_text(
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
    structure: vol.Schema | None,
) -> None:
    """A completed reply with no text (content None) raises a clear error."""
    mock_create_stream.return_value = [
        create_reasoning_item(id="rs_A", output_index=0, reasoning_summary="Hmm")
    ]

    with pytest.raises(HomeAssistantError, match="returned no text"):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.openai_ai_task",
            instructions="Generate test data",
            structure=structure,
        )


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_structured_data_after_thinking(
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
) -> None:
    """Thinking then JSON (Claude via LiteLLM) parses; optional fields are nullable."""
    mock_create_stream.return_value = [
        [
            *create_reasoning_item(id="rs_A", output_index=0, reasoning_summary="Hm"),
            *create_message_item(
                id="msg_A",
                text='{"food": "brisket", "eta_minutes": null, "stalled": true}',
                output_index=1,
            ),
        ]
    ]

    result = await ai_task.async_generate_data(
        hass,
        task_name="Grill probe review",
        entity_id="ai_task.openai_ai_task",
        instructions="Review the probe",
        structure=GRILL_STRUCTURE,
    )

    assert result.data == {"food": "brisket", "eta_minutes": None, "stalled": True}
    text_format = mock_create_stream.call_args.kwargs["text"]["format"]
    assert text_format["name"] == "grill_probe_review"
    schema = text_format["schema"]
    assert schema["additionalProperties"] is False
    assert sorted(schema["required"]) == ["eta_minutes", "food", "stalled"]
    assert schema["properties"]["eta_minutes"]["type"] == ["number", "null"]
    assert schema["properties"]["stalled"]["type"] == ["boolean", "null"]


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_data_with_attachments(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task data generation with attachments."""
    entity_id = "ai_task.openai_ai_task"

    # Mock the OpenAI response stream
    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="Hi there!", output_index=0)
    ]

    # Test with attachments
    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            side_effect=[
                media_source.PlayMedia(
                    url="http://example.com/doorbell_snapshot.jpg",
                    mime_type="image/jpeg",
                    path=Path("doorbell_snapshot.jpg"),
                ),
                media_source.PlayMedia(
                    url="http://example.com/context.pdf",
                    mime_type="application/pdf",
                    path=Path("context.pdf"),
                ),
            ],
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "custom_components.openai_compatible.entity.guess_file_type",
            return_value=("image/jpeg", None),
        ),
        patch("pathlib.Path.read_bytes", return_value=b"fake_image_data"),
    ):
        result = await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=entity_id,
            instructions="Test prompt",
            attachments=[
                {"media_content_id": "media-source://media/doorbell_snapshot.jpg"},
                {"media_content_id": "media-source://media/context.pdf"},
            ],
        )

    assert result.data == "Hi there!"

    # Verify that the create stream was called with the correct parameters
    # The last call should have the user message with attachments
    call_args = mock_create_stream.call_args
    assert call_args is not None

    # Check that the input includes the attachments
    input_messages = call_args[1]["input"]
    assert len(input_messages) > 0

    # Find the user message with attachments
    user_message_with_attachments = input_messages[-2]

    assert user_message_with_attachments is not None
    assert isinstance(user_message_with_attachments["content"], list)
    assert len(user_message_with_attachments["content"]) == 3  # Text + attachments
    assert user_message_with_attachments["content"] == [
        {"type": "input_text", "text": "Test prompt"},
        {
            "detail": "auto",
            "image_url": "data:image/jpeg;base64,ZmFrZV9pbWFnZV9kYXRh",
            "type": "input_image",
        },
        {
            "filename": "context.pdf",
            "file_data": "data:application/pdf;base64,ZmFrZV9pbWFnZV9kYXRh",
            "type": "input_file",
        },
    ]


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.freeze_time("2025-06-14 22:59:00")
@pytest.mark.parametrize("configured_store", [False, True])
@pytest.mark.parametrize(
    ("image_model", "input_fidelity_present"),
    [
        ("gpt-image-2", False),
        ("gpt-image-1.5", True),
        ("gpt-image-1", True),
        ("gpt-image-1-mini", False),
    ],
)
async def test_generate_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    image_model: str,
    input_fidelity_present: bool,
    configured_store: bool,
) -> None:
    """Test AI Task image generation."""
    entity_id = "ai_task.openai_ai_task"

    # Ensure entity is linked to the subentry
    entity_entry = entity_registry.async_get(entity_id)
    ai_task_entry = next(
        iter(
            entry
            for entry in mock_config_entry.subentries.values()
            if entry.subentry_type == "ai_task_data"
        )
    )
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        ai_task_entry,
        data={
            **ai_task_entry.data,
            "image_model": image_model,
            CONF_STORE_RESPONSES: configured_store,
        },
    )
    await hass.async_block_till_done()
    assert entity_entry is not None
    assert entity_entry.config_entry_id == mock_config_entry.entry_id
    assert entity_entry.config_subentry_id == ai_task_entry.subentry_id

    # Mock the OpenAI response stream
    mock_create_stream.return_value = [
        (
            *create_reasoning_item(
                id="rs_A",
                output_index=0,
                reasoning_summary=[["The user asks me to generate an image"]],
            ),
            *create_image_gen_call_item(id="ig_A", output_index=1),
            *create_message_item(id="msg_A", text="", output_index=2),
        )
    ]

    with patch.object(
        media_source.local_source.LocalSource,
        "async_upload_media",
        return_value="media-source://ai_task/image/2025-06-14_155900_test_task.png",
    ) as mock_upload_media:
        result = await ai_task.async_generate_image(
            hass,
            task_name="Test Task",
            entity_id="ai_task.openai_ai_task",
            instructions="Generate test image",
        )

    assert result["height"] == 1024
    assert result["width"] == 1536
    assert result["revised_prompt"] == "Mock revised prompt."
    assert result["mime_type"] == "image/png"
    assert result["model"] == image_model

    mock_upload_media.assert_called_once()
    assert mock_create_stream.call_args is not None
    assert mock_create_stream.call_args.kwargs["store"] is True
    image_tool = next(
        iter(
            tool
            for tool in mock_create_stream.call_args.kwargs["tools"]
            if tool["type"] == "image_generation"
        ),
    )
    assert ("input_fidelity" in image_tool) == input_fidelity_present
    image_data = mock_upload_media.call_args[0][1]
    assert image_data.file.getvalue() == b"A"
    assert image_data.content_type == "image/png"
    assert image_data.filename == "2025-06-14_155900_test_task.png"

    assert (
        issue_registry.async_get_issue(DOMAIN, "organization_verification_required")
        is None
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_repair_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that repair issue is raised when verification is required."""
    with (
        patch(
            "openai.resources.responses.AsyncResponses.create",
            side_effect=PermissionDeniedError(
                response=httpx.Response(
                    status_code=403, request=httpx.Request(method="GET", url="")
                ),
                body=None,
                message="Please click on Verify Organization.",
            ),
        ),
        pytest.raises(HomeAssistantError, match="Error talking to OpenAI"),
    ):
        await ai_task.async_generate_image(
            hass,
            task_name="Test Task",
            entity_id="ai_task.openai_ai_task",
            instructions="Generate test image",
        )

    assert issue_registry.async_get_issue(DOMAIN, "organization_verification_required")
