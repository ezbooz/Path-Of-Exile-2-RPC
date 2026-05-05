"""Domain port Protocols — all runtime_checkable, stdlib + domain imports only."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from poe2_rpc.domain.events import DomainEvent
from poe2_rpc.domain.locations import Location
from poe2_rpc.domain.models import AFKStatus, InstanceInfo, LevelInfo

if TYPE_CHECKING:
    Handler = Callable[[DomainEvent], Awaitable[None]]


@runtime_checkable
class GameDetector(Protocol):
    def is_running(self) -> bool: ...
    def log_path(self) -> Path: ...


@runtime_checkable
class LogStream(Protocol):
    def lines(self) -> Iterator[str]: ...
    def close(self) -> None: ...
    def is_closed(self) -> bool: ...


@runtime_checkable
class LogParser(Protocol):
    def parse_level(self, line: str) -> LevelInfo | None: ...
    def parse_instance(self, line: str) -> InstanceInfo | None: ...
    def parse_local_area_entered(self, line: str) -> str | None: ...
    def parse_party_joined(self, line: str) -> str | None: ...
    def parse_afk_event(self, line: str) -> AFKStatus | None: ...


@runtime_checkable
class PresencePublisher(Protocol):
    async def connect(self) -> None: ...
    async def publish(
        self,
        level_info: LevelInfo | None,
        instance_info: InstanceInfo | None,
        *,
        afk_on: bool = False,
        small_image_override: str | None = None,
    ) -> None: ...
    def close(self) -> None: ...


@runtime_checkable
class EventBus(Protocol):
    def emit(self, event: DomainEvent) -> None: ...
    def subscribe(
        self,
        event_type: type[DomainEvent],
        handler: Callable[[DomainEvent], Awaitable[None]],
    ) -> None: ...


@runtime_checkable
class LocationCatalogPort(Protocol):
    def resolve(self, area_code: str) -> Location: ...


@runtime_checkable
class Settings(Protocol):
    throttle_window_seconds: float
    connect_retry_attempts: int
    publish_retry_attempts: int
