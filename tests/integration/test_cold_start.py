"""F-4: cold-start benchmark for the PyInstaller binary.

Runs `validate-config --no-discord` 5 times and asserts each invocation
completes within the 8s budget. Skipped when the binary is not built (local
dev) — CI sets POE2_RPC_EXE to `dist/PathOfExile2DiscordRPC.exe`.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

_BUDGET_SECONDS = 8.0
_RUNS = 5


def _resolve_exe_path() -> Path | None:
    env = os.environ.get("POE2_RPC_EXE")
    if env:
        return Path(env)
    default = Path("dist") / "PathOfExile2DiscordRPC.exe"
    return default if default.exists() else None


@pytest.fixture(scope="module")
def exe_path() -> Path:
    path = _resolve_exe_path()
    if path is None or not path.exists():
        pytest.skip("PathOfExile2DiscordRPC.exe not built — set POE2_RPC_EXE or run pyinstaller")
    return path


def test_cold_start_p95_under_budget(exe_path: Path) -> None:
    """Each of the 5 cold-start runs must finish under the 8s p95 budget."""
    timings: list[float] = []
    for _ in range(_RUNS):
        started = time.perf_counter()
        result = subprocess.run(
            [str(exe_path), "validate-config", "--no-discord"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        elapsed = time.perf_counter() - started
        timings.append(elapsed)
        assert result.returncode == 0, (
            f"validate-config exited {result.returncode}: {result.stderr}"
        )
    sorted_timings = sorted(timings)
    p95 = sorted_timings[int(0.95 * len(sorted_timings)) - 1]
    assert p95 <= _BUDGET_SECONDS, (
        f"cold-start p95 {p95:.2f}s exceeds budget {_BUDGET_SECONDS}s; "
        f"timings={[f'{t:.2f}' for t in timings]}"
    )
