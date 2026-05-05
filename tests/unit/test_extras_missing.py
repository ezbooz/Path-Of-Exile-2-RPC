"""Tests that tray / install-autostart fail gracefully when extras are absent."""

from __future__ import annotations

import builtins
from typing import Any

import pytest
from typer.testing import CliRunner

from poe2_rpc.cli import app


def _patch_import_failure(
    monkeypatch: pytest.MonkeyPatch, blocked_module: str, message: str
) -> None:
    real_import = builtins.__import__

    def fake_import(
        name: str, globals_: Any = None, locals_: Any = None, fromlist: Any = (), level: int = 0
    ) -> Any:
        if name == blocked_module or name.startswith(blocked_module + "."):
            raise ImportError(message)
        return real_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_tray_command_exits_when_pystray_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    sys.modules.pop("poe2_rpc.infrastructure.tray", None)
    _patch_import_failure(
        monkeypatch,
        "pystray",
        "Tray support requires extras: pip install poe2-rpc[tray]",
    )

    runner = CliRunner()
    result = runner.invoke(app, ["tray"])

    assert result.exit_code == 1
    combined = (result.output or "") + (
        result.stderr if hasattr(result, "stderr") and result.stderr_bytes else ""
    )
    assert "pip install poe2-rpc[tray]" in combined


def test_install_autostart_exits_when_pylnk3_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    sys.modules.pop("poe2_rpc.infrastructure.autostart", None)
    _patch_import_failure(
        monkeypatch,
        "pylnk3",
        "Autostart support requires extras: pip install poe2-rpc[tray]",
    )

    runner = CliRunner()
    result = runner.invoke(app, ["install-autostart"])

    assert result.exit_code == 1
    combined = (result.output or "") + (
        result.stderr if hasattr(result, "stderr") and result.stderr_bytes else ""
    )
    assert "pip install poe2-rpc[tray]" in combined
