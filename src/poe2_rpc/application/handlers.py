"""Application-layer event handlers — pure application code, no infrastructure imports."""

from __future__ import annotations

import structlog
import structlog.contextvars

from poe2_rpc.application.throttle import PresenceThrottle
from poe2_rpc.domain.events import (
    AFKStatusChanged,
    AreaEntered,
    CharacterLevelChanged,
    LocalAreaEntered,
    PartyMemberJoined,
)
from poe2_rpc.domain.models import InstanceInfo, LevelInfo
from poe2_rpc.domain.owner import OwnerState, OwnerTracker
from poe2_rpc.domain.ports import PresencePublisher

_log = structlog.get_logger(__name__)

_AFK_SMALL_IMAGE = "afk"


class MutableState:
    """Shared mutable state threaded through handlers so each can see the other's last value."""

    def __init__(self, owner_tracker: OwnerTracker | None = None) -> None:
        self.level_info: LevelInfo | None = None
        self.instance_info: InstanceInfo | None = None
        self.owner_tracker: OwnerTracker = (
            owner_tracker if owner_tracker is not None else OwnerTracker.unknown()
        )
        self.afk_on: bool = False
        # Snapshot of small_image at the moment AFK turned ON; restored on OFF.
        # Decoupled from level_info so a level-up *during* AFK doesn't leak
        # the new ascendency into the post-AFK presence.
        self.prior_small_image: str | None = None


def _format_details(level_info: LevelInfo) -> str:
    details = f"{level_info.username} ({level_info.base_class}"
    if level_info.ascension_class is not None:
        details += f" | {level_info.ascension_class}"
    details += f" - Lvl {level_info.level})"
    return details


def _small_image_for(level_info: LevelInfo | None) -> str | None:
    """Mirror PypresencePublisher._build_update_kwargs small_image derivation."""
    if level_info is None:
        return None
    asc = level_info.ascension_class or level_info.base_class
    return asc.lower().replace(" ", "_")


def _afk_publish_kwargs(state: MutableState) -> dict[str, object]:
    """When AFK is on, every publish must keep the [AFK] suffix and afk small_image."""
    if state.afk_on:
        return {"afk_on": True, "small_image_override": _AFK_SMALL_IMAGE}
    return {"afk_on": False, "small_image_override": None}


async def on_level_changed(
    event: CharacterLevelChanged,
    *,
    publisher: PresencePublisher,
    throttle: PresenceThrottle,
    current_state: MutableState,
) -> None:
    li = event.level_info

    current_state.owner_tracker = current_state.owner_tracker.on_level_event(li.username)

    if not current_state.owner_tracker.should_emit(li.username):
        _log.debug(
            "level_event_dropped_non_owner",
            username=li.username,
            owner_state=current_state.owner_tracker.state.value,
            pinned_name=current_state.owner_tracker.pinned_name,
        )
        return

    current_state.level_info = li

    structlog.contextvars.bind_contextvars(
        username=li.username,
        character_class=li.base_class,
        area=current_state.instance_info.area_display_name if current_state.instance_info else "",
    )

    if not throttle.should_update():
        return

    area = current_state.instance_info.area_display_name if current_state.instance_info else ""
    _log.info(
        "level_changed",
        username=li.username,
        character_class=li.base_class,
        area=area,
        level=li.level,
        details=_format_details(li),
    )
    await publisher.publish(
        li,
        current_state.instance_info,
        **_afk_publish_kwargs(current_state),  # type: ignore[arg-type]
    )


async def on_area_entered(
    event: AreaEntered,
    *,
    publisher: PresencePublisher,
    throttle: PresenceThrottle,
    current_state: MutableState,
) -> None:
    ii = event.instance_info
    current_state.instance_info = ii

    structlog.contextvars.bind_contextvars(
        username=current_state.level_info.username if current_state.level_info else "",
        character_class=current_state.level_info.base_class if current_state.level_info else "",
        area=ii.area_display_name,
    )

    if not throttle.should_update():
        return

    username = current_state.level_info.username if current_state.level_info else ""
    character_class = current_state.level_info.base_class if current_state.level_info else ""
    _log.info(
        "area_entered",
        username=username,
        character_class=character_class,
        area=ii.area_display_name,
        area_level=ii.level,
    )
    await publisher.publish(
        current_state.level_info,
        ii,
        **_afk_publish_kwargs(current_state),  # type: ignore[arg-type]
    )


async def on_local_area_entered(
    event: LocalAreaEntered,
    *,
    current_state: MutableState,
) -> None:
    """`: You have entered <area>` opens a fresh owner-detection window."""
    current_state.owner_tracker = current_state.owner_tracker.on_local_area_entered()
    _log.debug(
        "local_area_entered",
        area_name=event.area_name,
        owner_state=current_state.owner_tracker.state.value,
        pinned_name=current_state.owner_tracker.pinned_name,
    )


async def on_party_joined(
    event: PartyMemberJoined,
    *,
    current_state: MutableState,
) -> None:
    """A party member entering the same instance invalidates an unpinned window."""
    prior = current_state.owner_tracker
    current_state.owner_tracker = prior.on_party_member_joined()
    if prior.state == OwnerState.PINNED:
        _log.warning(
            "party_member_joined_while_pinned",
            party_member=event.name,
            pinned_name=prior.pinned_name,
        )
    else:
        _log.debug(
            "party_member_joined",
            party_member=event.name,
            owner_state=current_state.owner_tracker.state.value,
        )


async def on_afk_changed(
    event: AFKStatusChanged,
    *,
    publisher: PresencePublisher,
    current_state: MutableState,
) -> None:
    """`: AFK mode is now ON|OFF` (and DND variants).

    On ON: snapshot the current small_image (derived from level_info) so a
    subsequent level-up during the AFK window cannot leak its new icon.
    On OFF: restore the snapshot via small_image_override; a None snapshot
    (no level seen before AFK) cleanly omits the override.
    """
    status = event.status
    structlog.contextvars.bind_contextvars(afk=status.on, afk_mode=status.mode)

    if status.on:
        current_state.prior_small_image = _small_image_for(current_state.level_info)
        current_state.afk_on = True
        _log.info(
            "afk_on",
            mode=status.mode,
            snapshot=current_state.prior_small_image,
            autoreply=status.autoreply,
        )
        await publisher.publish(
            current_state.level_info,
            current_state.instance_info,
            afk_on=True,
            small_image_override=_AFK_SMALL_IMAGE,
        )
        return

    current_state.afk_on = False
    restore = current_state.prior_small_image  # None when no level seen pre-AFK
    _log.info("afk_off", mode=status.mode, restored=restore)
    await publisher.publish(
        current_state.level_info,
        current_state.instance_info,
        afk_on=False,
        small_image_override=restore,
    )
    # Clear the snapshot AFTER the restore publish so a future AFK-ON that
    # arrives before any new level event can capture a fresh snapshot.
    current_state.prior_small_image = None
