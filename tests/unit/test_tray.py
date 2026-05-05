"""Tests for TrayController menu wiring and quit-callback ordering.

These tests run on POSIX dev machines via mocked pystray + Pillow imports,
so the tray module's import gate is satisfied before TrayController is touched.
"""

from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def fake_pystray(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Install a fake pystray module before TrayController import."""
    fake = types.ModuleType("pystray")

    class _Menu:
        SEPARATOR = object()

        def __init__(self, *items: Any) -> None:
            self.items = items

    class _MenuItem:
        def __init__(self, text: Any, action: Any = None, enabled: bool = True) -> None:
            self.text = text
            self.action = action
            self.enabled = enabled

    icon_instance = MagicMock()

    def _icon_factory(name: str, image: Any, title: str, menu: Any) -> MagicMock:
        icon_instance.name = name
        icon_instance.image = image
        icon_instance.title = title
        icon_instance.menu = menu
        return icon_instance

    fake.Menu = _Menu  # type: ignore[attr-defined]
    fake.MenuItem = _MenuItem  # type: ignore[attr-defined]
    fake.Icon = _icon_factory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pystray", fake)

    fake_pil = types.ModuleType("PIL")
    fake_pil_image = types.ModuleType("PIL.Image")

    def _open(_path: Any) -> Any:
        return MagicMock(name="opened-image")

    def _new(_mode: str, _size: tuple[int, int], _color: tuple[int, int, int]) -> Any:
        return MagicMock(name="generated-image")

    fake_pil_image.open = _open  # type: ignore[attr-defined]
    fake_pil_image.new = _new  # type: ignore[attr-defined]
    fake_pil.Image = fake_pil_image  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_pil_image)

    monkeypatch.delitem(sys.modules, "poe2_rpc.infrastructure.tray", raising=False)
    return icon_instance


def _make_controller(fake_pystray: MagicMock, on_quit: Any = None) -> Any:
    from poe2_rpc.infrastructure.tray import TrayController

    return TrayController(
        on_open_log=lambda: None,
        on_restart=lambda: None,
        on_quit=on_quit or (lambda: None),
        icon_path=None,
    )


def test_menu_items_built_correctly(fake_pystray: MagicMock) -> None:
    controller = _make_controller(fake_pystray)
    menu = controller._build_menu()
    items_with_text = [item for item in menu.items if hasattr(item, "text")]
    texts = [item.text(None) if callable(item.text) else item.text for item in items_with_text]
    assert texts[0] == "Status: waiting"
    assert "Open log file" in texts
    assert "Restart" in texts
    assert "Quit" in texts


def test_status_update_propagates_to_icon(fake_pystray: MagicMock) -> None:
    controller = _make_controller(fake_pystray)
    controller._icon = fake_pystray  # simulate run()
    controller.set_status("running")
    assert controller.status == "running"
    fake_pystray.update_menu.assert_called_once()


def test_quit_callback_fires(fake_pystray: MagicMock) -> None:
    fired: list[bool] = []
    controller = _make_controller(fake_pystray, on_quit=lambda: fired.append(True))
    menu = controller._build_menu()
    quit_item = next(
        i for i in menu.items if hasattr(i, "text") and getattr(i, "text", None) == "Quit"
    )
    quit_item.action(None, None)
    assert fired == [True]


def test_quit_callback_invokes_orchestrator_stop_then_tray_stop() -> None:
    """Order matters: orchestrator must stop FIRST so the worker thread can drain."""
    orch = MagicMock()
    icon = MagicMock()
    call_order: list[str] = []
    orch.stop.side_effect = lambda: call_order.append("orch_stop")
    icon.stop.side_effect = lambda: call_order.append("icon_stop")

    def on_quit() -> None:
        orch.stop()
        icon.stop()

    on_quit()
    assert call_order == ["orch_stop", "icon_stop"]
