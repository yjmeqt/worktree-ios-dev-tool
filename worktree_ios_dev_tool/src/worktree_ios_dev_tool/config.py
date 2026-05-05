# worktree_ios_dev_tool/src/worktree_ios_dev_tool/config.py
"""TOML read + schema validation. Writes via tomlkit to preserve comments."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomlkit

from .errors import UserError
from .paths import config_dir, derived_data_dir, worktree_root


@dataclass(frozen=True)
class ProjectConfig:
    path: Path             # absolute
    scheme: str
    configuration: str
    simulator_prefix: str | None = None


@dataclass(frozen=True)
class SimulatorEntry:
    """One configured simulator under [simulators.<label>] in simulator.toml.

    Attributes:
        name:    The simctl device name. Always synthesized as
                 ``<simulator_prefix>-<worktree_basename>-<label>``; never hand-edit.
        udid:    The simctl-assigned UUID; the source of truth for routing
                 build/test/run destinations.
        device:  Apple device-type display name (e.g. "iPhone 17 Pro").
        runtime: Apple runtime display name (e.g. "iOS 18.2").
    """
    name: str
    udid: str
    device: str
    runtime: str


# Temporary alias for backward compatibility; to be removed in a later task.
SimulatorConfig = SimulatorEntry


@dataclass(frozen=True)
class PackageOverride:
    scheme: str | None = None


@dataclass(frozen=True)
class Config:
    config_path: Path
    worktree_root: Path
    derived_data: Path
    project: ProjectConfig
    simulator: SimulatorEntry | None
    packages_root: Path
    package_overrides: dict[str, PackageOverride] = field(default_factory=dict)
    extras_xcodebuild_flags: list[str] = field(default_factory=list)


_ALLOWED_TOP_LEVEL = {"project", "simulator", "packages_root", "packages", "extras"}
_ALLOWED_PROJECT = {"path", "scheme", "configuration", "simulator_prefix"}
_ALLOWED_SIMULATOR = {"name", "udid", "device", "runtime"}
_ALLOWED_PACKAGES_ROOT = {"path"}
_ALLOWED_PACKAGE = {"scheme"}
_ALLOWED_EXTRAS = {"xcodebuild_flags"}


def _require_keys(table_name: str, table: dict[str, Any], allowed: set[str]) -> None:
    extra = set(table) - allowed
    if extra:
        raise UserError(
            f"Unknown key(s) in [{table_name}]: {sorted(extra)}. "
            f"Allowed: {sorted(allowed)}."
        )


def load(config_path: Path) -> Config:
    """Parse and validate config.toml. Raises UserError on schema violations."""
    with config_path.open("rb") as fh:
        data = tomllib.load(fh)

    _require_keys("<root>", data, _ALLOWED_TOP_LEVEL)

    if "project" not in data:
        raise UserError(
            f"Missing [project] section in {config_path}. "
            f"Re-run `worktree-ios-dev-tool bootstrap --force` to re-seed."
        )
    proj = data["project"]
    _require_keys("project", proj, _ALLOWED_PROJECT)
    for key in ("path", "scheme"):
        if key not in proj:
            raise UserError(f"[project] missing `{key}` in {config_path}.")
    wt_root = worktree_root(config_path)
    project = ProjectConfig(
        path=(wt_root / proj["path"]).resolve(),
        scheme=proj["scheme"],
        configuration=proj.get("configuration", "Debug"),
        simulator_prefix=proj.get("simulator_prefix") or None,
    )

    simulator: SimulatorEntry | None = None
    if "simulator" in data:
        sim = data["simulator"]
        _require_keys("simulator", sim, _ALLOWED_SIMULATOR)
        for key in _ALLOWED_SIMULATOR:
            if key not in sim:
                raise UserError(f"[simulator] missing `{key}` in {config_path}.")
        simulator = SimulatorEntry(
            name=sim["name"],
            udid=sim["udid"],
            device=sim["device"],
            runtime=sim["runtime"],
        )

    pkg_root_cfg = data.get("packages_root", {"path": "ios/Packages"})
    _require_keys("packages_root", pkg_root_cfg, _ALLOWED_PACKAGES_ROOT)
    packages_root = (wt_root / pkg_root_cfg.get("path", "ios/Packages")).resolve()

    overrides: dict[str, PackageOverride] = {}
    for name, table in (data.get("packages", {}) or {}).items():
        _require_keys(f"packages.{name}", table, _ALLOWED_PACKAGE)
        overrides[name] = PackageOverride(scheme=table.get("scheme"))

    extras = data.get("extras", {})
    _require_keys("extras", extras, _ALLOWED_EXTRAS)
    flags = extras.get("xcodebuild_flags", [])
    if not isinstance(flags, list) or not all(isinstance(f, str) for f in flags):
        raise UserError(
            f"[extras].xcodebuild_flags must be a list of strings in {config_path}."
        )

    return Config(
        config_path=config_path,
        worktree_root=wt_root,
        derived_data=derived_data_dir(config_path),
        project=project,
        simulator=simulator,
        packages_root=packages_root,
        package_overrides=overrides,
        extras_xcodebuild_flags=list(flags),
    )


def require_simulator(cfg: Config) -> SimulatorEntry:
    if cfg.simulator is None:
        raise UserError(
            "No [simulator] block in config.toml. "
            "Run `worktree-ios-dev-tool boot` first to create and register a simulator."
        )
    return cfg.simulator


def write_simulator(config_path: Path, sim: SimulatorEntry) -> None:
    """Rewrite the [simulator] block in-place using tomlkit to preserve comments."""
    text = config_path.read_text()
    doc = tomlkit.parse(text)
    block = tomlkit.table()
    block["name"] = sim.name
    block["udid"] = sim.udid
    block["device"] = sim.device
    block["runtime"] = sim.runtime
    doc["simulator"] = block
    config_path.write_text(tomlkit.dumps(doc))
