"""Owner detection state machine — frozen VO + transitions.

The orchestrator sees three kinds of signal:
  * `: You have entered <area>` — the LOCAL player crossed an area boundary.
  * `<name> has joined the area.` — a party member is in the same instance.
  * `: <name> (<class>) is now level <n>` — somebody (anybody) levelled.

In a fresh local-area-entered window with NO party members present, the very
next level event is by definition the local player — pin them. If a party
member shows up first, we cannot disambiguate the level event and drop it.
An optional `POE2RPC_CHARACTER_NAME` override short-circuits the state
machine straight to PINNED on the first area entry.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class OwnerState(StrEnum):
    UNKNOWN = "unknown"
    AREA_ENTERED = "area_entered"
    PINNED = "pinned"
    INVALIDATED = "invalidated"


class OwnerTracker(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: OwnerState = OwnerState.UNKNOWN
    pinned_name: str | None = None
    override_name: str | None = None

    @classmethod
    def unknown(cls, override_name: str | None = None) -> OwnerTracker:
        return cls(
            state=OwnerState.UNKNOWN,
            pinned_name=None,
            override_name=override_name,
        )

    def on_local_area_entered(self) -> OwnerTracker:
        if self.override_name is not None:
            return self.model_copy(
                update={
                    "state": OwnerState.PINNED,
                    "pinned_name": self.override_name,
                }
            )
        return self.model_copy(update={"state": OwnerState.AREA_ENTERED, "pinned_name": None})

    def on_party_member_joined(self) -> OwnerTracker:
        if self.state == OwnerState.AREA_ENTERED:
            return self.model_copy(update={"state": OwnerState.INVALIDATED})
        return self

    def on_level_event(self, username: str) -> OwnerTracker:
        if self.state == OwnerState.AREA_ENTERED:
            return self.model_copy(update={"state": OwnerState.PINNED, "pinned_name": username})
        return self

    def should_emit(self, username: str) -> bool:
        if self.state == OwnerState.PINNED:
            return self.pinned_name == username
        if self.state == OwnerState.AREA_ENTERED:
            return True
        return self.state == OwnerState.UNKNOWN
