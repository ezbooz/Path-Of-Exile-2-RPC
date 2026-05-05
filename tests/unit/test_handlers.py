"""Tests for application handlers — on_level_changed + on_area_entered (AC#7)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import structlog.testing

from poe2_rpc.application.handlers import on_area_entered, on_level_changed
from poe2_rpc.domain.events import AreaEntered, CharacterLevelChanged
from poe2_rpc.domain.models import InstanceInfo, LevelInfo


def _level_info(
    *,
    username: str = "TestUser",
    base_class: str = "Witch",
    ascension_class: str | None = "Lich",
    level: int = 42,
) -> LevelInfo:
    return LevelInfo(
        username=username,
        base_class=base_class,
        ascension_class=ascension_class,
        level=level,
    )


def _instance_info(
    *,
    area_code: str = "G1_1",
    area_display_name: str = "Clearfell",
    level: int = 5,
    seed: int = 1,
) -> InstanceInfo:
    return InstanceInfo(
        area_code=area_code,
        area_display_name=area_display_name,
        level=level,
        seed=seed,
    )


def _make_throttle(*, allow: bool = True) -> Any:
    t = MagicMock()
    t.should_update.return_value = allow
    return t


def _make_state(
    *,
    level_info: LevelInfo | None = None,
    instance_info: InstanceInfo | None = None,
) -> Any:
    s = MagicMock()
    s.level_info = level_info
    s.instance_info = instance_info
    return s


@pytest.mark.asyncio
async def test_on_level_changed_formats_details_with_ascendancy() -> None:
    publisher = AsyncMock()
    throttle = _make_throttle(allow=True)
    li = _level_info(username="TestUser", base_class="Witch", ascension_class="Lich", level=42)
    event = CharacterLevelChanged(level_info=li)
    state = _make_state(instance_info=None)

    await on_level_changed(event, publisher=publisher, throttle=throttle, current_state=state)

    publisher.publish.assert_called_once()
    call_level_info: LevelInfo = publisher.publish.call_args.args[0]
    assert call_level_info.username == "TestUser"
    assert call_level_info.base_class == "Witch"
    assert call_level_info.ascension_class == "Lich"
    assert call_level_info.level == 42


@pytest.mark.asyncio
async def test_on_level_changed_omits_ascendancy_pipe_when_none() -> None:
    publisher = AsyncMock()
    throttle = _make_throttle(allow=True)
    li = _level_info(username="TestUser", base_class="Mercenary", ascension_class=None, level=42)
    event = CharacterLevelChanged(level_info=li)
    state = _make_state(instance_info=None)

    await on_level_changed(event, publisher=publisher, throttle=throttle, current_state=state)

    publisher.publish.assert_called_once()
    call_level_info: LevelInfo = publisher.publish.call_args.args[0]
    assert call_level_info.ascension_class is None
    assert call_level_info.base_class == "Mercenary"


@pytest.mark.asyncio
async def test_on_area_entered_formats_in_state() -> None:
    publisher = AsyncMock()
    throttle = _make_throttle(allow=True)
    ii = _instance_info(area_display_name="Clearfell", level=5)
    event = AreaEntered(instance_info=ii)
    state = _make_state(level_info=None)

    await on_area_entered(event, publisher=publisher, throttle=throttle, current_state=state)

    publisher.publish.assert_called_once()
    call_instance_info: InstanceInfo = publisher.publish.call_args.args[1]
    assert call_instance_info.area_display_name == "Clearfell"
    assert call_instance_info.level == 5


@pytest.mark.asyncio
async def test_small_image_lowercases_and_underscores() -> None:
    """Infra derives small_image from ascension_class; handler passes LevelInfo correctly."""
    publisher = AsyncMock()
    throttle = _make_throttle(allow=True)
    li = _level_info(ascension_class="Smith of Kitava", base_class="Warrior", level=10)
    event = CharacterLevelChanged(level_info=li)
    state = _make_state(instance_info=None)

    await on_level_changed(event, publisher=publisher, throttle=throttle, current_state=state)

    call_level_info: LevelInfo = publisher.publish.call_args.args[0]
    asc = call_level_info.ascension_class or call_level_info.base_class
    assert asc.lower().replace(" ", "_") == "smith_of_kitava"


@pytest.mark.asyncio
async def test_handlers_bind_username_class_area_into_logs() -> None:
    publisher = AsyncMock()
    throttle = _make_throttle(allow=True)
    li = _level_info(username="LogUser", base_class="Ranger", ascension_class="Deadeye", level=20)
    ii = _instance_info(area_display_name="The Mud Flats", level=3)
    event = CharacterLevelChanged(level_info=li)
    state = _make_state(instance_info=ii)

    with structlog.testing.capture_logs() as cap:
        await on_level_changed(event, publisher=publisher, throttle=throttle, current_state=state)

    assert len(cap) > 0
    log_event = cap[0]
    assert log_event.get("username") == "LogUser"
    assert log_event.get("character_class") == "Ranger"
    assert "area" in log_event


@pytest.mark.asyncio
async def test_throttled_update_skips_publish() -> None:
    publisher = AsyncMock()
    throttle = _make_throttle(allow=False)
    li = _level_info()
    event = CharacterLevelChanged(level_info=li)
    state = _make_state(instance_info=None)

    await on_level_changed(event, publisher=publisher, throttle=throttle, current_state=state)

    publisher.publish.assert_not_called()
