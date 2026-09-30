# Repository instructions

## Project

This is a public Home Assistant custom integration (`openai_compatible`) for OpenAI-compatible API endpoints. It adds a configurable base URL to a fork of Home Assistant core's `openai_conversation` integration. Provider entries can have conversation, AI Task, speech-to-text, and text-to-speech subentries.

The README covers installation, configuration, endpoint requirements, development, and releases. `docs/provider-genericity.md` audits remaining OpenAI-specific behavior and records an open design decision; it is not a scheduled plan. The vendored core revision is recorded in `custom_components/openai_compatible/UPSTREAM_COMMIT`. `hacs.json` sets the minimum Home Assistant version (2026.9.0); `manifest.json` carries the integration version. Development and CI use Python 3.14.

Production Home Assistant runs this integration: the `hassio` repo commits a copy at `hassio/custom_components/openai_compatible` (version 0.2.0, matching this repo at the time of writing). Change code here, then copy it into `hassio`; that copy reaches the live instance through the hassio deploy, which needs the owner's OK.

## Boundaries

- `origin` is a public GitHub repository. Any push to `main` publishes the code, not only a release tag. Do not push without the owner's explicit OK.
- Changes to a live Home Assistant installation, a configured API provider or host, or a published GitHub release/HACS download need the owner's explicit OK. Read-only inspection is fine. The documented HACS and manual installation paths can change live Home Assistant behavior.
- Keep the fork's configurable base URL and separate `openai_compatible` domain intact when syncing upstream code. Preserve config-entry migration, provider/subentry behavior, and the four entity types; tests cover these paths.
- Do not put secrets, tokens, passwords, or private keys in any file. Do not search for credentials. Base URLs must reject embedded credentials because URLs can appear in errors and logs; API keys belong in the config flow's key field.
- Never list or read the UNAS or `/nfs/media`.

## Working rules

- Install test dependencies with `pip install -r requirements_test.txt` under Python 3.14+, then run `pytest tests/ -v`. `pyproject.toml` configures pytest and Ruff, but no Ruff command is listed in CI.
- Keep `url_util.py` separate from vendored upstream files so upstream syncing remains manageable. When changing `strings.json`, regenerate `translations/en.json` with `python scripts/generate_translations.py`; the translation test checks that they match.
- The README documents release steps. `python scripts/release.py VERSION` requires a clean, current `main`; it changes the manifest, commits, and tags. Pushing the tag publishes through `.github/workflows/release.yaml`. Do not run the release script or push without the owner's explicit OK.

## Documentation that must be kept current

- Installation, provider setup, endpoint behavior, or compatibility changes: update `README.md`.
- Changes to remaining OpenAI-specific behavior or the capability design decision: update `docs/provider-genericity.md`.
- Changes to repo commands, boundaries, or layout: update this file; keep `CLAUDE.md` as the import stub.
- Minimum Home Assistant version changes: update `hacs.json` and the README.
- Upstream syncs: keep `UPSTREAM_COMMIT` accurate. User-facing string changes: update `strings.json` and regenerate `translations/en.json`.
- Release process or version behavior changes: update the README's Releases section and the manifest or workflow as applicable.

## Definition of done

- Run `pytest tests/ -v` for code or translation changes. CI also runs Hassfest and the HACS validation action on pushes and pull requests; check their results when available.
- Keep behavior and docs aligned, including the translation output and upstream revision when affected. For releases, the tag version and `manifest.json` version must match; the release workflow enforces this.

## Layout

- `custom_components/openai_compatible/`: integration entry point (`__init__.py`), config flow, four entity platforms, URL/model helpers, manifest, service definitions, and UI strings/translations.
- `tests/`: ported upstream regression tests and fork-specific tests; `tests/snapshots/` holds conversation snapshots.
- `scripts/generate_translations.py`: builds the shipped English translation. `scripts/release.py`: prepares a version commit and annotated tag.
- `.github/workflows/`: pytest, Hassfest/HACS validation, and tag-triggered GitHub release workflows.
- `docs/provider-genericity.md`: provider compatibility audit and open design decision.

## Owner to confirm

- Which API provider endpoints or hosts does the production Home Assistant installation use?
