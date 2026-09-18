#!/usr/bin/env python3
"""Cut a release: bump manifest.json, commit, tag.

HACS shows the latest releases of a repository and, when there are none,
silently serves the default branch instead -- so every download looks
identical and there is no way to tell which code is installed. Home Assistant
reads the installed version from manifest.json. Those two have to agree, which
is what this script (and the check in .github/workflows/release.yaml) is for.

    python scripts/release.py 0.2.0

It stops short of pushing. Pushing the tag is what publishes the release, so
that stays an explicit step:

    git push origin main --follow-tags
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "custom_components" / "openai_compatible" / "manifest.json"

# Same shape AwesomeVersion accepts and HACS sorts by, kept deliberately
# strict: a stray "v" or a trailing ".0.0" is how tag/manifest drift starts.
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+([ab]\d+|rc\d+)?$")


def run(*args: str, capture: bool = False) -> str:
    """Run a git command, failing loudly."""
    result = subprocess.run(
        args, cwd=REPO, text=True, capture_output=capture, check=True
    )
    return (result.stdout or "").strip() if capture else ""


def check_clean_checkout() -> None:
    """Refuse to release from a dirty or diverged checkout."""
    if run("git", "status", "--porcelain", capture=True):
        raise SystemExit("working tree is not clean; commit or stash first")

    branch = run("git", "rev-parse", "--abbrev-ref", "HEAD", capture=True)
    if branch != "main":
        raise SystemExit(f"releases are cut from main, not {branch}")

    run("git", "fetch", "--quiet", "origin", "main")
    local = run("git", "rev-parse", "main", capture=True)
    remote = run("git", "rev-parse", "origin/main", capture=True)
    if local != remote:
        raise SystemExit("main and origin/main differ; push or pull first")


def main() -> int:
    """Bump, commit and tag."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="new version, e.g. 0.2.0")
    args = parser.parse_args()
    version = args.version.removeprefix("v")

    if not VERSION_RE.match(version):
        raise SystemExit(f"'{version}' is not a MAJOR.MINOR.PATCH version")

    tag = f"v{version}"
    existing = run("git", "tag", "--list", tag, capture=True)
    if existing:
        raise SystemExit(f"tag {tag} already exists")

    check_clean_checkout()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    previous = manifest["version"]
    if previous == version:
        raise SystemExit(f"manifest.json is already {version}")

    manifest["version"] = version
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    run("git", "add", str(MANIFEST.relative_to(REPO)))
    run("git", "commit", "--quiet", "-m", f"chore: release {tag}")
    run("git", "tag", "--annotate", tag, "-m", tag)

    print(f"{previous} -> {version}, committed and tagged {tag}")
    print("publish it with:  git push origin main --follow-tags")
    return 0


if __name__ == "__main__":
    sys.exit(main())
