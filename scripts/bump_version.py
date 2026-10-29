"""Bump the integration version from Conventional Commits since the last tag."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conventional import bump_level, next_version

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components/clockify/manifest.json"
CHANGELOG = ROOT / "CHANGELOG.md"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> int:
    try:
        latest_tag = git("describe", "--tags", "--abbrev=0")
    except subprocess.CalledProcessError:
        print("No version tag found; create the initial v<manifest-version> tag first.")
        return 1

    log = git("log", "--no-merges", "--format=%B%x00", f"{latest_tag}..HEAD")
    messages = [message.strip() for message in log.split("\x00") if message.strip()]
    level = max((bump_level(message) for message in messages), default=0)
    if level == 0:
        print("No releasable Conventional Commits since the latest version tag.")
        return 0

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    old_version = manifest["version"]
    version = next_version(old_version, level)
    manifest["version"] = version
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    summaries = "\n".join(f"- {message.splitlines()[0]}" for message in messages if bump_level(message))
    existing = CHANGELOG.read_text(encoding="utf-8")
    CHANGELOG.write_text(
        f"# Changelog\n\n## {version}\n\n{summaries}\n\n"
        + existing.removeprefix("# Changelog\n\n"),
        encoding="utf-8",
    )
    print(f"{old_version} -> {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
