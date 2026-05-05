"""Tests for Windows Startup-folder shortcut install/uninstall.

pylnk3 is in the optional ``[tray]`` extras; the tests inject a stub module
into ``sys.modules`` before importing the autostart adapter so the import gate
in ``poe2_rpc.infrastructure.autostart`` succeeds on dev machines without the
extras installed.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def autostart_module(monkeypatch: pytest.MonkeyPatch) -> tuple[object, MagicMock]:
    fake_lnk = types.ModuleType("pylnk3")
    for_file_mock = MagicMock()
    fake_lnk.for_file = for_file_mock  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pylnk3", fake_lnk)
    monkeypatch.delitem(sys.modules, "poe2_rpc.infrastructure.autostart", raising=False)

    import importlib

    module = importlib.import_module("poe2_rpc.infrastructure.autostart")
    return module, for_file_mock


def test_install_creates_shortcut_in_startup_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    autostart_module: tuple[object, MagicMock],
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    module, for_file_mock = autostart_module

    exe = Path(r"C:\Tools\PathOfExile2DiscordRPC.exe")
    target = module.install_startup_shortcut(exe, target_args=["tray", "--quiet"])  # type: ignore[attr-defined]

    assert target.name == "PathOfExile2DiscordRPC.lnk"
    assert target.parent.exists()
    for_file_mock.assert_called_once()
    _, kwargs = for_file_mock.call_args
    assert kwargs["target_file"] == str(exe)
    assert kwargs["arguments"] == "tray --quiet"
    assert kwargs["lnk_name"] == str(target)


def test_uninstall_returns_false_when_shortcut_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    autostart_module: tuple[object, MagicMock],
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    module, _ = autostart_module
    assert module.uninstall_startup_shortcut() is False  # type: ignore[attr-defined]


def test_uninstall_removes_existing_shortcut(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    autostart_module: tuple[object, MagicMock],
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    module, _ = autostart_module

    startup = tmp_path / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    startup.mkdir(parents=True)
    shortcut = startup / "PathOfExile2DiscordRPC.lnk"
    shortcut.write_text("fake-lnk-bytes")

    assert module.uninstall_startup_shortcut() is True  # type: ignore[attr-defined]
    assert not shortcut.exists()


def test_install_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    autostart_module: tuple[object, MagicMock],
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    module, _ = autostart_module

    exe = Path(r"C:\Tools\foo.exe")
    target1 = module.install_startup_shortcut(exe, target_args=["tray"])  # type: ignore[attr-defined]
    target2 = module.install_startup_shortcut(exe, target_args=["tray"])  # type: ignore[attr-defined]
    assert target1 == target2


@pytest.mark.parametrize(
    ("frozen", "executable", "argv0", "expected"),
    [
        (
            True,
            r"C:\Tools\PathOfExile2DiscordRPC.exe",
            "irrelevant",
            r"C:\Tools\PathOfExile2DiscordRPC.exe",
        ),
        (
            False,
            r"C:\Python311\python.exe",
            r"C:\Tools\poe2-rpc.exe",
            r"C:\Tools\poe2-rpc.exe",
        ),
    ],
)
def test_install_autostart_uses_frozen_exe_path(
    monkeypatch: pytest.MonkeyPatch,
    frozen: bool,
    executable: str,
    argv0: str,
    expected: str,
) -> None:
    from poe2_rpc.cli import _resolve_tray_exe_path

    if frozen:
        monkeypatch.setattr(sys, "frozen", True, raising=False)
    else:
        monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(sys, "executable", executable)
    monkeypatch.setattr(sys, "argv", [argv0])

    assert _resolve_tray_exe_path() == Path(expected)
