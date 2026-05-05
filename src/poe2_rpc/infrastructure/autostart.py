"""Windows Startup-folder shortcut adapter.

Writes a ``.lnk`` file into ``%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup``
so the tray launcher boots on user login. Import-gated on the ``[tray]`` extras.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    import pylnk3
except ImportError as e:
    raise ImportError("Autostart support requires extras: pip install poe2-rpc[tray]") from e

_SHORTCUT_NAME = "PathOfExile2DiscordRPC.lnk"


def _startup_dir() -> Path:
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def install_startup_shortcut(exe_path: Path, target_args: list[str]) -> Path:
    """Create or overwrite the Startup-folder shortcut. Idempotent."""
    target = _startup_dir() / _SHORTCUT_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    pylnk3.for_file(
        target_file=str(exe_path),
        lnk_name=str(target),
        arguments=" ".join(target_args),
        description="Path of Exile 2 Discord RPC (background tray)",
    )
    return target


def uninstall_startup_shortcut() -> bool:
    """Remove the Startup-folder shortcut if present. Returns True iff removed."""
    target = _startup_dir() / _SHORTCUT_NAME
    if target.exists():
        target.unlink()
        return True
    return False
