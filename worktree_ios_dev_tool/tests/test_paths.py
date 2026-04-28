# worktree_ios_dev_tool/tests/test_paths.py
"""Tests for worktree_ios_dev_tool.paths (DerivedData routing)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from worktree_ios_dev_tool.paths import (  # noqa: E402
    _filesystem_type,
    _is_on_local_filesystem,
    derived_data_dir,
    find_worktree_root_for_bootstrap,
    CONFIG_DIRNAME,
)


class FilesystemTypeTests(unittest.TestCase):
    def test_root_is_apfs_on_macos(self) -> None:
        result = _filesystem_type(Path("/"))
        if result is None:
            self.skipTest("mount(8) not available in this environment")
        self.assertEqual(result, "apfs")

    def test_returns_none_when_mount_fails(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            self.assertIsNone(_filesystem_type(Path("/")))

    def test_picks_longest_matching_mountpoint(self) -> None:
        fake_mount_output = (
            "/dev/disk1s1 on / (apfs, local, journaled)\n"
            "/dev/disk2 on /Volumes/My Shared Files "
            "(smbfs, nodev, nosuid, mounted by admin)\n"
        )

        class FakeProc:
            stdout = fake_mount_output

        with (
            patch("subprocess.run", return_value=FakeProc()),
            patch.object(Path, "exists", return_value=True),
        ):
            self.assertEqual(
                _filesystem_type(Path("/Volumes/My Shared Files/foo")),
                "smbfs",
            )


class IsLocalFilesystemTests(unittest.TestCase):
    def test_apfs_is_local(self) -> None:
        with patch("worktree_ios_dev_tool.paths._filesystem_type", return_value="apfs"):
            self.assertTrue(_is_on_local_filesystem(Path("/")))

    def test_smbfs_is_not_local(self) -> None:
        with patch("worktree_ios_dev_tool.paths._filesystem_type", return_value="smbfs"):
            self.assertFalse(_is_on_local_filesystem(Path("/x")))

    def test_unknown_fstype_is_treated_as_non_local(self) -> None:
        with patch("worktree_ios_dev_tool.paths._filesystem_type", return_value="weirdfs"):
            self.assertFalse(_is_on_local_filesystem(Path("/x")))

    def test_none_fstype_is_treated_as_non_local(self) -> None:
        with patch("worktree_ios_dev_tool.paths._filesystem_type", return_value=None):
            self.assertFalse(_is_on_local_filesystem(Path("/x")))


class DerivedDataDirTests(unittest.TestCase):
    def _config(self, root: Path) -> Path:
        """Fake config layout: <root>/worktree-ios-dev/config.toml."""
        cfg_dir = root / CONFIG_DIRNAME
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg = cfg_dir / "config.toml"
        cfg.touch()
        return cfg

    def test_local_filesystem_returns_in_tree_path(self) -> None:
        with patch("worktree_ios_dev_tool.paths._is_on_local_filesystem", return_value=True):
            with tempfile.TemporaryDirectory() as tmp:
                wt = Path(tmp) / "feat-x"
                wt.mkdir()
                cfg = self._config(wt)
                self.assertEqual(
                    derived_data_dir(cfg),
                    wt / CONFIG_DIRNAME / "derivedData",
                )

    def test_non_local_filesystem_routes_to_offload(self) -> None:
        with patch("worktree_ios_dev_tool.paths._is_on_local_filesystem", return_value=False):
            with tempfile.TemporaryDirectory() as tmp:
                wt = Path(tmp) / "feat-comment-scrolling"
                wt.mkdir()
                cfg = self._config(wt)
                self.assertEqual(
                    derived_data_dir(cfg),
                    Path("/tmp/worktree-ios-dev/feat-comment-scrolling/derivedData"),
                )

    def test_offload_keys_on_worktree_basename_not_full_path(self) -> None:
        with patch("worktree_ios_dev_tool.paths._is_on_local_filesystem", return_value=False):
            with tempfile.TemporaryDirectory() as tmp:
                a = Path(tmp) / "feat-A"
                b = Path(tmp) / "feat-B"
                a.mkdir()
                b.mkdir()
                self.assertNotEqual(
                    derived_data_dir(self._config(a)),
                    derived_data_dir(self._config(b)),
                )


class FindWorktreeRootForBootstrapTests(unittest.TestCase):
    def test_finds_git_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            subdir = root / "ios" / "src"
            subdir.mkdir(parents=True)
            result = find_worktree_root_for_bootstrap(start=subdir)
            self.assertEqual(result, root)

    def test_raises_user_error_when_no_git(self) -> None:
        from worktree_ios_dev_tool.errors import UserError
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(UserError):
                find_worktree_root_for_bootstrap(start=Path(tmp))


if __name__ == "__main__":
    unittest.main()
