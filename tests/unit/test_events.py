"""Tests for domain event hierarchy."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from poe2_rpc.domain.events import (
    AreaEntered,
    CharacterLevelChanged,
    DomainEvent,
    GameStarted,
    GameStopped,
)
from poe2_rpc.domain.models import InstanceInfo, LevelInfo


def _level_info() -> LevelInfo:
    return LevelInfo(username="Exile", base_class="Mercenary", ascension_class=None, level=1)


def _instance_info() -> InstanceInfo:
    return InstanceInfo(area_code="G1_4", area_display_name="Test Zone", level=5, seed=99)


def test_game_started_is_frozen() -> None:
    event = GameStarted(log_path=Path("/tmp/Client.txt"))
    with pytest.raises((ValidationError, TypeError)):
        event.log_path = Path("/tmp/other.txt")  # type: ignore[misc]


def test_game_started_eq_by_value() -> None:
    p = Path("/tmp/Client.txt")
    assert GameStarted(log_path=p) == GameStarted(log_path=p)


def test_character_level_changed_holds_level_info() -> None:
    info = _level_info()
    event = CharacterLevelChanged(level_info=info)
    assert event.level_info == info


def test_area_entered_holds_instance_info() -> None:
    info = _instance_info()
    event = AreaEntered(instance_info=info)
    assert event.instance_info == info


def test_game_stopped_is_singleton_like() -> None:
    assert GameStopped() == GameStopped()


def test_events_share_base() -> None:
    assert isinstance(GameStarted(log_path=Path("/tmp/Client.txt")), DomainEvent)
    assert isinstance(GameStopped(), DomainEvent)
    assert isinstance(CharacterLevelChanged(level_info=_level_info()), DomainEvent)
    assert isinstance(AreaEntered(instance_info=_instance_info()), DomainEvent)
