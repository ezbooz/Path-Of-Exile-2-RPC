"""Test that `python -m poe2_rpc` works as an alternate entry point."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from poe2_rpc.__version__ import __version__

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"


def test_module_runs_via_python_dash_m() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "poe2_rpc", "--version"],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(SRC_DIR), **_env_passthrough()},
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert __version__ in result.stdout


def _env_passthrough() -> dict[str, str]:
    keep = ("PATH", "HOME", "USER", "LANG", "LC_ALL", "LC_CTYPE", "TERM")
    return {k: os.environ[k] for k in keep if k in os.environ}
