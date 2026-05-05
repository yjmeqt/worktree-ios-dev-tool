"""Tests for the prefix-scan logic that drives ``sim cleanup``.

We don't drive the verb end-to-end (it depends on argparse + ui + the full
config); we test the pure helper :func:`sim.match_for_cleanup` which the
verb delegates to. That gives the verb body a thin shell over a tested
filter.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from worktree_ios_dev_tool.sim import match_for_cleanup  # noqa: E402


_FAKE = [
    {"name": "Pulse-feat-auth-default", "udid": "AAAA"},
    {"name": "Pulse-feat-auth-peer",    "udid": "BBBB"},
    {"name": "Pulse-main-default",      "udid": "CCCC"},
    {"name": "Pulse-feat-auth-extras",  "udid": "DDDD"},  # also matches
    {"name": "Other-feat-auth-default", "udid": "EEEE"},  # different prefix
    {"name": "Pulse-feat-auth",         "udid": "FFFF"},  # no label segment
]


class MatchForCleanupTests(unittest.TestCase):
    def test_matches_all_label_variants_for_basename(self) -> None:
        result = match_for_cleanup(_FAKE, prefix="Pulse", basename="feat-auth")
        names = {d["name"] for d in result}
        self.assertEqual(names, {
            "Pulse-feat-auth-default",
            "Pulse-feat-auth-peer",
            "Pulse-feat-auth-extras",
        })

    def test_excludes_other_basenames(self) -> None:
        result = match_for_cleanup(_FAKE, prefix="Pulse", basename="main")
        names = {d["name"] for d in result}
        self.assertEqual(names, {"Pulse-main-default"})

    def test_excludes_other_prefix(self) -> None:
        result = match_for_cleanup(_FAKE, prefix="Other", basename="feat-auth")
        names = {d["name"] for d in result}
        self.assertEqual(names, {"Other-feat-auth-default"})


if __name__ == "__main__":
    unittest.main()
