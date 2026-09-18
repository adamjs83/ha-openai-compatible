"""Model discovery for an OpenAI-compatible endpoint.

Upstream hardcodes OpenAI's model names as defaults and validates them
against lists of OpenAI models, which is useless against a proxy or a
self-hosted server serving entirely different names. This asks the endpoint
what it actually serves, so the config flow can offer a dropdown instead of
a free-text box the user has to get exactly right.

Kept separate from the vendored upstream files so re-syncing with
home-assistant/core never conflicts with it.
"""

from __future__ import annotations

from typing import Any

import openai

from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import LOGGER

DEFAULT_TIMEOUT = 10.0


async def async_fetch_model_ids(
    client: openai.AsyncOpenAI, *, timeout: float = DEFAULT_TIMEOUT
) -> list[str]:
    """Return the endpoint's model ids, sorted and de-duplicated.

    Returns an empty list if the endpoint cannot or will not list them. Model
    discovery is a convenience: an endpoint that serves /v1/responses but not
    /v1/models, or a key scoped so narrowly it cannot enumerate, must still be
    configurable by typing a model name in by hand.
    """
    try:
        # max_retries=0: the SDK otherwise retries with backoff, and this call
        # runs while the user waits on a config-flow dialog. Discovery is a
        # convenience with a free-text fallback, so one quick attempt is the
        # right trade -- retrying would just stall the form.
        page = await client.with_options(
            max_retries=0, timeout=timeout
        ).models.list()
    except openai.OpenAIError as err:
        LOGGER.debug("Could not list models: %s", err)
        return []

    return sorted({model.id for model in page.data if getattr(model, "id", None)})


def model_field(model_ids: list[str]) -> Any:
    """Return a schema field for choosing a model.

    A dropdown of what the endpoint advertises when that is known, otherwise a
    plain string field. The dropdown accepts a typed-in value too, since an
    endpoint may route a model it does not list (LiteLLM wildcard routes, for
    instance).
    """
    if not model_ids:
        return str

    return SelectSelector(
        SelectSelectorConfig(
            options=model_ids,
            custom_value=True,
            mode=SelectSelectorMode.DROPDOWN,
            sort=True,
        )
    )
