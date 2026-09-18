# Provider genericity: audit and roadmap

This fork currently makes one thing configurable — the API base URL — and inherits
everything else from `homeassistant/components/openai_conversation`. That is enough to
reach an OpenAI-compatible endpoint, and not enough to behave correctly against one.

This document records what is still OpenAI-specific, what each item actually costs, and
the design decision that has to be made before most of it can be fixed. It is an audit,
not a plan of record: nothing here is scheduled.

Line references are against the tree at the time of writing; treat them as starting
points, not gospel.

## Why a proxy makes this hard to notice

A gateway such as LiteLLM can be configured to drop parameters the target provider does
not support (`drop_params`). With that on, an endpoint absorbs OpenAI-only parameters
silently and requests succeed — so the payload problem below never surfaces, while
options that do nothing look like options that work.

That cuts both ways, and it is the single most important thing to understand about
testing this integration:

- **A dropping proxy hides finding 1.** No error is ever raised, so passing tests
  against it say nothing about portability.
- **A dropping proxy makes finding 2 worse.** A parameter that is silently discarded
  turns a misconfigured option into a no-op rather than an error, with nothing in the UI
  or the log to indicate it had no effect.

A strict server (vLLM, llama.cpp, a minimal home-grown endpoint) is the honest test
target, because it will reject what it does not implement.

## 1. OpenAI-only parameters on every request

`entity.py`, in the `ResponseCreateParamsStreaming` construction at line 515:

| Parameter | Sent when | Line |
| --- | --- | --- |
| `service_tier` | always | 520 |
| `store` | always | 521 |
| `prompt_cache_retention: "24h"` | always, unless the model name matches `UNSUPPORTED_EXTENDED_CACHE_RETENTION_MODELS` | 563 |
| `reasoning`, `include: ["reasoning.encrypted_content"]` | model name starts with `o` or `gpt-5` | 525-544 |
| `text.verbosity` | model name starts with `gpt-5` | 555-557 |

`service_tier`, `store` and `prompt_cache_retention` are therefore sent to every
provider, whatever it is. A server that validates its input strictly returns 400; a
dropping proxy discards them and the request succeeds.

**Cost:** breaks strict servers outright. Invisible behind a dropping proxy.

## 2. Capability inferred from OpenAI model names

There are 23 `startswith(...)` model-name gates across the component
(`config_flow.py` 11, `entity.py` 9, `__init__.py` 2, `ai_task.py` 1), plus the
`UNSUPPORTED_*` lists in `const.py`, which enumerate OpenAI model names.

Against a third-party model string, every one of those checks is meaningless — and it
fails in both directions:

- **Options offered that the provider cannot honour.** The `UNSUPPORTED_*` lists contain
  only OpenAI names, so a name like `claude-sonnet-4-6` never matches one and the option
  is shown. Service tier ("Controls the cost and response time") is offered for every
  such model. Code interpreter and web search are OpenAI *hosted tools*, offered
  unconditionally, and almost no compatible server implements either.
- **Options withheld that the provider does support.** Reasoning effort, reasoning
  summary and verbosity are only offered when the name starts with `o` or `gpt-5`. Point
  an endpoint at a reasoning-capable model whose name does not look like OpenAI's and
  there is no way to set a reasoning effort at all — the field never renders. A dropping
  proxy cannot compensate for this one, because the parameter is never sent.

**Cost:** the config UI misrepresents the endpoint in both directions. This is the
finding to fix first: it is what a user sees, and a dropping proxy makes it silent
rather than loud.

## 3. OpenAI branding in entities and errors

- `manufacturer="OpenAI"` on every device (`entity.py:492`)
- `DEFAULT_CONVERSATION_NAME`, `DEFAULT_AI_TASK_NAME`, `DEFAULT_STT_NAME`,
  `DEFAULT_TTS_NAME` in `const.py` — "OpenAI Conversation", "OpenAI AI Task", …
- user-facing error text: `OpenAI response incomplete` (459), `OpenAI response failed`
  (473), `OpenAI response error` (475), `Error talking to OpenAI` (719-720)

**Cost:** cosmetic, but the errors are the ones a user reads while debugging their own
provider, which makes them actively misleading.

## 4. Stale upstream notices

- The `deprecated_generate_content` and `deprecated_generate_image` repair issues state
  the actions will be removed "in the 2026.9.0 release". That is Home Assistant core's
  schedule for its own integration, it has already passed, and this fork has made no
  such commitment.
- `organization_verification_required` is an OpenAI-platform-specific repair that
  directs the user to OpenAI's settings page — meaningless for any other provider.

**Cost:** informational, but wrong, and repair issues are prominent in the UI.

## The open design decision

The OpenAI API has no capability discovery: `GET /v1/models` returns ids, not feature
support. So "which options should this endpoint offer" cannot be answered by asking the
provider, and something has to stand in for it. The candidates:

1. **A per-entry capability toggle** — "this endpoint supports OpenAI-specific
   features", defaulted on when the host is `api.openai.com`. Explicit, one decision per
   provider, and wrong only if the user sets it wrong.
2. **Host detection alone** — infer from the base URL. No user burden; wrong for Azure
   or OpenAI reached through a proxy, which is a normal setup here.
3. **Per-endpoint feature checkboxes** — let each endpoint declare what to send. Most
   precise, most tedious, and it asks the user to know their provider's API surface.

The shape that was recommended, and not agreed: a portable payload by default, with
OpenAI extras behind option 1. Deciding this is the prerequisite for findings 1 and 2;
findings 3 and 4 are independent and can be done at any time.
