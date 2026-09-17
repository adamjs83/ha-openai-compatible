"""Tests for the OpenAI integration."""

from unittest.mock import AsyncMock

import httpx
from openai import AuthenticationError, RateLimitError
from openai.types.responses import (
    ResponseError,
    ResponseErrorEvent,
    ResponseStreamEvent,
)
from openai.types.responses.response import IncompleteDetails
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import conversation
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.intent import async_register_timer_handler
from custom_components.openai_compatible.const import (
    CONF_CHAT_MODEL,
    CONF_PRO_MODE,
    CONF_SERVICE_TIER,
    CONF_STORE_RESPONSES,
)
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from . import (
    create_function_tool_call_item,
    create_message_item,
    create_reasoning_item,
)

from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test entity properties."""
    state = hass.states.get("conversation.openai_conversation")
    assert state
    assert state.attributes["supported_features"] == 0

    hass.config_entries.async_update_subentry(
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        data={CONF_LLM_HASS_API: "assist"},
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)

    state = hass.states.get("conversation.openai_conversation")
    assert state
    assert (
        state.attributes["supported_features"]
        == conversation.ConversationEntityFeature.CONTROL
    )


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (
            RateLimitError(
                response=httpx.Response(status_code=429, request=""),
                body=None,
                message=None,
            ),
            "Rate limited or insufficient funds",
        ),
        (
            AuthenticationError(
                response=httpx.Response(status_code=401, request=""),
                body=None,
                message=None,
            ),
            "Error talking to OpenAI",
        ),
    ],
)
async def test_error_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    exception,
    message,
) -> None:
    """Test that we handle errors when calling completion API."""
    mock_create_stream.return_value = [exception]

    result = await conversation.async_converse(
        hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR, result
    assert result.response.speech["plain"]["speech"] == message, result.response.speech


@pytest.mark.parametrize(
    ("reason", "message"),
    [
        (
            "max_output_tokens",
            "max output tokens reached",
        ),
        (
            "content_filter",
            "content filter triggered",
        ),
        (
            None,
            "unknown reason",
        ),
    ],
)
async def test_incomplete_response(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    reason: str,
    message: str,
) -> None:
    """Test handling early model stop."""
    # Incomplete details received after some content is generated
    mock_create_stream.return_value = [
        (
            # Start message
            *create_message_item(
                id="msg_A",
                text=["Once upon", " a time, ", "there was "],
                output_index=0,
            ),
            # Length limit or content filter
            IncompleteDetails(reason=reason),
        )
    ]

    result = await conversation.async_converse(
        hass,
        "Please tell me a big story",
        "mock-conversation-id",
        Context(),
        agent_id="conversation.openai_conversation",
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR, result
    assert (
        result.response.speech["plain"]["speech"]
        == f"OpenAI response incomplete: {message}"
    ), result.response.speech

    # Incomplete details received before any content is generated
    mock_create_stream.return_value = [
        (
            # Start generating response
            *create_reasoning_item(id="rs_A", output_index=0),
            # Length limit or content filter
            IncompleteDetails(reason=reason),
        )
    ]

    result = await conversation.async_converse(
        hass,
        "please tell me a big story",
        "mock-conversation-id",
        Context(),
        agent_id="conversation.openai_conversation",
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR, result
    assert (
        result.response.speech["plain"]["speech"]
        == f"OpenAI response incomplete: {message}"
    ), result.response.speech


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            ResponseError(code="rate_limit_exceeded", message="Rate limit exceeded"),
            "OpenAI response failed: Rate limit exceeded",
        ),
        (
            ResponseErrorEvent(type="error", message="Some error", sequence_number=0),
            "OpenAI response error: Some error",
        ),
    ],
)
async def test_failed_response(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    error: ResponseError | ResponseErrorEvent,
    message: str,
) -> None:
    """Test handling failed and error responses."""
    mock_create_stream.return_value = [(error,)]

    result = await conversation.async_converse(
        hass,
        "next natural number please",
        "mock-conversation-id",
        Context(),
        agent_id="conversation.openai_conversation",
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR, result
    assert result.response.speech["plain"]["speech"] == message, result.response.speech


async def test_conversation_agent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test OpenAIAgent."""
    agent = conversation.get_agent_manager(hass).async_get_agent(
        mock_config_entry.entry_id
    )
    assert agent.supported_languages == "*"


@pytest.mark.parametrize(
    ("description", "messages"),
    [
        (
            "Test function call started with missing arguments",
            (
                *create_function_tool_call_item(
                    id="fc_1",
                    arguments=[],
                    call_id="call_call_1",
                    name="test_tool",
                    output_index=0,
                ),
                *create_message_item(id="msg_A", text="Cool", output_index=1),
            ),
        ),
        (
            "Test invalid JSON",
            (
                *create_function_tool_call_item(
                    id="fc_1",
                    arguments=['{"para'],
                    call_id="call_call_1",
                    name="test_tool",
                    output_index=0,
                ),
                *create_message_item(id="msg_A", text="Cool", output_index=1),
            ),
        ),
    ],
)
async def test_function_call_invalid(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    description: str,
    messages: tuple[ResponseStreamEvent],
) -> None:
    """Test function call containing invalid data."""
    mock_create_stream.return_value = [messages]

    with pytest.raises(ValueError):
        await conversation.async_converse(
            hass,
            "Please call the test function",
            "mock-conversation-id",
            Context(),
            agent_id="conversation.openai_conversation",
        )


async def test_assist_api_tools_conversion(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
    mock_create_stream,
) -> None:
    """Test that we are able to convert actual tools from Assist API."""
    for domain in (
        "calendar",
        "climate",
        "cover",
        "humidifier",
        "intent",
        "light",
        "media_player",
        "script",
        "shopping_list",
        "todo",
        "vacuum",
        "weather",
    ):
        assert await async_setup_component(hass, domain, {})
        hass.states.async_set(f"{domain}.test", "on")
        async_expose_entity(hass, "conversation", f"{domain}.test", True)

    async_register_timer_handler(hass, "test_device", lambda *args: None)

    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="Cool", output_index=0)
    ]

    await conversation.async_converse(
        hass,
        "hello",
        None,
        Context(),
        agent_id="conversation.openai_conversation",
        device_id="test_device",
    )

    tools = mock_create_stream.mock_calls[0][2]["tools"]
    assert tools

    for tool in tools:
        msg = (
            f"Invalid schema for function '{tool['name']}': schema must have type "
            "'object' and not have 'oneOf'/'anyOf'/'allOf'/"
            "'enum'/'not' at the top level."
        )
        assert tool["parameters"]["type"] == "object", msg
        for key in ("oneOf", "anyOf", "allOf", "enum", "not"):
            assert key not in tool["parameters"], msg


@pytest.mark.parametrize(
    "expected_store",
    [
        False,
        True,
    ],
)
async def test_store_responses_forwarded_for_conversation_agent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    expected_store: bool,
) -> None:
    """Test store_responses is forwarded for the conversation agent."""
    subentry = next(
        entry
        for entry in mock_config_entry.subentries.values()
        if entry.subentry_type == "conversation"
    )
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={**subentry.data, CONF_STORE_RESPONSES: expected_store},
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)

    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="Hello!", output_index=0)
    ]

    result = await conversation.async_converse(
        hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert mock_create_stream.call_args is not None
    assert mock_create_stream.call_args.kwargs["store"] is expected_store


async def test_flex_tier_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream,
) -> None:
    """Test retry with default tier if flex tier unavailable."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            **subentry.data,
            CONF_SERVICE_TIER: "flex",
        },
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)

    mock_create_stream.return_value = [
        RateLimitError(
            response=httpx.Response(
                status_code=429,
                request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
            ),
            body=None,
            message="Resource Unavailable",
        ),
        create_message_item(id="msg_A", text="How can I assist?", output_index=0),
    ]

    result = await conversation.async_converse(
        hass,
        "Hi!",
        None,
        Context(),
        agent_id="conversation.openai_conversation",
    )

    assert mock_create_stream.call_count == 2
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == "How can I assist?", (
        result.response.speech
    )
    assert mock_create_stream.mock_calls[0][2]["service_tier"] == "flex"
    assert mock_create_stream.mock_calls[1][2]["service_tier"] == "default"


@pytest.mark.parametrize(
    "subentry_options", [{CONF_CHAT_MODEL: "gpt-5.6-sol", CONF_PRO_MODE: True}]
)
async def test_model_args(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    snapshot: SnapshotAssertion,
    subentry_options: dict,
) -> None:
    """Test model arguments for various configuration."""

    subentry = next(
        entry
        for entry in mock_config_entry.subentries.values()
        if entry.subentry_type == "conversation"
    )
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data=subentry_options,
    )
    await hass.async_block_till_done()

    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="Hi!", output_index=0),
    ]

    result = await conversation.async_converse(
        hass,
        "Hello",
        None,
        Context(),
        agent_id="conversation.openai_conversation",
    )

    model_args = mock_create_stream.call_args.kwargs.copy()
    model_args.pop("input")
    assert model_args.pop("user") == result.conversation_id
    assert model_args == snapshot
