"""Application-layer event bus — pure asyncio, no infrastructure imports."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable

import structlog

from poe2_rpc.domain.events import DomainEvent

Handler = Callable[[DomainEvent], Awaitable[None]]

_log = structlog.get_logger(__name__)


class AsyncioEventBus:
    def __init__(self) -> None:
        self._registry: dict[type[DomainEvent], list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: type[DomainEvent], handler: Handler) -> None:
        self._registry[event_type].append(handler)

    def emit(self, event: DomainEvent) -> None:
        asyncio.get_event_loop().run_until_complete(self.publish(event))

    async def publish(self, event: DomainEvent) -> None:
        handlers = self._registry.get(type(event), [])
        results = await asyncio.gather(*(h(event) for h in handlers), return_exceptions=True)
        for result in results:
            if isinstance(result, BaseException):
                _log.error("event_handler_error", event_type=type(event).__name__, exc_info=result)
