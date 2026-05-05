"""Frozen pydantic v2 domain event hierarchy."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from poe2_rpc.domain.models import AFKStatus, InstanceInfo, LevelInfo


class DomainEvent(BaseModel):
    model_config = ConfigDict(frozen=True)


class GameStarted(DomainEvent):
    log_path: Path


class GameStopped(DomainEvent):
    pass


class CharacterLevelChanged(DomainEvent):
    level_info: LevelInfo


class AreaEntered(DomainEvent):
    instance_info: InstanceInfo


class LocalAreaEntered(DomainEvent):
    """Emitted on `: You have entered <area>.` — signals the local player crossed a boundary."""

    area_name: str


class PartyMemberJoined(DomainEvent):
    """Emitted on `<name> has joined the area.` — signals another player is in the same instance."""

    name: str


class AFKStatusChanged(DomainEvent):
    """Emitted on `: AFK mode is now ON. Autoreply "..."` and OFF variants (also DND)."""

    status: AFKStatus
