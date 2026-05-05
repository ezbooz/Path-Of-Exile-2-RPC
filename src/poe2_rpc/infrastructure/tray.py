"""System-tray icon adapter wrapping pystray.

Imported only by the ``tray`` CLI command. Module-level import gate raises a
clear ImportError when the optional ``[tray]`` extras are not installed.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

try:
    import pystray
    from PIL import Image
except ImportError as e:
    raise ImportError("Tray support requires extras: pip install poe2-rpc[tray]") from e

TrayStatus = Literal["waiting", "running", "error"]


def _default_icon() -> Any:
    """Generate a 64x64 dark-purple PIL Image when no custom icon is provided."""
    return Image.new("RGB", (64, 64), (40, 16, 56))


class TrayController:
    """Wraps pystray.Icon with a Status/Open log/Restart/Quit menu.

    Status is updated thread-safely from the orchestrator thread; the icon
    itself runs on the main thread (pystray requirement on Windows).
    """

    def __init__(
        self,
        *,
        on_open_log: Callable[[], None],
        on_restart: Callable[[], None],
        on_quit: Callable[[], None],
        icon_path: Path | None = None,
    ) -> None:
        self._status: TrayStatus = "waiting"
        self._on_open_log = on_open_log
        self._on_restart = on_restart
        self._on_quit = on_quit
        self._icon_image = Image.open(icon_path) if icon_path is not None else _default_icon()
        self._icon: Any | None = None
        self._lock = threading.Lock()

    @property
    def status(self) -> TrayStatus:
        with self._lock:
            return self._status

    def set_status(self, status: TrayStatus) -> None:
        with self._lock:
            self._status = status
            icon = self._icon
        if icon is not None:
            icon.update_menu()

    def _build_menu(self) -> Any:
        return pystray.Menu(
            pystray.MenuItem(lambda _i: f"Status: {self.status}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open log file", lambda _i, _it: self._on_open_log()),
            pystray.MenuItem("Restart", lambda _i, _it: self._on_restart()),
            pystray.MenuItem("Quit", lambda _i, _it: self._on_quit()),
        )

    def run(self) -> None:
        """Blocking — runs the tray icon on the calling (main) thread."""
        self._icon = pystray.Icon(
            "poe2-rpc",
            self._icon_image,
            "PoE2 RPC",
            menu=self._build_menu(),
        )
        self._icon.run()

    def stop(self) -> None:
        if self._icon is not None:
            self._icon.stop()
