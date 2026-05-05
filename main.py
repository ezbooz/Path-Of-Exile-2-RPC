import argparse
import datetime
import json
import logging
import os
import re
import sys
import threading
import time
from enum import Enum
from pathlib import Path
import random
from typing import Dict, List, Optional

import psutil
from pypresence import Presence

_stop_event = threading.Event()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class CharacterClass(Enum):
    MERCENARY = "Mercenary"
    MONK = "Monk"
    RANGER = "Ranger"
    SORCERESS = "Sorceress"
    WARRIOR = "Warrior"
    WITCH = "Witch"
    HUNTRESS = "Huntress"

    def get_ascendencies(self) -> Optional[List["ClassAscendency"]]:
        return {
            CharacterClass.MERCENARY: [
                ClassAscendency.WITCHHUNTER,
                ClassAscendency.GEMLING_LEGIONNAIRE,
            ],
            CharacterClass.MONK: [
                ClassAscendency.ACOLYTE_OF_CHAYULA,
                ClassAscendency.INVOKER,
            ],
            CharacterClass.RANGER: [
                ClassAscendency.DEADEYE,
                ClassAscendency.PATHFINDER,
            ],
            CharacterClass.SORCERESS: [
                ClassAscendency.CHRONOMANCER,
                ClassAscendency.STORMWEAVER,
            ],
            CharacterClass.WARRIOR: [
                ClassAscendency.TITAN,
                ClassAscendency.WARBRINGER,
            ],
            CharacterClass.WITCH: [
                ClassAscendency.BLOOD_MAGE,
                ClassAscendency.INFERNALIST,
            ],
            CharacterClass.HUNTRESS: [
                ClassAscendency.RITUALIST,
                ClassAscendency.AMAZON,
            ],
        }.get(self)


class ClassAscendency(Enum):
    WITCHHUNTER = "Witchhunter"
    GEMLING_LEGIONNAIRE = "Gemling Legionnaire"
    ACOLYTE_OF_CHAYULA = "Acolyte of Chayula"
    INVOKER = "Invoker"
    DEADEYE = "Deadeye"
    PATHFINDER = "Pathfinder"
    CHRONOMANCER = "Chronomancer"
    STORMWEAVER = "Stormweaver"
    TITAN = "Titan"
    WARBRINGER = "Warbringer"
    BLOOD_MAGE = "Blood Mage"
    INFERNALIST = "Infernalist"
    RITUALIST = "Ritualist"
    AMAZON = "Amazon"
    SMITH_OF_KITAVA = "Smith of Kitava"
    LICH = "Lich"
    TACTICIAN = "Tactician"

    def get_class(self) -> CharacterClass:
        return {
            ClassAscendency.WITCHHUNTER: CharacterClass.MERCENARY,
            ClassAscendency.GEMLING_LEGIONNAIRE: CharacterClass.MERCENARY,
            ClassAscendency.TACTICIAN: CharacterClass.MERCENARY,
            ClassAscendency.ACOLYTE_OF_CHAYULA: CharacterClass.MONK,
            ClassAscendency.INVOKER: CharacterClass.MONK,
            ClassAscendency.DEADEYE: CharacterClass.RANGER,
            ClassAscendency.PATHFINDER: CharacterClass.RANGER,
            ClassAscendency.CHRONOMANCER: CharacterClass.SORCERESS,
            ClassAscendency.STORMWEAVER: CharacterClass.SORCERESS,
            ClassAscendency.TITAN: CharacterClass.WARRIOR,
            ClassAscendency.WARBRINGER: CharacterClass.WARRIOR,
            ClassAscendency.SMITH_OF_KITAVA: CharacterClass.WARRIOR,
            ClassAscendency.BLOOD_MAGE: CharacterClass.WITCH,
            ClassAscendency.INFERNALIST: CharacterClass.WITCH,
            ClassAscendency.LICH: CharacterClass.WITCH,
            ClassAscendency.RITUALIST: CharacterClass.HUNTRESS,
            ClassAscendency.AMAZON: CharacterClass.HUNTRESS,
        }[self]


def find_game_log():
    logging.info("Waiting for the game start..")
    while True:
        try:
            for process in psutil.process_iter(["name", "exe"]):
                if process.info.get("name") == "PathOfExileSteam.exe":
                    full_path = process.info.get("exe")
                    if full_path:
                        game_dir = os.path.dirname(full_path)
                        logging.info(f"Found game log at {game_dir}")
                        return os.path.join(game_dir, "logs", "Client.txt")
        except Exception as e:
            logging.error(f"Error accessing processes: {e}")
        time.sleep(3)


def random_status():
    statuses = [
        "Exploring ancient ruins",
        "Leveling up your skills",
        "Defeating hordes of enemies",
        "Looting rare artifacts",
        "Crossing dark portals",
        "Enhancing powerful gear",
        "Learning forbidden magic",
        "Tracking down the next boss",
        "Joining the fight in the league",
        "Preparing for the final encounter",
    ]
    return random.choice(statuses)


def load_locations():
    file_path = Path("locations.json")
    url = "https://raw.githubusercontent.com/ezbooz/Path-Of-Exile-2-RPC/refs/heads/main/locations.json"

    if file_path.exists():
        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                logging.info("Loaded locations from local cache.")
                return data.get("areas", {})
        except Exception as e:
            logging.error(f"Error reading cached locations: {e}")
            return {}

    try:
        import urllib.request

        with urllib.request.urlopen(url) as response:
            data = json.load(response)
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logging.info("Downloaded and cached locations.")
        return data.get("areas", {})
    except Exception as e:
        logging.error(f"Failed to fetch locations from the server: {e}")
        return {}


def determine_location(area_name: str, locations: Dict[str, str]) -> Optional[str]:
    normalized_area_name = area_name

    if area_name.startswith("Map"):
        normalized_area_name = area_name[3:].split("_")[0]

    if normalized_area_name in locations.values():
        return normalized_area_name
    else:
        for key, value in locations.items():
            if normalized_area_name == key or normalized_area_name == value:
                return value

    return normalized_area_name


def find_last_level_up(line: str, regex_level: re.Pattern) -> Optional[Dict[str, str]]:
    if match := regex_level.search(line):
        username, base_class, level = match.groups()
        base_class = base_class.strip()
        try:
            if base_class in ClassAscendency._value2member_map_:
                ascension_class = base_class
                base_class = ClassAscendency(base_class).get_class().value
            else:
                ascension_class = "Unknown"
        except Exception:
            ascension_class = "Unknown"
        return {
            "username": username,
            "ascension_class": ascension_class,
            "base_class": base_class,
            "level": level,
        }
    return None


def get_last_level_up(
    log_file_path: Path, regex_level: re.Pattern
) -> Optional[Dict[str, str]]:
    try:
        with log_file_path.open("r", encoding="utf-8") as log_file:
            lines = log_file.readlines()
            for line in reversed(lines):
                if match := regex_level.search(line):
                    return find_last_level_up(line, regex_level)
    except Exception:
        pass
    return None


def find_instance(
    line: str, regex_instance: re.Pattern, locations: Dict[str, str]
) -> Optional[Dict[str, str]]:
    if match := regex_instance.search(line):
        level, area_name, seed = match.groups()
        location_name = determine_location(area_name, locations)
        return {
            "location_name": location_name or area_name,
            "location_level": level,
        }
    return None


def rpc_connect():
    retries = 0
    while retries < 5:
        try:
            rpc = Presence("1315800372207419504")
            rpc.connect()
            logging.info("Connected to Discord RPC.")
            return rpc
        except Exception as e:
            retries += 1
            logging.error(f"Retrying RPC connection, attempt {retries}...")
            time.sleep(2**retries)
            logging.warning(f"Error connecting to Discord RPC: {e}")
    logging.error(
        f"Failed to connect to Discord RPC after multiple retries.  Please ensure Discord is running and the application is authorized."
    )
    return None


def update_rpc(level_info, instance_info=None, status=None):
    if instance_info:
        status = f"In: {instance_info['location_name']} (Lvl {instance_info['location_level']})"
    else:
        if status is None:
            status = random_status()

    try:
        details = (
            f"{level_info['username']} ({level_info['base_class']}"
            + (
                f" | {level_info['ascension_class']}"
                if level_info["ascension_class"] != "Unknown"
                else ""
            )
            + f" - Lvl {level_info['level']})"
        )
        rpc.update(
            details=details,
            state=status,
            start=int(datetime.datetime.now().timestamp()),
            small_image=level_info["ascension_class"].lower().replace(" ", "_"),
        )
    except Exception as e:
        logging.error(f"Failed to update RPC: {e}")


regex_level = re.compile(r": (\w+) \(([\w\s]+)\) is now level (\d+)")
regex_instance = re.compile(r'Generating level (\d+) area "([^"]+)" with seed (\d+)')


def monitor_log():
    game_path = find_game_log()

    log_file_path = Path(game_path)
    locations = load_locations()

    last_level_info = get_last_level_up(log_file_path, regex_level)
    if last_level_info:
        details = (
            f"{last_level_info['username']} ({last_level_info['base_class']}"
            + (
                f" | {last_level_info['ascension_class']}"
                if last_level_info["ascension_class"] != "Unknown"
                else ""
            )
            + f" - Lvl {last_level_info['level']})"
        )
        rpc.update(
            details=details,
            state=random_status(),
            start=int(datetime.datetime.now().timestamp()),
            small_image=last_level_info["ascension_class"].lower(),
        )

    with log_file_path.open("r", encoding="utf-8") as log_file:
        log_file.seek(0, 2)

        current_status = {"level_info": last_level_info, "instance_info": None}

        while not _stop_event.is_set():
            new_lines = log_file.readlines()
            for line in new_lines:
                level_info = find_last_level_up(line, regex_level)
                if level_info and (
                    not current_status["level_info"]
                    or level_info != current_status["level_info"]
                ):
                    current_status["level_info"] = level_info
                    update_rpc(level_info, current_status["instance_info"])

                instance_info = find_instance(line, regex_instance, locations)
                if instance_info and (
                    not current_status["instance_info"]
                    or instance_info != current_status["instance_info"]
                ):
                    current_status["instance_info"] = instance_info
                    update_rpc(current_status["level_info"], instance_info)

            if _stop_event.wait(5.0):
                break


# ---------------------------------------------------------------------------
# Background launcher: tray icon + Windows Startup-folder shortcut.
# All optional dependencies (pystray, Pillow, pylnk3) are imported lazily
# inside the helpers below so the standard `python main.py` flow keeps
# working without them. Install them with: pip install pystray Pillow pylnk3
# ---------------------------------------------------------------------------

_STARTUP_SHORTCUT_NAME = "PathOfExile2DiscordRPC.lnk"


def _startup_dir() -> Path:
    appdata = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _resolve_target_exe() -> Path:
    """Return the executable the Startup shortcut should launch.

    Frozen (PyInstaller --onefile) installs point at the bundled .exe;
    source installs point at the current Python interpreter.
    """
    return Path(sys.executable)


def _resolve_target_args() -> List[str]:
    """Args the shortcut passes; for source installs, prepend the script path."""
    if getattr(sys, "frozen", False):
        return ["--tray", "--quiet"]
    return [str(Path(__file__).resolve()), "--tray", "--quiet"]


def install_autostart() -> Path:
    try:
        import pylnk3
    except ImportError:
        sys.exit(
            "Autostart support requires pylnk3. Install with: pip install pylnk3"
        )

    target = _startup_dir() / _STARTUP_SHORTCUT_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    pylnk3.for_file(
        target_file=str(_resolve_target_exe()),
        lnk_name=str(target),
        arguments=" ".join(_resolve_target_args()),
        description="Path of Exile 2 Discord RPC (background tray)",
    )
    logging.info(f"Installed Startup shortcut at {target}")
    return target


def uninstall_autostart() -> bool:
    target = _startup_dir() / _STARTUP_SHORTCUT_NAME
    if target.exists():
        target.unlink()
        logging.info(f"Removed Startup shortcut at {target}")
        return True
    logging.info(f"No Startup shortcut found at {target}")
    return False


def _open_log_file() -> None:
    """Best-effort open of the live game log via the OS handler."""
    try:
        path = Path(find_game_log())
    except Exception as e:
        logging.error(f"Cannot resolve log path: {e}")
        return
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        os.system(f'open "{path}"')
    else:
        os.system(f'xdg-open "{path}"')


def _restart_self() -> None:
    """Re-exec the current process with the same arguments."""
    _stop_event.set()
    os.execv(sys.executable, [sys.executable, *sys.argv])


def run_tray() -> None:
    try:
        import pystray
        from PIL import Image
    except ImportError:
        sys.exit(
            "Tray support requires pystray and Pillow. "
            "Install with: pip install pystray Pillow"
        )

    icon_image = Image.new("RGB", (64, 64), (40, 16, 56))
    state: Dict[str, str] = {"status": "waiting"}

    def on_quit(icon: object, _item: object) -> None:
        _stop_event.set()
        getattr(icon, "stop", lambda: None)()

    def on_open_log(_icon: object, _item: object) -> None:
        _open_log_file()

    def on_restart(_icon: object, _item: object) -> None:
        _restart_self()

    menu = pystray.Menu(
        pystray.MenuItem(lambda _i: f"Status: {state['status']}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open log file", on_open_log),
        pystray.MenuItem("Restart", on_restart),
        pystray.MenuItem("Quit", on_quit),
    )
    icon = pystray.Icon("poe2-rpc", icon_image, "PoE2 RPC", menu=menu)

    def worker() -> None:
        global rpc
        try:
            rpc = rpc_connect()
            state["status"] = "running"
            icon.update_menu()
            monitor_log()
        except Exception as e:
            state["status"] = "error"
            logging.error(f"Tray worker crashed: {e}")
            icon.update_menu()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    icon.run()
    _stop_event.set()
    thread.join(timeout=5.0)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Path of Exile 2 Discord RPC")
    parser.add_argument(
        "--tray",
        action="store_true",
        help="Run as a system-tray background service (requires pystray + Pillow).",
    )
    parser.add_argument(
        "--install-autostart",
        action="store_true",
        help="Install a Windows Startup-folder shortcut that launches --tray on login.",
    )
    parser.add_argument(
        "--uninstall-autostart",
        action="store_true",
        help="Remove the Windows Startup-folder shortcut, if present.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress console logging (intended for tray/autostart launches).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    if args.install_autostart:
        install_autostart()
        sys.exit(0)
    if args.uninstall_autostart:
        sys.exit(0 if uninstall_autostart() else 1)
    if args.tray:
        run_tray()
        sys.exit(0)
    rpc = rpc_connect()
    monitor_log()
