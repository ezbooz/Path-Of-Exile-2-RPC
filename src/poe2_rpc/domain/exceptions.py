"""Domain exceptions — pure domain layer, no I/O imports."""

from __future__ import annotations


class PoE2RPCError(Exception):
    """Base for all domain-layer exceptions."""


class LogStreamStalledError(PoE2RPCError):
    """Raised when the log stream cannot enqueue domain-relevant lines within the deadline."""
