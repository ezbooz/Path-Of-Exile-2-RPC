"""Tests for sync close-stream design: Orchestrator.stop() unblocks run_once()."""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Iterator
from pathlib import Path

from poe2_rpc.application.bus import AsyncioEventBus
from poe2_rpc.application.handlers import MutableState
from poe2_rpc.application.orchestrator import Orchestrator
from poe2_rpc.application.throttle import PresenceThrottle
from poe2_rpc.domain.locations import Location
from poe2_rpc.domain.models import AFKStatus, InstanceInfo, LevelInfo
from poe2_rpc.domain.ports import LogStream


class _BlockingLogStream:
    """Yields one line, then blocks on a threading.Event until close() fires."""

    def __init__(self) -> None:
        self._closed = threading.Event()

    def lines(self) -> Iterator[str]:
        yield "first-line"
        self._closed.wait(timeout=5.0)

    def close(self) -> None:
        self._closed.set()

    def is_closed(self) -> bool:
        return self._closed.is_set()


class _StubSettings:
    throttle_window_seconds: float = 0.0
    connect_retry_attempts: int = 1
    publish_retry_attempts: int = 1


class _StubDetector:
    def is_running(self) -> bool:
        return True

    def log_path(self) -> Path:
        return Path("/fake/Client.txt")


class _StubParser:
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


class _StubPublisher:
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


class _StubCatalog:
    def resolve(self, area_code: str) -> Location:
        return Location(area_code=area_code, display_name=area_code)


def _build_orchestrator(stream: LogStream) -> Orchestrator:
    def factory(_path: Path, _loop: asyncio.AbstractEventLoop) -> LogStream:
        return stream

    return Orchestrator(
        detector=_StubDetector(),
        parser=_StubParser(),
        publisher=_StubPublisher(),
        catalog=_StubCatalog(),
        bus=AsyncioEventBus(),
        log_stream_factory=factory,
        throttle=PresenceThrottle(interval=0.0),
        current_state=MutableState(),
        settings=_StubSettings(),
    )


def test_orchestrator_stop_closes_stream_within_1s() -> None:
    """Tray Quit thread → orch.stop() → stream.close() → for-loop exits → join."""
    stream = _BlockingLogStream()
    orch = _build_orchestrator(stream)

    worker = threading.Thread(target=orch.run_once, daemon=True)
    worker.start()
    time.sleep(0.1)
    orch.stop()
    worker.join(timeout=1.0)

    assert not worker.is_alive(), "stop() did not terminate run_once within 1s"
    assert stream.is_closed()


def test_log_stream_close_is_idempotent(tmp_path: Path) -> None:
    """Double-close (rapid tray quit) must not raise."""
    from poe2_rpc.infrastructure.log_stream import WatchdogLogStream
    from poe2_rpc.infrastructure.settings import AppSettings

    log_file = tmp_path / "Client.txt"
    log_file.write_text("")
    loop = asyncio.new_event_loop()
    try:
        stream = WatchdogLogStream(log_file, AppSettings(), loop)
        stream.start()
        stream.close()
        stream.close()
        assert stream.is_closed() is True
    finally:
        loop.close()


def test_orchestrator_stop_when_no_stream_active_is_noop() -> None:
    """stop() before any run_once() must not raise — _current_stream is None."""
    stream = _BlockingLogStream()
    orch = _build_orchestrator(stream)
    orch.stop()
    assert orch._current_stream is None
