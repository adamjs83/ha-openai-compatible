#!/usr/bin/env python3
"""Generate translations/en.json from strings.json.

Home Assistant core builds each integration's translations/ directory from
strings.json as a release step, resolving the `[%key:...%]` references that
strings.json uses to avoid duplicating text. A vendored copy of a core
integration therefore ships strings.json but no translations/ -- and
homeassistant.helpers.translation only ever reads
`<integration>/translations/<lang>.json`, with no fallback to strings.json.
Without this file every label, description and error in the config flow
renders untranslated in the UI.

Re-run after syncing strings.json with upstream:

    python scripts/generate_translations.py

`common::` references resolve against the installed homeassistant package's
own strings.json, so the text matches what core would have produced for the
same HA version. Self-references (`component::openai_compatible::...`)
resolve against strings.json itself.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any

DOMAIN = "openai_compatible"
COMPONENT_DIR = Path(__file__).resolve().parent.parent / "custom_components" / DOMAIN
STRINGS = COMPONENT_DIR / "strings.json"
OUTPUT = COMPONENT_DIR / "translations" / "en.json"

RE_KEY = re.compile(r"\[%key:([^%\]]+)%\]")
MAX_PASSES = 10


def core_strings() -> dict[str, Any]:
    """Return the installed homeassistant package's strings.json."""
    import homeassistant

    path = Path(homeassistant.__file__).parent / "strings.json"
    if not path.is_file():
        raise SystemExit(f"core strings.json not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def lookup(data: dict[str, Any], parts: list[str], ref: str) -> str:
    """Walk a `::`-separated reference path, or fail loudly."""
    node: Any = data
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            raise SystemExit(f"unresolvable reference: {ref} (at '{part}')")
        node = node[part]
    if not isinstance(node, str):
        raise SystemExit(f"reference {ref} does not point at a string")
    return node


def resolve_one(ref: str, own: dict[str, Any], core: dict[str, Any]) -> str:
    """Resolve a single reference body to its text."""
    parts = ref.split("::")
    if parts[0] == "common":
        return lookup(core, parts, ref)
    if parts[0] == "component":
        if parts[1] != DOMAIN:
            # Only core itself can resolve another integration's strings; this
            # fork has no reference to one, and silently emitting the raw
            # marker would ship a broken label.
            raise SystemExit(f"reference to another integration: {ref}")
        return lookup(own, parts[2:], ref)
    raise SystemExit(f"unknown reference namespace: {ref}")


def substitute(node: Any, own: dict[str, Any], core: dict[str, Any]) -> Any:
    """Replace every `[%key:...%]` marker in a nested structure."""
    if isinstance(node, dict):
        return {k: substitute(v, own, core) for k, v in node.items()}
    if isinstance(node, list):
        return [substitute(v, own, core) for v in node]
    if isinstance(node, str):
        return RE_KEY.sub(lambda m: resolve_one(m.group(1), own, core), node)
    return node


def build() -> dict[str, Any]:
    """Return strings.json with all references resolved."""
    own = json.loads(STRINGS.read_text(encoding="utf-8"))
    core = core_strings()

    resolved = own
    for _ in range(MAX_PASSES):
        # A reference can point at a value that is itself a reference, so keep
        # substituting until the result stops changing.
        nxt = substitute(resolved, own, core)
        if nxt == resolved:
            break
        resolved = nxt
    else:
        raise SystemExit(f"references still unresolved after {MAX_PASSES} passes")

    leftover = RE_KEY.findall(json.dumps(resolved))
    if leftover:
        raise SystemExit(f"unresolved references remain: {sorted(set(leftover))}")
    return resolved


def main() -> int:
    """Write translations/en.json."""
    resolved = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(resolved, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUTPUT.relative_to(Path.cwd())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
