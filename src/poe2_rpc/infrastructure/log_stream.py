"""WatchdogLogStream — file-tail adapter using watchdog with thread-safety contract.

The watchdog observer runs on its own thread. It MUST NOT touch the asyncio Queue
directly. All enqueues are scheduled via loop.call_soon_threadsafe so they execute
on the event-loop thread, keeping the Queue single-threaded.
"""

from __future__ import annotations

import asyncio
import re
import threading
import time
from asyncio import AbstractEventLoop, QueueFull
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from poe2_rpc.domain.exceptions import LogStreamStalledError

if TYPE_CHECKING:
    from poe2_rpc.infrastructure.settings import AppSettings

log = structlog.get_logger(__name__)

# Byte-identical to main.py:273-274 — Principle 5 forbids any change.
_REGEX_LEVEL = re.compile(r": (\w+) \(([\w\s]+)\) is now level (\d+)")
_REGEX_INSTANCE = re.compile(r'Generating level (\d+) area "([^"]+)" with seed (\d+)')

_BACKOFF_CAP = 0.5
_BACKOFF_INITIAL = 0.05


def _classify_line(line: str) -> bool:
    """Return True if the line matches a domain-relevant regex."""
    return bool(_REGEX_LEVEL.search(line) or _REGEX_INSTANCE.search(line))


class _LogFileHandler(FileSystemEventHandler):
    """Watchdog handler — runs on the observer thread."""

    def __init__(self, stream: WatchdogLogStream) -> None:
        super().__init__()
        self._stream = stream

    def on_modified(self, _event: FileSystemEvent) -> None:
        self._stream._read_new_lines()


class WatchdogLogStream:
    """Tails a log file using watchdog; enqueues lines safely to the asyncio loop."""

    def __init__(
        self,
        log_path: Path,
        settings: AppSettings,
        loop: AbstractEventLoop,
    ) -> None:
        self._log_path = log_path
        self._settings = settings
        self._loop = loop
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=settings.log_stream_queue_maxsize)
        self._cursor: int = 0
        self._observer = Observer()
        self._handler = _LogFileHandler(self)
        self.dropped_non_domain_count: int = 0
        self._last_drop_warn_time: float = 0.0
        self._is_closed: bool = False
        self._close_lock = threading.Lock()

        # Seek to EOF on start
        if log_path.exists():
            self._cursor = log_path.stat().st_size

        self._observer.schedule(self._handler, str(log_path.parent), recursive=False)

    def start(self) -> None:
        self._observer.start()

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join()

    def close(self) -> None:
        """Idempotent, thread-safe close. Safe to call from any thread."""
        with self._close_lock:
            if self._is_closed:
                return
            self._is_closed = True
        self._observer.stop()
        self._observer.join()
        # Wake any pending await on the queue so consumers can observe is_closed():
        self._loop.call_soon_threadsafe(self._queue.put_nowait, "")

    def is_closed(self) -> bool:
        return self._is_closed

    def _read_new_lines(self) -> None:
        """Called from the watchdog observer thread. Reads new bytes and schedules enqueues."""
        try:
            current_size = self._log_path.stat().st_size
        except FileNotFoundError:
            return

        # File rotation: cursor beyond EOF → reset
        if self._cursor > current_size:
            self._cursor = 0

        if self._cursor == current_size:
            return

        with open(self._log_path, "rb") as f:
            f.seek(self._cursor)
            raw = f.read(current_size - self._cursor)

        self._cursor += len(raw)
        text = raw.decode("utf-8", errors="replace")
        lines = text.split("\n")

        for line in lines:
            stripped = line.rstrip("\r")
            if not stripped:
                continue
            # Schedule enqueue on the asyncio loop thread — NEVER touch queue directly here.
            self._loop.call_soon_threadsafe(self._enqueue, stripped)

    def _enqueue(
        self,
        line: str,
        _started_at: float | None = None,
        _delay: float = _BACKOFF_INITIAL,
    ) -> None:
        """Runs on the asyncio loop thread. Enqueues line; retries domain lines on QueueFull."""
        try:
            self._queue.put_nowait(line)
        except QueueFull:
            if _classify_line(line):
                started_at = _started_at if _started_at is not None else time.monotonic()
                deadline = self._settings.log_stream_enqueue_deadline_seconds
                if time.monotonic() - started_at >= deadline:
                    raise LogStreamStalledError(
                        f"Domain line could not be enqueued within {deadline}s"
                    ) from None
                next_delay = min(_delay * 2, _BACKOFF_CAP)
                self._loop.call_later(
                    next_delay,
                    self._enqueue,
                    line,
                    started_at,
                    next_delay,
                )
            else:
                self.dropped_non_domain_count += 1
                now = time.monotonic()
                if now - self._last_drop_warn_time >= 1.0:
                    self._last_drop_warn_time = now
                    log.warning(
                        "non_domain_line_dropped",
                        dropped_total=self.dropped_non_domain_count,
                    )

    async def __aiter__(self) -> AsyncIterator[str]:
        while True:
            line = await self._queue.get()
            yield line
