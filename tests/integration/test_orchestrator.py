"""Integration test: Orchestrator full-flow with fake factory."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

from poe2_rpc.application.bus import AsyncioEventBus
from poe2_rpc.application.handlers import MutableState
from poe2_rpc.application.orchestrator import Orchestrator
from poe2_rpc.application.throttle import PresenceThrottle
from poe2_rpc.domain.locations import Location
from poe2_rpc.domain.models import AFKStatus, InstanceInfo, LevelInfo
from poe2_rpc.domain.ports import LogStream

# --- Fakes ---


class FakeSettings:
    throttle_window_seconds: float = 0.0
    connect_retry_attempts: int = 1
    publish_retry_attempts: int = 1


class FakeGameDetector:
    def __init__(self, path: Path) -> None:
        self._path = path

    def is_running(self) -> bool:
        return True

    def log_path(self) -> Path:
        return self._path


class FakeLogStream:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self._closed = False

    def lines(self) -> Iterator[str]:
        for line in self._lines:
            if self._closed:
                return
            yield line

    def close(self) -> None:
        self._closed = True

    def is_closed(self) -> bool:
        return self._closed


class FakeLogParser:
    def parse_level(self, line: str) -> LevelInfo | None:
        if line.startswith("LEVEL:"):
            parts = line[6:].split(",")
            return LevelInfo(
                username=parts[0],
                base_class=parts[1],
                ascension_class=None,
                level=int(parts[2]),
            )
        return None

    def parse_instance(self, line: str) -> InstanceInfo | None:
        if line.startswith("AREA:"):
            parts = line[5:].split(",")
            return InstanceInfo(
                area_code=parts[0],
                area_display_name=parts[1],
                level=int(parts[2]),
                seed=0,
            )
        return None

    def parse_local_area_entered(self, line: str) -> str | None:
        if line.startswith("LOCAL_AREA:"):
            return line[len("LOCAL_AREA:") :]
        return None

    def parse_party_joined(self, line: str) -> str | None:
        if line.startswith("PARTY:"):
            return line[len("PARTY:") :]
        return None

    def parse_afk_event(self, line: str) -> AFKStatus | None:
        if line.startswith("AFK_ON:"):
            return AFKStatus(mode="AFK", on=True, autoreply=line[len("AFK_ON:") :])
        if line == "AFK_OFF":
            return AFKStatus(mode="AFK", on=False, autoreply=None)
        return None


class FakePresencePublisher:
    def __init__(self) -> None:
        self.published: list[tuple[LevelInfo | None, InstanceInfo | None]] = []
        self.publish_kwargs: list[dict[str, object]] = []
        self.connected: bool = False

    async def connect(self) -> None:
        self.connected = True

    async def publish(
        self,
        level_info: LevelInfo | None,
        instance_info: InstanceInfo | None,
        *,
        afk_on: bool = False,
        small_image_override: str | None = None,
    ) -> None:
        self.published.append((level_info, instance_info))
        self.publish_kwargs.append({"afk_on": afk_on, "small_image_override": small_image_override})

    def close(self) -> None:
        pass


class FakeLocationCatalog:
    def resolve(self, area_code: str) -> Location:
        return Location(area_code=area_code, display_name=area_code)


def _make_orchestrator(
    *,
    stream_lines: list[str],
    publisher: FakePresencePublisher | None = None,
    received_paths: list[Path] | None = None,
) -> tuple[Orchestrator, FakePresencePublisher]:
    pub = publisher or FakePresencePublisher()
    log_path = Path("/fake/Client.txt")

    def factory(path: Path, loop: asyncio.AbstractEventLoop) -> LogStream:
        if received_paths is not None:
            received_paths.append(path)
        return FakeLogStream(stream_lines)

    orch = Orchestrator(
        detector=FakeGameDetector(log_path),
        parser=FakeLogParser(),
        publisher=pub,
        catalog=FakeLocationCatalog(),
        bus=AsyncioEventBus(),
        log_stream_factory=factory,
        throttle=PresenceThrottle(interval=0.0),
        current_state=MutableState(),
        settings=FakeSettings(),
    )
    return orch, pub


# --- Tests ---


def test_orchestrator_emits_level_event_and_publishes() -> None:
    """Orchestrator wires bus/handlers: a LEVEL log line triggers presence publish."""
    orch, publisher = _make_orchestrator(stream_lines=["LEVEL:Hero,Warrior,10"])
    orch.run_once()

    assert len(publisher.published) == 1
    level_info, _ = publisher.published[0]
    assert level_info is not None
    assert level_info.username == "Hero"
    assert level_info.level == 10


def test_orchestrator_emits_area_event_and_publishes() -> None:
    """Orchestrator wires bus/handlers: an AREA log line triggers presence publish."""
    orch, publisher = _make_orchestrator(stream_lines=["AREA:G1_1,Act 1,5"])
    orch.run_once()

    assert len(publisher.published) == 1
    _, instance_info = publisher.published[0]
    assert instance_info is not None
    assert instance_info.area_code == "G1_1"


def test_orchestrator_resolves_area_display_name_via_catalog() -> None:
    """panvex-00o: orchestrator must call catalog.resolve() so handlers see resolved names."""

    class ResolvingCatalog:
        def resolve(self, area_code: str) -> Location:
            return Location(area_code=area_code, display_name="The Riverbank")

    pub = FakePresencePublisher()
    log_path = Path("/fake/Client.txt")

    def factory(path: Path, loop: asyncio.AbstractEventLoop) -> LogStream:
        return FakeLogStream(["AREA:G1_1,raw_internal_code,5"])

    orch = Orchestrator(
        detector=FakeGameDetector(log_path),
        parser=FakeLogParser(),
        publisher=pub,
        catalog=ResolvingCatalog(),
        bus=AsyncioEventBus(),
        log_stream_factory=factory,
        throttle=PresenceThrottle(interval=0.0),
        current_state=MutableState(),
        settings=FakeSettings(),
    )
    orch.run_once()

    assert len(pub.published) == 1
    _, instance_info = pub.published[0]
    assert instance_info is not None
    assert instance_info.area_code == "G1_1"
    assert instance_info.area_display_name == "The Riverbank"


def test_orchestrator_factory_called_with_log_path() -> None:
    """Factory receives the path from GameDetector.log_path()."""
    received_paths: list[Path] = []
    orch, _ = _make_orchestrator(stream_lines=[], received_paths=received_paths)
    orch.run_once()

    assert received_paths == [Path("/fake/Client.txt")]


def test_orchestrator_graceful_shutdown_on_cancelled_error() -> None:
    """run_once() exits cleanly on CancelledError; publisher.close() is called."""
    pub = FakePresencePublisher()
    closed: list[bool] = []
    original_close = pub.close

    def tracking_close() -> None:
        closed.append(True)
        original_close()

    pub.close = tracking_close  # type: ignore[method-assign]

    def factory(path: Path, loop: asyncio.AbstractEventLoop) -> LogStream:
        raise asyncio.CancelledError()

    orch = Orchestrator(
        detector=FakeGameDetector(Path("/fake/Client.txt")),
        parser=FakeLogParser(),
        publisher=pub,
        catalog=FakeLocationCatalog(),
        bus=AsyncioEventBus(),
        log_stream_factory=factory,
        throttle=PresenceThrottle(interval=0.0),
        current_state=MutableState(),
        settings=FakeSettings(),
    )

    orch.run_once()  # should not raise

    assert closed == [True]
