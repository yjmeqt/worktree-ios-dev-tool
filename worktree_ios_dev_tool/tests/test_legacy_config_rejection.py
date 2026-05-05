"""Tests that a worktree with only the legacy config.toml triggers a hard
UserError listing the manual migration steps."""
from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from worktree_ios_dev_tool.errors import UserError  # noqa: E402
from worktree_ios_dev_tool.paths import find_project_toml  # noqa: E402


class LegacyConfigRejectionTests(unittest.TestCase):
    def test_legacy_only_raises_with_migration_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wt = Path(tmp) / "feat-x"
            (wt / "worktree-ios-dev").mkdir(parents=True)
            (wt / "worktree-ios-dev" / "config.toml").write_text(textwrap.dedent("""
                [project]
                path = "ios/Pulse.xcodeproj"
                scheme = "Pulse"
            """))
            with self.assertRaises(UserError) as cm:
                find_project_toml(start=wt)
            msg = str(cm.exception)
            self.assertIn("legacy config.toml", msg)
            self.assertIn("proj init", msg)
            self.assertIn("sim pick", msg)


if __name__ == "__main__":
    unittest.main()
