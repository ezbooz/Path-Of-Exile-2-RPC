"""Tests for domain port Protocols — all must be @runtime_checkable."""

from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path

from poe2_rpc.domain.events import DomainEvent
from poe2_rpc.domain.locations import Location
from poe2_rpc.domain.models import AFKStatus, InstanceInfo, LevelInfo
from poe2_rpc.domain.ports import (
    EventBus,
    GameDetector,
    LocationCatalogPort,
    LogParser,
    LogStream,
    PresencePublisher,
)


class _ConcreteGameDetector:
    def is_running(self) -> bool:
        return True

    def log_path(self) -> Path:
        return Path("/fake/Client.txt")


class _ConcreteLogStream:
    def lines(self) -> Iterator[str]:
        yield "line"

    def close(self) -> None:
        pass

    def is_closed(self) -> bool:
        return False


class _ConcreteLogParser:
    def parse_level(self, line: str) -> LevelInfo | None:
        return None

    def parse_instance(self, line: str) -> InstanceInfo | None:
        return None

    def parse_local_area_entered(self, line: str) -> str | None:
        return None

    def parse_party_joined(self, line: str) -> str | None:
        return None

    def parse_afk_event(self, line: str) -> AFKStatus | None:
        return None


class _ConcretePresencePublisher:
    async def connect(self) -> None:
        pass

    async def publish(
        self,
        level_info: LevelInfo | None,
        instance_info: InstanceInfo | None,
        *,
        afk_on: bool = False,
        small_image_override: str | None = None,
    ) -> None:
        pass

    def close(self) -> None:
        pass


class _ConcreteEventBus:
    def emit(self, event: DomainEvent) -> None:
        pass

    def subscribe(
        self,
        event_type: type[DomainEvent],
        handler: Callable[[DomainEvent], Awaitable[None]],
    ) -> None:
        pass


class _ConcreteLocationCatalogPort:
    def resolve(self, area_code: str) -> Location:
        return Location(area_code=area_code, display_name=area_code)


def test_game_detector_is_runtime_checkable() -> None:
    assert isinstance(_ConcreteGameDetector(), GameDetector)


def test_log_stream_is_runtime_checkable() -> None:
    assert isinstance(_ConcreteLogStream(), LogStream)


def test_log_parser_is_runtime_checkable() -> None:
    assert isinstance(_ConcreteLogParser(), LogParser)


def test_presence_publisher_is_runtime_checkable() -> None:
    assert isinstance(_ConcretePresencePublisher(), PresencePublisher)


def test_event_bus_is_runtime_checkable() -> None:
    assert isinstance(_ConcreteEventBus(), EventBus)


def test_location_catalog_port_is_runtime_checkable() -> None:
    assert isinstance(_ConcreteLocationCatalogPort(), LocationCatalogPort)
