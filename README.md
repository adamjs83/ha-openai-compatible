# OpenAI Compatible for Home Assistant

[![test](https://github.com/adamjs83/ha-openai-compatible/actions/workflows/test.yaml/badge.svg)](https://github.com/adamjs83/ha-openai-compatible/actions/workflows/test.yaml)
[![validate](https://github.com/adamjs83/ha-openai-compatible/actions/workflows/validate.yaml/badge.svg)](https://github.com/adamjs83/ha-openai-compatible/actions/workflows/validate.yaml)
[![HACS: custom](https://img.shields.io/badge/HACS-custom-41BDF5.svg)](https://hacs.xyz)

Home Assistant's built-in **OpenAI** integration, with one change that matters: the
**API base URL is configurable**. Point Home Assistant's conversation agent, AI Task,
speech-to-text and text-to-speech at any OpenAI-compatible endpoint — LiteLLM, vLLM,
OpenRouter, a gateway of your own — instead of only `api.openai.com`.

Everything else is upstream Home Assistant code, vendored unmodified, so behavior and
options match the core integration you already know.

## Why this exists

Core's `openai_conversation` hardcodes OpenAI's endpoint. If you run a proxy for cost
control, routing, key management or privacy, or you self-host models, there is no way to
tell the core integration about it. This fork adds a **Base URL** field to the config
flow and threads it to every client it creates.

## How it is organised

**One entry per server or provider**, and **one endpoint per model** underneath it.
Setup asks only for the connection; nothing is created on your behalf. You then add
endpoints yourself, picking the type and the model each time — so a single LiteLLM entry
can carry a conversation agent on one model, another on a second, and a TTS endpoint on
a third.

Each endpoint is one of four types, and each becomes its own Home Assistant entity:

- **Conversation agent** — an Assist conversation entity, with the LLM Assist API,
  tool calling, and the full upstream option set (model, temperature, top-p, max tokens,
  reasoning effort, verbosity, web search, code interpreter, service tier, …)
- **AI Task** — for `ai_task.generate_data` / image generation
- **Speech-to-text** — an STT entity
- **Text-to-speech** — a TTS entity, with speed control

Plus two actions on the entry itself: `openai_compatible.generate_content` and
`openai_compatible.generate_image`.

## Requirements

- Home Assistant **2026.9.0** or newer
- An OpenAI-compatible endpoint (see [Endpoint compatibility](#endpoint-compatibility))

## Installation

### HACS (custom repository)

1. HACS → ⋮ → **Custom repositories**
2. Add `https://github.com/adamjs83/ha-openai-compatible`, category **Integration**
3. Find **OpenAI Compatible** in HACS, download it, and restart Home Assistant
4. **Settings → Devices & services → Add integration → OpenAI Compatible**

### Manual

Copy `custom_components/openai_compatible/` into your Home Assistant
`config/custom_components/` directory and restart.

## Configuration

### 1. Add the provider

| Field | Notes |
| --- | --- |
| **Name** | Label for this provider, e.g. `LiteLLM`. Leave blank to use the endpoint's host. |
| **Base URL** | Full URL including any version path, e.g. `https://api.openai.com/v1`. Passed to the OpenAI SDK as-is. |
| **API key** | Optional — **leave blank** for an endpoint that does not authenticate. |

Submitting it checks the connection with `GET /v1/models` and creates the entry. No
entities are created yet, deliberately: guessing them would mean pointing STT and TTS at
OpenAI model names your provider probably does not serve.

You can add **several entries for the same server** — one per provider-side key, say.
Upstream refuses this as a duplicate; this fork does not.

### 2. Add endpoints for the models you want

On the entry, use **Add conversation agent** / **Add AI task** / **Add speech-to-text** /
**Add text-to-speech**. Each flow offers a **model dropdown populated from that
provider's own `GET /v1/models`**, read when you open the form, so it lists what is
actually available right then. The dropdown also accepts a typed-in name, for a provider
that routes models it does not advertise (LiteLLM wildcard routes, for instance), and
falls back to a plain text box if the endpoint will not list models at all.

Repeat per model. Name each endpoint something you will recognise in Assist — the
subentry title becomes the entity name.

### Base URL rules

- Only `http` and `https` are accepted; the URL must include a host.
- Whitespace and trailing slashes are stripped.
- **Include the version path** if your server expects one. Most do: `/v1`.
- Credentials embedded in the URL (`https://user:pass@host/v1`) are **rejected**. Put
  the token in the API key field — it is stored as a secret and kept out of logs, while
  a base URL is echoed back in error and log messages.
- Re-authenticating (rotating the API key) **keeps** your configured base URL.

### Empty API keys

Local endpoints often require no auth. Leave the API key blank and the integration sends
the placeholder `not-required` — the OpenAI SDK refuses to build a client with no key at
all, so something has to be sent, and servers that ignore auth ignore it.

### Endpoint examples

| Server | Typical base URL |
| --- | --- |
| OpenAI | `https://api.openai.com/v1` |
| LiteLLM | `http://litellm.local:4000/v1` |
| vLLM | `http://vllm.local:8000/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |
| Azure OpenAI (via a proxy) | your proxy's URL |

## Endpoint compatibility

This is the important caveat. Upstream uses OpenAI's **Responses API**, not Chat
Completions, so a server that only implements `/v1/chat/completions` **will not work**
for conversation or AI Task.

| Feature | Endpoint the server must implement |
| --- | --- |
| Setup / connection test | `GET /v1/models` |
| Conversation, AI Task | `POST /v1/responses` |
| Text-to-speech | `POST /v1/audio/speech` |
| Speech-to-text | `POST /v1/audio/transcriptions` |
| `generate_image` action | `POST /v1/images/generations` |

You only need the endpoints for the subentries you actually add. Check your server's
docs for Responses API support before filing a bug — LiteLLM and vLLM have it in recent
versions; several popular local servers still do not.

### Model names

Pick from the dropdown and this mostly takes care of itself. Two upstream behaviours to
know about anyway:

- The fallback defaults are OpenAI's (`gpt-4o-mini`, `gpt-4o-mini-tts`,
  `gpt-4o-mini-transcribe`), used only if you never choose a model. A new endpoint starts
  with **Recommended settings** unticked so the flow always asks.
- Upstream's lists of models that don't support web search, image generation, reasoning
  effort and so on are keyed to OpenAI names, so they won't match a third-party model
  string. Options are offered based on those name patterns, and the endpoint's own error
  is what you'll see if you ask for something it can't do.

## Relationship to Home Assistant core

`custom_components/openai_compatible/` is derived from
`homeassistant/components/openai_conversation/` at core tag **2026.9.2**
(commit recorded in [`UPSTREAM_COMMIT`](custom_components/openai_compatible/UPSTREAM_COMMIT)),
with the domain renamed to `openai_compatible` and the base URL made configurable.

Base-URL handling lives in its own module,
[`url_util.py`](custom_components/openai_compatible/url_util.py), deliberately separate
from the vendored files so re-syncing with core stays a clean merge.

Installing this alongside core's OpenAI integration is fine — different domain, separate
config entries. This is **not** an official Home Assistant integration and is not
affiliated with or endorsed by OpenAI.

## Development

Requires Python 3.14+ (Home Assistant 2026.9's floor).

```bash
pip install -r requirements_test.txt
pytest tests/ -v
```

The suite is core's `openai_conversation` test suite, ported as a regression net, plus
tests for the base-URL behavior this fork adds.

## Releases

HACS falls back to serving the default branch when a repository has no releases, so
every download looks identical and there is no way to tell what is installed. Tagged
releases fix that, and Home Assistant shows `manifest.json`'s version on the
integration page.

Versions are `0.x` while the config entry shape is still changing; `1.0.0` when it
settles.

To cut one:

```bash
python scripts/release.py 0.2.0
git push origin main --follow-tags
```

The script bumps `manifest.json`, commits, and creates the annotated tag `v0.2.0`. It
deliberately does not push — pushing the tag is what publishes. That triggers
[`release.yaml`](.github/workflows/release.yaml), which refuses to publish if the tag
and the manifest version disagree (HACS reads the tag, HA reads the manifest; when they
drift you install "v0.2.0" and it reports 0.1.0) and then creates the GitHub release.

## License

[Apache-2.0](LICENSE), inherited from Home Assistant core. See [NOTICE](NOTICE) for
attribution.
