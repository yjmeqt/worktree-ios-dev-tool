"""Local Swift package test resolution.

Default convention:

    cd ios/Packages/<Name> && xcodebuild test \
        -scheme <Name>

xcodebuild auto-discovers Package.swift from CWD — do not pass -project.

Overrides from [packages.<Name>] in config.toml merge over the convention.
"""
from __future__ import annotations

from pathlib import Path

from .config import Config, require_simulator
from .errors import UserError


def resolve(cfg: Config, package_name: str) -> tuple[list[str], Path]:
    """Return (argv, cwd) for testing a local package."""
    pkg_dir = cfg.packages_root / package_name
    if not pkg_dir.is_dir():
        raise UserError(
            f"Package directory not found: `{pkg_dir}`. "
            f"Check the name and `packages_root.path` in config.toml."
        )

    override = cfg.package_overrides.get(package_name)
    scheme = override.scheme if (override and override.scheme) else package_name

    sim = require_simulator(cfg)
    argv = [
        "xcodebuild",
        "test",
        "-scheme", scheme,
        "-destination", f"platform=iOS Simulator,id={sim.udid}",
        "-derivedDataPath", str(cfg.derived_data),
    ] + cfg.extras_xcodebuild_flags
    return argv, pkg_dir
