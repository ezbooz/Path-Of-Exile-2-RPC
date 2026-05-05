"""Unit tests for domain exceptions (C-4b)."""

from __future__ import annotations

from poe2_rpc.domain.exceptions import LogStreamStalledError, PoE2RPCError


def test_log_stream_stalled_is_poe2rpc_error() -> None:
    assert issubclass(LogStreamStalledError, PoE2RPCError)


def test_log_stream_stalled_carries_message() -> None:
    msg = "Failed to enqueue domain line within 2.0s"
    exc = LogStreamStalledError(msg)
    assert str(exc) == msg
