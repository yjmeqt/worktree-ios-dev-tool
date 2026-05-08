"""The only module that actually runs subprocesses."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from .errors import EnvError, SubprocessError


def require(binary: str) -> None:
    """Raise EnvError if `binary` is not on PATH."""
    if shutil.which(binary) is None:
        raise EnvError(
            f"`{binary}` not found on PATH. Install it or run `xcode-select --install`."
        )


def _run_xcodebuild_pretty(
    argv: Sequence[str],
    *,
    cwd: Path | None,
    quiet: bool = True,
) -> int:
    """Run `xcodebuild` with its merged stdout/stderr piped through `mint run xcbeautify`.
    Returns xcodebuild's exit code (xcbeautify's is ignored — pipefail semantics)."""
    xcbeautify_argv = ["mint", "run", "xcbeautify"]
    if quiet:
        xcbeautify_argv.append("--quiet")
    xcb = subprocess.Popen(
        xcbeautify_argv,
        stdin=subprocess.PIPE,
    )
    try:
        child = subprocess.Popen(
            list(argv),
            cwd=cwd,
            stdout=xcb.stdin,
            stderr=subprocess.STDOUT,
        )
    finally:
        # Close our copy so xcbeautify sees EOF once xcodebuild exits.
        assert xcb.stdin is not None
        xcb.stdin.close()
    returncode = child.wait()
    xcb.wait()
    return returncode


def run(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    capture: bool = False,
    verbose: bool = False,
    quiet: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run argv. If capture=False, stdout/stderr stream to the parent tty.
    When argv invokes `xcodebuild` and output is not captured, the merged
    stdout/stderr is piped through `mint run xcbeautify` if `mint` is on PATH.
    Raises SubprocessError with the upstream exit code on non-zero return."""
    if verbose:
        display_cwd = f" (cwd={cwd})" if cwd else ""
        print(f"+ {' '.join(argv)}{display_cwd}")

    use_pretty = (
        not capture
        and len(argv) > 0
        and argv[0] == "xcodebuild"
        and shutil.which("mint") is not None
    )

    if use_pretty:
        returncode = _run_xcodebuild_pretty(argv, cwd=cwd, quiet=quiet)
        if returncode != 0:
            raise SubprocessError(
                f"xcodebuild failed with exit code {returncode}",
                upstream_exit=returncode,
            )
        return subprocess.CompletedProcess(list(argv), returncode, stdout=None, stderr=None)

    if (
        not capture
        and len(argv) > 0
        and argv[0] == "xcodebuild"
        and shutil.which("mint") is None
    ):
        print(
            "note: `mint` not found on PATH — xcodebuild output will not be prettified "
            "through xcbeautify. Install mint (brew install mint) for cleaner logs.",
            file=sys.stderr,
        )

    result = subprocess.run(
        list(argv),
        cwd=cwd,
        text=True,
        capture_output=capture,
    )
    if result.returncode != 0:
        tool = argv[0]
        msg = f"{tool} failed with exit code {result.returncode}"
        if capture and result.stderr:
            msg += f":\n{result.stderr.rstrip()}"
        raise SubprocessError(msg, upstream_exit=result.returncode)
    return result


def run_json(argv: Sequence[str], *, verbose: bool = False) -> str:
    """Capture-only convenience; returns stdout as string. Used for simctl list --json."""
    result = run(argv, capture=True, verbose=verbose)
    return result.stdout
