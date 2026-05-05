"""Application orchestrator — composes bus, throttle, and handlers into a runnable loop.

Principle 4: zero poe2_rpc.infrastructure.* imports. The log stream is created
via an injected factory so the composition root (cli.py) owns the concrete type.
"""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable
from pathlib import Path

import structlog

from poe2_rpc.application.bus import AsyncioEventBus
from poe2_rpc.application.handlers import (
    MutableState,
    on_afk_changed,
    on_area_entered,
    on_level_changed,
    on_local_area_entered,
    on_party_joined,
)
from poe2_rpc.application.throttle import PresenceThrottle
from poe2_rpc.domain.events import (
    AFKStatusChanged,
    AreaEntered,
    CharacterLevelChanged,
    LocalAreaEntered,
    PartyMemberJoined,
)
from poe2_rpc.domain.ports import (
    GameDetector,
    LocationCatalogPort,
    LogParser,
    LogStream,
    PresencePublisher,
    Settings,
)

_log = structlog.get_logger(__name__)

LogStreamFactory = Callable[[Path, asyncio.AbstractEventLoop], LogStream]


class Orchestrator:
    def __init__(
        self,
        *,
        detector: GameDetector,
        parser: LogParser,
        publisher: PresencePublisher,
        catalog: LocationCatalogPort,
        bus: AsyncioEventBus,
        log_stream_factory: LogStreamFactory,
        throttle: PresenceThrottle,
        current_state: MutableState,
        settings: Settings,
    ) -> None:
        self._detector = detector
        self._parser = parser
        self._publisher = publisher
        self._catalog = catalog
        self._bus = bus
        self._factory = log_stream_factory
        self._throttle = throttle
        self._current_state = current_state
        self._settings = settings
        self._current_stream: LogStream | None = None
        self._subscribe_handlers()

    def _subscribe_handlers(self) -> None:
        self._bus.subscribe(
            CharacterLevelChanged,
            functools.partial(
                on_level_changed,
                publisher=self._publisher,
                throttle=self._throttle,
                current_state=self._current_state,
            ),
        )
        self._bus.subscribe(
            AreaEntered,
            functools.partial(
                on_area_entered,
                publisher=self._publisher,
                throttle=self._throttle,
                current_state=self._current_state,
            ),
        )
        self._bus.subscribe(
            LocalAreaEntered,
            functools.partial(on_local_area_entered, current_state=self._current_state),
        )
        self._bus.subscribe(
            PartyMemberJoined,
            functools.partial(on_party_joined, current_state=self._current_state),
        )
        self._bus.subscribe(
            AFKStatusChanged,
            functools.partial(
                on_afk_changed,
                publisher=self._publisher,
                current_state=self._current_state,
            ),
        )

    def run_once(self) -> None:
        """Process all lines from one log stream pass. Handles CancelledError/KeyboardInterrupt."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._publisher.connect())
            log_path = self._detector.log_path()
            stream = self._factory(log_path, loop)
            self._current_stream = stream
            try:
                for line in stream.lines():
                    if stream.is_closed():
                        break
                    if not line:
                        continue
                    local_area = self._parser.parse_local_area_entered(line)
                    if local_area is not None:
                        self._bus.emit(LocalAreaEntered(area_name=local_area))
                        continue
                    party_name = self._parser.parse_party_joined(line)
                    if party_name is not None:
                        self._bus.emit(PartyMemberJoined(name=party_name))
                        continue
                    afk_status = self._parser.parse_afk_event(line)
                    if afk_status is not None:
                        self._bus.emit(AFKStatusChanged(status=afk_status))
                        continue
                    level_info = self._parser.parse_level(line)
                    if level_info is not None:
                        self._bus.emit(CharacterLevelChanged(level_info=level_info))
                        continue
                    instance_info = self._parser.parse_instance(line)
                    if instance_info is not None:
                        location = self._catalog.resolve(instance_info.area_code)
                        resolved = instance_info.model_copy(
                            update={"area_display_name": location.display_name}
                        )
                        self._bus.emit(AreaEntered(instance_info=resolved))
            finally:
                stream.close()
                self._current_stream = None
        except (asyncio.CancelledError, KeyboardInterrupt):
            _log.info("orchestrator_shutdown")
        finally:
            self._publisher.close()
            loop.close()
            asyncio.set_event_loop(None)

    def run(self) -> None:
        """Continuous monitor loop — runs until cancelled or interrupted."""
        try:
            while True:
                if self._current_stream is not None and self._current_stream.is_closed():
                    break
                self.run_once()
                if self._current_stream is not None and self._current_stream.is_closed():
                    break
        except (asyncio.CancelledError, KeyboardInterrupt):
            _log.info("orchestrator_stopped")

    def stop(self) -> None:
        """Thread-safe shutdown signal — called from the tray Quit thread.

        Closes the active stream (if any). The sync ``for line in stream.lines()``
        loop exits cleanly on the next ``is_closed()`` check, then the ``finally``
        block tears down the publisher and event loop.
        """
        stream = self._current_stream
        if stream is not None:
            stream.close()
