# Changelog

Versions match `custom_components/openai_compatible/manifest.json` and the `v*` release
tags. Earlier releases are described on their GitHub release pages.

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
