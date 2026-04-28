"""xcrun simctl wrappers + interactive picker for `boot`.

Only this module and proc.py touch simctl.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass

from . import ui
from .config import SimulatorConfig
from .errors import EnvError, UserError
from .proc import require, run, run_json


@dataclass(frozen=True)
class DeviceType:
    identifier: str
    name: str


@dataclass(frozen=True)
class Runtime:
    identifier: str
    name: str
    version: str


_IPHONE17_RE = re.compile(r"iPhone 17(\b| )")


def ensure_tooling() -> None:
    require("xcrun")


def list_device_types(*, iphone_17_only: bool = True) -> list[DeviceType]:
    ensure_tooling()
    data = json.loads(run_json(["xcrun", "simctl", "list", "devicetypes", "--json"]))
    types = [
        DeviceType(identifier=t["identifier"], name=t["name"])
        for t in data.get("devicetypes", [])
        if t.get("productFamily") == "iPhone"
    ]
    if iphone_17_only:
        types = [t for t in types if _IPHONE17_RE.search(t.name)]
    types.sort(key=lambda t: t.name)
    return types


def list_runtimes() -> list[Runtime]:
    ensure_tooling()
    data = json.loads(run_json(["xcrun", "simctl", "list", "runtimes", "--json"]))
    out: list[Runtime] = []
    for r in data.get("runtimes", []):
        if not r.get("isAvailable", False):
            continue
        if r.get("platform", "iOS") != "iOS":
            continue
        out.append(Runtime(identifier=r["identifier"], name=r["name"], version=r["version"]))
    out.sort(key=lambda r: [int(p) for p in r.version.split(".") if p.isdigit()], reverse=True)
    return out


def find_device_by_name(name: str) -> dict | None:
    """Return the first device dict matching name, or None."""
    data = json.loads(run_json(["xcrun", "simctl", "list", "devices", "--json"]))
    for _, devices in data.get("devices", {}).items():
        for dev in devices:
            if dev.get("name") == name:
                return dev
    return None


def find_device_by_udid(udid: str) -> dict | None:
    data = json.loads(run_json(["xcrun", "simctl", "list", "devices", "--json"]))
    for _, devices in data.get("devices", {}).items():
        for dev in devices:
            if dev.get("udid") == udid:
                return dev
    return None


def create(name: str, device_type: DeviceType, runtime: Runtime) -> str:
    """Create a simulator and return the new UDID."""
    out = run_json(["xcrun", "simctl", "create", name, device_type.identifier, runtime.identifier])
    return out.strip()


def boot(udid: str) -> None:
    """Boot the simulator. No-ops if already booted."""
    dev = find_device_by_udid(udid)
    if dev is None:
        raise UserError(f"No simulator with UDID {udid}.")
    if dev.get("state") == "Booted":
        ui.step(f"Simulator already booted ({udid}).")
        return
    ui.step("Booting simulator…")
    run(["xcrun", "simctl", "boot", udid])
    run(["open", "-a", "Simulator"])


def delete(udid: str) -> None:
    run(["xcrun", "simctl", "delete", udid])


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _pick_fuzzy(prompt: str, options: list[str]) -> str:
    """Fuzzy picker using InquirerPy. Falls back to numbered list when InquirerPy
    cannot render (e.g. TERM=dumb). Raises EnvError if not on a TTY."""
    if not _is_interactive():
        raise EnvError(
            "`worktree-ios-dev-tool boot` first-run picker needs a real terminal. "
            "Re-run from an interactive shell."
        )
    try:
        from InquirerPy import inquirer
        return inquirer.fuzzy(message=prompt, choices=options).execute()
    except (ImportError, OSError, EOFError):
        # Fallback: numbered list when InquirerPy unavailable or terminal can't render
        print(prompt)
        for i, opt in enumerate(options, start=1):
            print(f"  {i}. {opt}")
        while True:
            raw = input("Choice: ").strip()
            if raw.isdigit():
                idx = int(raw)
                if 1 <= idx <= len(options):
                    return options[idx - 1]
            print(f"Enter a number 1..{len(options)}.")


def pick_device_and_runtime(*, iphone_17_only: bool) -> tuple[DeviceType, Runtime]:
    devices = list_device_types(iphone_17_only=iphone_17_only)
    if not devices:
        raise EnvError(
            "No matching iPhone device types found. "
            "Try `worktree-ios-dev-tool boot --all-devices`."
        )
    runtimes = list_runtimes()
    if not runtimes:
        raise EnvError("No iOS runtimes installed. Install via Xcode > Settings > Platforms.")
    device_name = _pick_fuzzy("Select device type:", [d.name for d in devices])
    runtime_name = _pick_fuzzy("Select runtime:", [r.name for r in runtimes])
    device = next(d for d in devices if d.name == device_name)
    runtime = next(r for r in runtimes if r.name == runtime_name)
    return device, runtime


def to_config(name: str, udid: str, device: DeviceType, runtime: Runtime) -> SimulatorConfig:
    return SimulatorConfig(name=name, udid=udid, device=device.name, runtime=runtime.name)
