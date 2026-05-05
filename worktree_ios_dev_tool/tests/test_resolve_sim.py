"""Tests for the single/multi-simulator resolution helper."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from worktree_ios_dev_tool.config import (  # noqa: E402
    Config,
    ProjectConfig,
    SimulatorEntry,
    resolve_sim,
)
from worktree_ios_dev_tool.errors import UserError  # noqa: E402


def _cfg(simulators: dict[str, SimulatorEntry]) -> Config:
    return Config(
        config_path=Path("/tmp/x/worktree-ios-dev/project.toml"),
        worktree_root=Path("/tmp/x"),
        derived_data=Path("/tmp/x/worktree-ios-dev/derivedData"),
        project=ProjectConfig(
            path=Path("/tmp/x/ios/App.xcodeproj"),
            scheme="App",
            configuration="Debug",
            simulator_prefix="App",
        ),
        simulators=simulators,
        packages_root=Path("/tmp/x/ios/Packages"),
    )


def _entry(name: str, udid: str = "U") -> SimulatorEntry:
    return SimulatorEntry(name=name, udid=udid, device="iPhone 17 Pro", runtime="iOS 18.2")


class ResolveSimTests(unittest.TestCase):
    def test_no_simulators_errors(self) -> None:
        with self.assertRaises(UserError) as cm:
            resolve_sim(_cfg({}), label=None)
        self.assertIn("sim pick", str(cm.exception))

    def test_single_sim_auto_picks(self) -> None:
        only = _entry("App-feat-default")
        result = resolve_sim(_cfg({"default": only}), label=None)
        self.assertIs(result, only)

    def test_multi_sim_without_label_errors(self) -> None:
        cfg = _cfg({
            "default": _entry("App-feat-default"),
            "peer": _entry("App-feat-peer"),
        })
        with self.assertRaises(UserError) as cm:
            resolve_sim(cfg, label=None)
        self.assertIn("--sim", str(cm.exception))
        self.assertIn("default", str(cm.exception))
        self.assertIn("peer", str(cm.exception))

    def test_explicit_label_resolves(self) -> None:
        peer = _entry("App-feat-peer")
        cfg = _cfg({"default": _entry("App-feat-default"), "peer": peer})
        self.assertIs(resolve_sim(cfg, label="peer"), peer)

    def test_unknown_label_errors(self) -> None:
        cfg = _cfg({"default": _entry("App-feat-default")})
        with self.assertRaises(UserError) as cm:
            resolve_sim(cfg, label="missing")
        self.assertIn("missing", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
