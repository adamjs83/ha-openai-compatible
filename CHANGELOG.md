# Changelog

Versions match `custom_components/openai_compatible/manifest.json` and the `v*` release
tags. Earlier releases are described on their GitHub release pages.

## 0.2.3 — unreleased

### Fixed

- A reply cut off at max tokens through LiteLLM (Anthropic and other non-OpenAI models)
  now raises "OpenAI response incomplete". LiteLLM reports the cut-off as a completed
  response with status `incomplete`, which was taken as a success: AI Task returned an
  empty string, or a cut-off JSON reply failed as "Error with OpenAI structured
  response", and a conversation showed the partial text.
- AI Task raises "The model returned no text" when a reply has no text (a thinking model
  that answered with reasoning only), instead of returning an empty string or a JSON
  parse error.

## 0.2.2 — 2026-11-18

### Fixed

- Temperature and top-p are no longer sent unless set away from their defaults (1.0).
  A gateway alias for a reasoning model (for example LiteLLM `openai-mid`) failed with
  "Unsupported parameter: 'top_p' is not supported with this model", because only
  model names starting with `gpt-5` were treated as reasoning models.
- Structured AI Task output (`ai_task.generate_data` with `structure`) works with
  Anthropic models through LiteLLM. The schema no longer carries a non-standard
  `strict` key on its objects, which Anthropic rejected ("For 'object' type, property
  'strict' is not supported"); strict mode is now requested on the response format,
  where OpenAI reads it.
