"""The shipped translations/en.json must exist and match strings.json.

Home Assistant only reads translations/<lang>.json, so a stale or missing
en.json silently degrades every label in the config flow rather than failing
loudly. strings.json is the file that gets edited (and re-synced from core),
so this guards against the two drifting apart.
"""

import json

from scripts.generate_translations import OUTPUT, build


def test_en_json_exists() -> None:
    """A vendored core integration ships no translations/ dir of its own."""
    assert OUTPUT.is_file(), (
        f"{OUTPUT} is missing -- run: python scripts/generate_translations.py"
    )


def test_en_json_matches_strings() -> None:
    """en.json must be exactly what the generator produces from strings.json."""
    shipped = json.loads(OUTPUT.read_text(encoding="utf-8"))
    assert shipped == build(), (
        "translations/en.json is out of sync with strings.json -- run: "
        "python scripts/generate_translations.py"
    )


def test_no_unresolved_key_references_shipped() -> None:
    """A surviving [%key:...%] marker would render literally in the UI."""
    assert "[%key:" not in OUTPUT.read_text(encoding="utf-8")
