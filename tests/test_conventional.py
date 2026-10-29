from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from conventional import bump_level, next_version, validate


class ConventionalCommitTests(unittest.TestCase):
    def test_accepts_standard_commit_and_scope(self) -> None:
        self.assertIsNone(validate("feat(sensor): add weekly total"))
        self.assertIsNone(validate("fix!: prevent duplicate timer"))

    def test_rejects_non_conventional_subject(self) -> None:
        self.assertIsNotNone(validate("Add weekly total"))

    def test_wip_is_accepted_and_does_not_bump(self) -> None:
        self.assertIsNone(validate("WIP: add weekly total"))
        self.assertIsNone(validate("wip feat(sensor): draft"))
        self.assertEqual(bump_level("WIP: feat: draft"), 0)

    def test_maps_conventional_commits_to_semver(self) -> None:
        self.assertEqual(bump_level("feat(sensor): add weekly total"), 2)
        self.assertEqual(bump_level("fix: handle empty response"), 1)
        self.assertEqual(bump_level("docs: clarify setup"), 0)
        self.assertEqual(bump_level("fix!: change service contract"), 3)
        self.assertEqual(
            bump_level("docs: change config\n\nBREAKING CHANGE: rename option"), 3
        )

    def test_increments_and_resets_semver_components(self) -> None:
        self.assertEqual(next_version("0.4.1", 1), "0.4.2")
        self.assertEqual(next_version("0.4.1", 2), "0.5.0")
        self.assertEqual(next_version("0.4.1", 3), "1.0.0")


if __name__ == "__main__":
    unittest.main()
