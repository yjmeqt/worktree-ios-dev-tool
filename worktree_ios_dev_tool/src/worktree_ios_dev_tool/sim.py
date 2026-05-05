# worktree_ios_dev_tool/src/worktree_ios_dev_tool/sim.py
"""Implementations of the `sim` namespace verbs.

Each function corresponds to one ``sim <verb>`` CLI invocation. The module
owns the policy layer (single/multi-sim resolution, name synthesis, output
formatting); :mod:`simulator` owns the simctl subprocess wrappers.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from . import simulator as sim_mod, ui
from .config import (
    Config,
    SimulatorEntry,
    load,
    remove_simulator_entry,
    resolve_sim,
    upsert_simulator_entry,
)
from .errors import UserError
from .paths import find_project_toml, simulator_toml_for


# ── shared helpers ───────────────────────────────────────────────────────────

def _load(args: argparse.Namespace) -> tuple[Config, Path]:
    """Resolve project.toml and the matching simulator.toml path."""
    path = args.config.resolve() if args.config else find_project_toml()
    return load(path), simulator_toml_for(path)


def _resolve_label(cfg: Config, label: str | None) -> str:
    """Return the label of the sim a verb without an explicit arg should target.

    Same single/multi rules as :func:`config.resolve_sim`, but returns the
    *label* rather than the entry — useful for verbs like ``shutdown`` that
    operate on the entry by label.
    """
    entry = resolve_sim(cfg, label=label)
    for k, v in cfg.simulators.items():
        if v is entry:
            return k
    raise AssertionError("resolve_sim returned an entry not in cfg.simulators")


# ── verbs ────────────────────────────────────────────────────────────────────

def cmd_pick(args: argparse.Namespace) -> int:
    """Interactively pick + create a simulator and write it to simulator.toml.

    Errors if an entry with that label already exists; the user must call
    ``sim recreate <label>`` to replace one.
    """
    cfg, sim_toml = _load(args)
    label = args.label or "default"
    sim_mod.validate_label(label)

    if label in cfg.simulators:
        raise UserError(
            f"A simulator labeled `{label}` already exists. "
            f"Use `worktree-ios-dev-tool sim recreate {label}` to replace it."
        )

    sim_mod.ensure_tooling()

    device, runtime = sim_mod.pick_device_and_runtime(iphone_17_only=not args.all_devices)
    name = sim_mod.synth_managed_name(
        cfg.project.simulator_prefix, cfg.worktree_root.name, label,
    )

    existing = sim_mod.find_device_by_name(name)
    if existing is not None:
        ui.warn(f"Simulator named '{name}' already exists (udid={existing['udid']}).")
        choice = input("Reuse it? [Y/n] ").strip().lower() if ui.is_interactive() else "y"
        if choice in ("", "y", "yes"):
            udid = existing["udid"]
        else:
            raise UserError(
                "Aborted. Delete the existing sim manually or use "
                f"`sim recreate {label}` next time."
            )
    else:
        ui.step(f"Creating {name}…")
        udid = sim_mod.create(name, device, runtime)

    entry = SimulatorEntry(name=name, udid=udid, device=device.name, runtime=runtime.name)
    upsert_simulator_entry(sim_toml, label, entry)
    sim_mod.boot(udid)

    ui.sep()
    ui.done(f"Simulator ready  [{label}]")
    ui.info(f"name    = {entry.name}")
    ui.info(f"udid    = {entry.udid}")
    ui.info(f"device  = {entry.device}")
    ui.info(f"runtime = {entry.runtime}")
    return 0


def cmd_boot(args: argparse.Namespace) -> int:
    """Boot a configured simulator. ``--all`` boots every entry."""
    cfg, _ = _load(args)
    if args.all:
        if not cfg.simulators:
            raise UserError("No simulators configured. Run `sim pick` first.")
        for label, entry in cfg.simulators.items():
            ui.step(f"Booting {label} ({entry.udid})…")
            sim_mod.boot(entry.udid)
        ui.done(f"Booted {len(cfg.simulators)} simulator(s).")
        return 0

    entry = resolve_sim(cfg, label=args.label)
    sim_mod.boot(entry.udid)
    ui.done(f"Booted {entry.name} ({entry.udid}).")
    return 0


def cmd_shutdown(args: argparse.Namespace) -> int:
    """Shutdown a configured simulator. ``--all`` shuts down every entry."""
    cfg, _ = _load(args)
    if args.all:
        if not cfg.simulators:
            ui.done("No simulators configured.")
            return 0
        for label, entry in cfg.simulators.items():
            ui.step(f"Shutdown {label} ({entry.udid})…")
            sim_mod.shutdown(entry.udid)
        ui.done(f"Shut down {len(cfg.simulators)} simulator(s).")
        return 0

    entry = resolve_sim(cfg, label=args.label)
    sim_mod.shutdown(entry.udid)
    ui.done(f"Shut down {entry.name} ({entry.udid}).")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List configured simulators (default: this worktree; ``--global`` for all).

    Local mode uses ``simulator.toml`` as truth and consults simctl for state.
    Global mode scans simctl for ``<simulator_prefix>-*`` and groups by the
    parsed worktree-basename segment of each device name.
    """
    cfg, _ = _load(args)
    if args.global_:
        prefix = cfg.project.simulator_prefix
        groups: dict[str, list[dict]] = defaultdict(list)
        for dev in sim_mod.list_devices_by_prefix(prefix):
            parsed = sim_mod.parse_managed_name(dev["name"], prefix=prefix)
            if parsed is None:
                continue
            basename, _label = parsed
            groups[basename].append(dev)
        if not groups:
            ui.done(f"No managed simulators found (prefix: {prefix}).")
            return 0
        for basename in sorted(groups):
            ui.info(f"worktree={basename}")
            for dev in sorted(groups[basename], key=lambda d: d["name"]):
                state = dev.get("state", "?")
                ui.info(f"  {dev['name']:<40} {dev['udid']}  state={state}")
        return 0

    if not cfg.simulators:
        ui.done("No simulators configured. Run `sim pick`.")
        return 0
    for label, entry in cfg.simulators.items():
        dev = sim_mod.find_device_by_udid(entry.udid)
        state = dev.get("state", "?") if dev else "MISSING"
        ui.info(f"{label:<10} {entry.name:<40} {entry.udid}  state={state}")
    return 0
