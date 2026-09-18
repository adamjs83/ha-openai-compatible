"""manifest.json's version is what HACS and Home Assistant report."""

import json
from pathlib import Path

from awesomeversion import AwesomeVersion
import pytest

MANIFEST = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "openai_compatible"
    / "manifest.json"
)


@pytest.fixture(name="manifest")
def manifest_fixture() -> dict:
    """Return the integration manifest."""
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_version_is_present_and_parseable(manifest: dict) -> None:
    """HACS validates the version with AwesomeVersion; so do we, locally."""
    version = manifest.get("version")
    assert version, "manifest.json needs a version for HACS to install it"
    assert AwesomeVersion(version).valid


def test_version_matches_the_release_script_format(manifest: dict) -> None:
    """Keep the manifest in the shape scripts/release.py will accept, so a
    release never fails on the version string itself."""
    from scripts.release import VERSION_RE

    assert VERSION_RE.match(manifest["version"]), (
        f"{manifest['version']} is not MAJOR.MINOR.PATCH; "
        "scripts/release.py and the release workflow expect that shape"
    )
