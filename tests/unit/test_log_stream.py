"""Unit tests for WatchdogLogStream — thread-safety contract (C-4)."""

from __future__ import annotations

import re
import time
from asyncio import QueueFull
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from poe2_rpc.domain.exceptions import LogStreamStalledError
from poe2_rpc.infrastructure.log_stream import WatchdogLogStream
from poe2_rpc.infrastructure.settings import AppSettings

_REGEX_LEVEL = re.compile(r": (\w+) \(([\w\s]+)\) is now level (\d+)")
_REGEX_INSTANCE = re.compile(r'Generating level (\d+) area "([^"]+)" with seed (\d+)')

DOMAIN_LINE = ": Marauder (Juggernaut) is now level 42"
NON_DOMAIN_LINE = "[INFO] some irrelevant log line"


def _make_stream(tmp_path: Path, maxsize: int = 2) -> WatchdogLogStream:
    log_file = tmp_path / "Client.txt"
    log_file.write_text("", encoding="utf-8")

    settings = AppSettings(
        log_stream_queue_maxsize=maxsize,
        log_stream_enqueue_deadline_seconds=0.5,
    )
    loop = MagicMock()
    return WatchdogLogStream(log_path=log_file, settings=settings, loop=loop)


# ---------------------------------------------------------------------------
# Test 1 — observer thread NEVER calls put_nowait directly
# ---------------------------------------------------------------------------


def test_watchdog_observer_thread_does_not_touch_queue_directly(tmp_path: Path) -> None:
    """Handler's on_modified path must use call_soon_threadsafe, not queue.put_nowait."""
    log_file = tmp_path / "Client.txt"
    log_file.write_text("", encoding="utf-8")

    mock_loop = MagicMock()
    settings = AppSettings(log_stream_queue_maxsize=10)
    stream = WatchdogLogStream(log_path=log_file, settings=settings, loop=mock_loop)

    log_file.write_text(DOMAIN_LINE + "\n", encoding="utf-8")
    stream._handler.on_modified(MagicMock())  # type: ignore[attr-defined]

    mock_loop.call_soon_threadsafe.assert_called()
    put_nowait = getattr(stream._queue, "put_nowait", None)
    if isinstance(put_nowait, MagicMock):
        assert not put_nowait.called


# ---------------------------------------------------------------------------
# Test 2 — _enqueue is invoked via call_soon_threadsafe
# ---------------------------------------------------------------------------


def test_enqueue_runs_on_loop_thread(tmp_path: Path) -> None:
    """call_soon_threadsafe must schedule _enqueue (not call put_nowait directly)."""
    log_file = tmp_path / "Client.txt"
    log_file.write_text("", encoding="utf-8")

    mock_loop = MagicMock()
    settings = AppSettings(log_stream_queue_maxsize=10)
    stream = WatchdogLogStream(log_path=log_file, settings=settings, loop=mock_loop)

    log_file.write_text(DOMAIN_LINE + "\n", encoding="utf-8")
    stream._handler.on_modified(MagicMock())  # type: ignore[attr-defined]

    calls = mock_loop.call_soon_threadsafe.call_args_list
    assert len(calls) >= 1
    assert calls[0][0][0] == stream._enqueue  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Test 3 — QueueFull → exponential backoff for domain lines → LogStreamStalledError
# ---------------------------------------------------------------------------


def test_queue_full_exponential_backoff_for_domain_lines(tmp_path: Path) -> None:
    """Domain lines on QueueFull get exponential-backoff retry; raises past deadline."""
    log_file = tmp_path / "Client.txt"
    log_file.write_text("", encoding="utf-8")

    mock_loop = MagicMock()
    settings = AppSettings(
        log_stream_queue_maxsize=1,
        log_stream_enqueue_deadline_seconds=2.0,
    )
    stream = WatchdogLogStream(log_path=log_file, settings=settings, loop=mock_loop)

    stream._queue = MagicMock()  # type: ignore[attr-defined]
    stream._queue.put_nowait.side_effect = QueueFull()

    started_at = time.monotonic() - 10.0  # well past deadline
    with pytest.raises(LogStreamStalledError):
        stream._enqueue(DOMAIN_LINE, _started_at=started_at)  # type: ignore[attr-defined]


def test_queue_full_exponential_backoff_schedules_call_later(tmp_path: Path) -> None:
    """Domain lines on QueueFull within deadline schedule a call_later retry."""
    log_file = tmp_path / "Client.txt"
    log_file.write_text("", encoding="utf-8")

    mock_loop = MagicMock()
    settings = AppSettings(
        log_stream_queue_maxsize=1,
        log_stream_enqueue_deadline_seconds=2.0,
    )
    stream = WatchdogLogStream(log_path=log_file, settings=settings, loop=mock_loop)

    stream._queue = MagicMock()  # type: ignore[attr-defined]
    stream._queue.put_nowait.side_effect = QueueFull()

    started_at = time.monotonic()
    stream._enqueue(DOMAIN_LINE, _started_at=started_at, _delay=0.05)  # type: ignore[attr-defined]

    mock_loop.call_later.assert_called_once()
    delay_arg = mock_loop.call_later.call_args[0][0]
    assert abs(delay_arg - 0.1) < 1e-9  # next delay doubles to 0.1


# ---------------------------------------------------------------------------
# Test 4 — QueueFull drops non-domain lines, increments counter
# ---------------------------------------------------------------------------


def test_queue_full_drops_non_domain_lines_with_metric(tmp_path: Path) -> None:
    """Non-domain lines on QueueFull are dropped; dropped_non_domain_count incremented."""
    log_file = tmp_path / "Client.txt"
    log_file.write_text("", encoding="utf-8")

    mock_loop = MagicMock()
    settings = AppSettings(log_stream_queue_maxsize=1)
    stream = WatchdogLogStream(log_path=log_file, settings=settings, loop=mock_loop)

    stream._queue = MagicMock()  # type: ignore[attr-defined]
    stream._queue.put_nowait.side_effect = QueueFull()

    assert stream.dropped_non_domain_count == 0  # type: ignore[attr-defined]

    stream._enqueue(NON_DOMAIN_LINE)  # type: ignore[attr-defined]

    assert stream.dropped_non_domain_count == 1  # type: ignore[attr-defined]
    mock_loop.call_later.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5 — file rotation resets cursor
# ---------------------------------------------------------------------------


def test_file_rotation_resets_cursor(tmp_path: Path) -> None:
    """When cursor > file size (rotation), cursor resets to 0 and new lines are yielded."""
    log_file = tmp_path / "Client.txt"
    initial_content = "old line 1\nold line 2\n"
    log_file.write_text(initial_content, encoding="utf-8")

    mock_loop = MagicMock()
    settings = AppSettings(log_stream_queue_maxsize=100)
    stream = WatchdogLogStream(log_path=log_file, settings=settings, loop=mock_loop)

    new_content = "new line after rotation\n"
    log_file.write_text(new_content, encoding="utf-8")

    stream._cursor = len(initial_content.encode("utf-8")) + 100  # type: ignore[attr-defined]

    stream._handler.on_modified(MagicMock())  # type: ignore[attr-defined]

    assert stream._cursor == len(new_content.encode("utf-8"))  # type: ignore[attr-defined]

    assert mock_loop.call_soon_threadsafe.call_count >= 1
    scheduled_line = mock_loop.call_soon_threadsafe.call_args_list[0][0][1]
    assert "new line after rotation" in scheduled_line
