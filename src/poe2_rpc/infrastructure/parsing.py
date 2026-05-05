"""Regex-based log line parsers — byte-patterns preserved verbatim from main.py:273-274."""

from __future__ import annotations

import re
from typing import Literal

from poe2_rpc.domain.models import AFKStatus, InstanceInfo, LevelInfo

regex_level = re.compile(r": (\w+) \(([\w\s]+)\) is now level (\d+)")
regex_instance = re.compile(r'Generating level (\d+) area "([^"]+)" with seed (\d+)')
# Verbatim from klayveR/poe-log-monitor resource/events.json:
regex_local_area_entered = re.compile(r": You have entered (.*)\.")
regex_party_joined = re.compile(r": (\S+) has joined the area\.")
regex_afk = re.compile(r': (DND|AFK) mode is now (?:(ON)\. Autoreply "(.*)"|(OFF))')


def parse_level_event(line: str) -> LevelInfo | None:
    m = regex_level.search(line)
    if not m:
        return None
    return LevelInfo(
        username=m.group(1),
        base_class=m.group(2),
        ascension_class=None,
        level=int(m.group(3)),
    )


def parse_instance_event(line: str) -> InstanceInfo | None:
    m = regex_instance.search(line)
    if not m:
        return None
    return InstanceInfo(
        level=int(m.group(1)),
        area_code=m.group(2),
        area_display_name=m.group(2),
        seed=int(m.group(3)),
    )


def parse_local_area_entered_event(line: str) -> str | None:
    m = regex_local_area_entered.search(line)
    return m.group(1) if m else None


def parse_party_joined_event(line: str) -> str | None:
    m = regex_party_joined.search(line)
    return m.group(1) if m else None


def parse_afk_event_line(line: str) -> AFKStatus | None:
    m = regex_afk.search(line)
    if not m:
        return None
    raw_mode = m.group(1)
    mode: Literal["AFK", "DND"]
    if raw_mode == "AFK":
        mode = "AFK"
    elif raw_mode == "DND":
        mode = "DND"
    else:
        return None
    if m.group(2) == "ON":
        return AFKStatus(mode=mode, on=True, autoreply=m.group(3))
    return AFKStatus(mode=mode, on=False, autoreply=None)


class RegexLogParser:
    """LogParser port adapter wrapping the module-level parse_*_event functions."""

    @staticmethod
    def parse_level(line: str) -> LevelInfo | None:
        return parse_level_event(line)

    @staticmethod
    def parse_instance(line: str) -> InstanceInfo | None:
        return parse_instance_event(line)

    @staticmethod
    def parse_local_area_entered(line: str) -> str | None:
        return parse_local_area_entered_event(line)

    @staticmethod
    def parse_party_joined(line: str) -> str | None:
        return parse_party_joined_event(line)

    @staticmethod
    def parse_afk_event(line: str) -> AFKStatus | None:
        return parse_afk_event_line(line)
