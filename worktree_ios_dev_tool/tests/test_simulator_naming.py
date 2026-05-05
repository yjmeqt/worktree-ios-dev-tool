"""Tests for label validation + reverse-parsing of simctl device names."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from worktree_ios_dev_tool.errors import UserError  # noqa: E402
from worktree_ios_dev_tool.simulator import (  # noqa: E402
    parse_managed_name,
    synth_managed_name,
    validate_label,
)


class ValidateLabelTests(unittest.TestCase):
    def test_accepts_alnum_underscore(self) -> None:
        validate_label("default")
        validate_label("peer_2")
        validate_label("ABC")

    def test_rejects_hyphen(self) -> None:
        with self.assertRaises(UserError):
            validate_label("with-dash")

    def test_rejects_empty(self) -> None:
        with self.assertRaises(UserError):
            validate_label("")

    def test_rejects_whitespace(self) -> None:
        with self.assertRaises(UserError):
            validate_label("ab cd")


class SynthNameTests(unittest.TestCase):
    def test_join(self) -> None:
        self.assertEqual(synth_managed_name("Pulse", "feat-auth", "default"),
                         "Pulse-feat-auth-default")


class ParseNameTests(unittest.TestCase):
    def test_simple(self) -> None:
        self.assertEqual(parse_managed_name("Pulse-main-default", prefix="Pulse"),
                         ("main", "default"))

    def test_basename_with_hyphen(self) -> None:
        self.assertEqual(parse_managed_name("Pulse-feat-auth-default", prefix="Pulse"),
                         ("feat-auth", "default"))

    def test_prefix_with_hyphen(self) -> None:
        self.assertEqual(parse_managed_name("My-App-feat-auth-peer", prefix="My-App"),
                         ("feat-auth", "peer"))

    def test_returns_none_when_prefix_mismatch(self) -> None:
        self.assertIsNone(parse_managed_name("Other-feat-default", prefix="Pulse"))

    def test_returns_none_when_no_label_segment(self) -> None:
        # exactly equal to "<prefix>-x" — only one trailing component, no
        # basename/label split possible.
        self.assertIsNone(parse_managed_name("Pulse-bare", prefix="Pulse"))


if __name__ == "__main__":
    unittest.main()
