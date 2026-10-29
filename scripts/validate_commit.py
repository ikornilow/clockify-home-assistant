"""Validate a Git commit message file."""

from __future__ import annotations

import sys
from pathlib import Path

from conventional import validate


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_commit.py <commit-message-file>", file=sys.stderr)
        return 2
    message = Path(sys.argv[1]).read_text(encoding="utf-8")
    error = validate(message)
    if error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
