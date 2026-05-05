"""AFK status tests — parser, presence kwargs, and snapshot/restore handler semantics."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from poe2_rpc.application.handlers import MutableState, on_afk_changed
from poe2_rpc.domain.events import AFKStatusChanged
from poe2_rpc.domain.models import AFKStatus, InstanceInfo, LevelInfo
from poe2_rpc.infrastructure.parsing import parse_afk_event_line
from poe2_rpc.infrastructure.presence import PypresencePublisher


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (
            '2026-05-05 12:00:00 12345 [INFO Client 1234] : AFK mode is now ON. Autoreply "brb"',
            AFKStatus(mode="AFK", on=True, autoreply="brb"),
        ),
        (
            "2026-05-05 12:00:00 12345 [INFO Client 1234] : AFK mode is now OFF",
            AFKStatus(mode="AFK", on=False, autoreply=None),
        ),
        (
            '2026-05-05 12:00:00 12345 [INFO Client 1234] : DND mode is now ON. Autoreply "busy"',
            AFKStatus(mode="DND", on=True, autoreply="busy"),
        ),
        (
            "2026-05-05 12:00:00 12345 [INFO Client 1234] : DND mode is now OFF",
            AFKStatus(mode="DND", on=False, autoreply=None),
        ),
    ],
)
def test_parse_afk_event_table(line: str, expected: AFKStatus) -> None:
    assert parse_afk_event_line(line) == expected


def test_parse_afk_event_returns_none_for_unrelated_line() -> None:
    assert parse_afk_event_line("2026-05-05 12:00:00 [INFO Client 1234] : Connected to ...") is None


def test_presence_kwargs_afk_on_appends_afk_suffix_and_swaps_small_image() -> None:
    li = LevelInfo(username="Alice", base_class="Witch", ascension_class=None, level=10)
    ii = InstanceInfo(level=5, area_code="G1_1", area_display_name="Lioneye's Watch", seed=1)
    kwargs = PypresencePublisher._build_update_kwargs(
        li,
        ii,
        afk_on=True,
        small_image_override="afk",
    )
    assert kwargs["small_image"] == "afk"
    assert kwargs["state"].endswith("[AFK]")


def test_presence_kwargs_afk_off_with_restore_override() -> None:
    """OFF with explicit override restores the captured snapshot, not the recomputed default."""
    li = LevelInfo(username="Alice", base_class="Witch", ascension_class=None, level=10)
    ii = InstanceInfo(level=5, area_code="G1_1", area_display_name="Lioneye's Watch", seed=1)
    kwargs = PypresencePublisher._build_update_kwargs(
        li,
        ii,
        afk_on=False,
        small_image_override="witch",
    )
    assert kwargs["small_image"] == "witch"
    assert "[AFK]" not in kwargs["state"]


def test_afk_restore_after_level_during_afk() -> None:
    """Snapshot survives a level/ascendency change inside the AFK window.

    1. Witch lvl 10 → small_image "witch".
    2. AFK ON → snapshot "witch".
    3. Mid-AFK level/ascendency change to Infernalist lvl 11.
    4. AFK OFF → restore must use snapshot "witch", NOT recomputed "infernalist".
    """
    state = MutableState()
    state.level_info = LevelInfo(
        username="Alice", base_class="Witch", ascension_class=None, level=10
    )
    state.instance_info = InstanceInfo(
        level=5, area_code="G1_1", area_display_name="Lioneye's Watch", seed=1
    )
    publisher = AsyncMock()

    asyncio.run(
        on_afk_changed(
            AFKStatusChanged(status=AFKStatus(mode="AFK", on=True)),
            publisher=publisher,
            current_state=state,
        )
    )
    assert state.prior_small_image == "witch"
    publisher.publish.assert_awaited_with(
        state.level_info,
        state.instance_info,
        afk_on=True,
        small_image_override="afk",
    )
    publisher.publish.reset_mock()

    state.level_info = LevelInfo(
        username="Alice",
        base_class="Witch",
        ascension_class="Infernalist",
        level=11,
    )

    asyncio.run(
        on_afk_changed(
            AFKStatusChanged(status=AFKStatus(mode="AFK", on=False)),
            publisher=publisher,
            current_state=state,
        )
    )
    publisher.publish.assert_awaited_with(
        state.level_info,
        state.instance_info,
        afk_on=False,
        small_image_override="witch",
    )
    assert state.prior_small_image is None


def test_afk_on_off_with_no_prior_level_info() -> None:
    """AFK ON arrives BEFORE any 'is now level' event — handler must not crash."""
    state = MutableState()
    state.instance_info = None
    publisher = AsyncMock()

    asyncio.run(
        on_afk_changed(
            AFKStatusChanged(status=AFKStatus(mode="AFK", on=True)),
            publisher=publisher,
            current_state=state,
        )
    )
    assert state.prior_small_image is None
    publisher.publish.assert_awaited_with(
        None,
        None,
        afk_on=True,
        small_image_override="afk",
    )
    publisher.publish.reset_mock()

    asyncio.run(
        on_afk_changed(
            AFKStatusChanged(status=AFKStatus(mode="AFK", on=False)),
            publisher=publisher,
            current_state=state,
        )
    )
    publisher.publish.assert_awaited_with(
        None,
        None,
        afk_on=False,
        small_image_override=None,
    )
