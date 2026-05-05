"""Tests for PresenceThrottle application service."""

from __future__ import annotations

from poe2_rpc.application.throttle import PresenceThrottle, random_status


def test_first_call_is_not_throttled() -> None:
    clock_val = 0.0

    def clock() -> float:
        return clock_val

    throttle = PresenceThrottle(interval=5.0, clock=clock)
    assert throttle.should_update() is True


def test_second_call_within_interval_is_throttled() -> None:
    clock_val = 0.0

    def clock() -> float:
        return clock_val

    throttle = PresenceThrottle(interval=5.0, clock=clock)
    throttle.should_update()
    clock_val = 3.0
    assert throttle.should_update() is False


def test_call_after_interval_is_not_throttled() -> None:
    clock_val = 0.0

    def clock() -> float:
        return clock_val

    throttle = PresenceThrottle(interval=5.0, clock=clock)
    throttle.should_update()
    clock_val = 6.0
    assert throttle.should_update() is True


def test_random_status_returns_known_string() -> None:
    result = random_status()
    known = [
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
    assert result in known
