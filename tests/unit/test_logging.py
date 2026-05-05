"""Tests for configure_logging — RED phase."""

from __future__ import annotations

import sys

import pytest
import structlog

from poe2_rpc.infrastructure.logging import configure_logging
from poe2_rpc.infrastructure.settings import AppSettings


def _make_settings(log_format: str = "console", log_level: str = "INFO") -> object:
    return AppSettings(log_format=log_format, log_level=log_level)  # type: ignore[arg-type]


def test_configure_logging_console_when_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    settings = _make_settings(log_format="console")

    configure_logging(settings)  # type: ignore[arg-type]

    cfg = structlog.get_config()
    renderer_types = [type(p).__name__ for p in cfg["processors"]]
    assert "ConsoleRenderer" in renderer_types


def test_configure_logging_json_when_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    settings = _make_settings(log_format="json")

    configure_logging(settings)  # type: ignore[arg-type]

    cfg = structlog.get_config()
    renderer_types = [type(p).__name__ for p in cfg["processors"]]
    assert "JSONRenderer" in renderer_types


def test_bind_contextvars_propagates(capsys: pytest.CaptureFixture[str]) -> None:
    settings = _make_settings(log_format="console", log_level="DEBUG")

    configure_logging(settings)  # type: ignore[arg-type]

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(zone="Hideout")

    logger = structlog.get_logger()
    logger.info("test_event")

    captured = capsys.readouterr()
    assert "Hideout" in captured.out or "Hideout" in captured.err


def test_log_level_respected(capsys: pytest.CaptureFixture[str]) -> None:
    settings = _make_settings(log_format="console", log_level="WARNING")

    configure_logging(settings)  # type: ignore[arg-type]

    structlog.contextvars.clear_contextvars()
    logger = structlog.get_logger()
    logger.info("should_not_appear")

    captured = capsys.readouterr()
    assert "should_not_appear" not in captured.out
    assert "should_not_appear" not in captured.err
