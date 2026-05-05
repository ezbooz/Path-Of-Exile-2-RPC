import datetime
import json
import logging
import os
import re
import time
from enum import Enum
from pathlib import Path
import random
from typing import Dict, List, Optional

import psutil
from pypresence import Presence

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


def update_rpc(
    level_info,
    instance_info=None,
    status=None,
    small_image_override=None,
    afk_suffix=False,
):
    if instance_info:
        status = f"In: {instance_info['location_name']} (Lvl {instance_info['location_level']})"
    else:
        if status is None:
            status = random_status()

    if afk_suffix:
        status = f"{status} [AFK]"

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
        if small_image_override is not None:
            small_image = small_image_override
        else:
            small_image = level_info["ascension_class"].lower().replace(" ", "_")
        rpc.update(
            details=details,
            state=status,
            start=int(datetime.datetime.now().timestamp()),
            small_image=small_image,
        )
    except Exception as e:
        logging.error(f"Failed to update RPC: {e}")


regex_level = re.compile(r": (\w+) \(([\w\s]+)\) is now level (\d+)")
regex_instance = re.compile(r'Generating level (\d+) area "([^"]+)" with seed (\d+)')
regex_afk = re.compile(r': (DND|AFK) mode is now (?:(ON)\. Autoreply "(.*)"|(OFF))')

_afk_on = False
_prior_small_image: Optional[str] = None


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

    global _afk_on, _prior_small_image

    with log_file_path.open("r", encoding="utf-8") as log_file:
        log_file.seek(0, 2)

        current_status = {"level_info": last_level_info, "instance_info": None}

        while True:
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

                afk_match = regex_afk.search(line)
                if afk_match and current_status["level_info"]:
                    on_token = afk_match.group(2)
                    if on_token == "ON":
                        # Snapshot current small_image so OFF restores EXACTLY
                        # this value, even if level changes during AFK window.
                        _prior_small_image = (
                            current_status["level_info"]["ascension_class"]
                            .lower()
                            .replace(" ", "_")
                        )
                        _afk_on = True
                        update_rpc(
                            current_status["level_info"],
                            current_status["instance_info"],
                            small_image_override="afk",
                            afk_suffix=True,
                        )
                    else:
                        _afk_on = False
                        update_rpc(
                            current_status["level_info"],
                            current_status["instance_info"],
                            small_image_override=_prior_small_image,
                        )
                        _prior_small_image = None

            time.sleep(5)


if __name__ == "__main__":
    rpc = rpc_connect()
    monitor_log()
