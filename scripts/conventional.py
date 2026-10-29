"""Parse Conventional Commit messages and calculate semantic version bumps."""

from __future__ import annotations

import re

HEADER = re.compile(
    r"^(?P<type>[a-z][a-z0-9-]*)(?:\((?P<scope>[^\r\n()]+)\))?(?P<breaking>!)?: .+$"
)
WIP = re.compile(r"^wip(?:$|[\s:])", re.IGNORECASE)


def is_wip(message: str) -> bool:
    """Return whether a commit is explicitly marked as work in progress."""
    return WIP.match(message.strip()) is not None


def validate(message: str) -> str | None:
    """Return an error for an invalid message, or None for accepted messages."""
    subject = message.splitlines()[0].strip() if message.splitlines() else ""
    if is_wip(subject):
        return None
    if not HEADER.fullmatch(subject):
        return (
            "Expected Conventional Commit format: "
            "<type>[optional scope][!]: <description>; WIP messages are also allowed"
        )
    return None


def bump_level(message: str) -> int:
    """Return SemVer bump level: 0 none, 1 patch, 2 minor, 3 major."""
    lines = message.splitlines()
    subject = lines[0].strip() if lines else ""
    if not subject or is_wip(subject):
        return 0
    match = HEADER.fullmatch(subject)
    if not match:
        return 0
    if match.group("breaking") or any(
        line.startswith("BREAKING CHANGE:") for line in lines[1:]
    ):
        return 3
    if match.group("type") == "feat":
        return 2
    if match.group("type") in {"fix", "perf", "revert"}:
        return 1
    return 0


def next_version(version: str, level: int) -> str:
    """Apply a SemVer bump level to a plain x.y.z version."""
    match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version)
    if not match:
        raise ValueError(f"Unsupported version: {version}")
    major, minor, patch = map(int, match.groups())
    if level >= 3:
        return f"{major + 1}.0.0"
    if level == 2:
        return f"{major}.{minor + 1}.0"
    if level == 1:
        return f"{major}.{minor}.{patch + 1}"
    return version
