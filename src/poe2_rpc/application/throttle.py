"""Presence update throttle and random status strings."""

from __future__ import annotations

import random
import time
from collections.abc import Callable


def random_status() -> str:
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


class PresenceThrottle:
    """Rate-limits presence updates to at most once per interval seconds."""

    def __init__(
        self,
        interval: float = 15.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._interval = interval
        self._clock = clock
        self._last: float | None = None

    def should_update(self) -> bool:
        now = self._clock()
        if self._last is None or (now - self._last) >= self._interval:
            self._last = now
            return True
        return False
