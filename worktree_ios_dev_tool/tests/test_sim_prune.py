"""Tests for the orphan-detection helper that drives ``sim prune``."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from worktree_ios_dev_tool.sim import find_orphans  # noqa: E402


_DEVICES = [
    {"name": "Pulse-main-default",     "udid": "AAAA"},
    {"name": "Pulse-feat-auth-peer",   "udid": "BBBB"},
    {"name": "Pulse-old-branch-default", "udid": "CCCC"},   # orphan
    {"name": "Other-thing-default",    "udid": "DDDD"},     # not managed
    {"name": "Pulse-malformed",        "udid": "EEEE"},     # no label segment
]


class FindOrphansTests(unittest.TestCase):
    def test_basenames_in_set_are_not_orphans(self) -> None:
        live = {"main", "feat-auth"}
        orphans = find_orphans(_DEVICES, prefix="Pulse", live_basenames=live)
        names = {d["name"] for d, _, _ in orphans}
        self.assertEqual(names, {"Pulse-old-branch-default"})

    def test_empty_live_set_makes_everything_orphan(self) -> None:
        orphans = find_orphans(_DEVICES, prefix="Pulse", live_basenames=set())
        names = {d["name"] for d, _, _ in orphans}
        self.assertEqual(names, {
            "Pulse-main-default",
            "Pulse-feat-auth-peer",
            "Pulse-old-branch-default",
        })

    def test_returns_basename_and_label_alongside_device(self) -> None:
        orphans = find_orphans(_DEVICES, prefix="Pulse", live_basenames=set())
        as_map = {d["name"]: (b, l) for d, b, l in orphans}
        self.assertEqual(as_map["Pulse-feat-auth-peer"], ("feat-auth", "peer"))


if __name__ == "__main__":
    unittest.main()
