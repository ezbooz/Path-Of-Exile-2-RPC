"""Tests for AppSettings — RED phase."""

from __future__ import annotations

from importlib import reload
from pathlib import Path

import pytest

import poe2_rpc.infrastructure.settings as settings_mod
from poe2_rpc.infrastructure.settings import AppSettings


def test_settings_defaults() -> None:
    s = AppSettings()
    assert s.discord_app_id == "1315800372207419504"
    assert s.process_name == ["PathOfExileSteam.exe", "PathOfExile.exe"]
    assert s.locations_url is None
    assert s.log_stream_enqueue_deadline_seconds == 2.0
    assert s.log_stream_queue_maxsize == 1000
    assert s.throttle_window_seconds == 15.0
    assert s.connect_retry_attempts == 5
    assert s.publish_retry_attempts == 3
    assert s.log_format == "console"
    assert s.log_level == "INFO"


def test_settings_env_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POE2RPC_DISCORD_APP_ID", "9999999999999999999")
    monkeypatch.setenv("POE2RPC_THROTTLE_WINDOW_SECONDS", "30.0")

    reload(settings_mod)

    s = settings_mod.AppSettings()
    assert s.discord_app_id == "9999999999999999999"
    assert s.throttle_window_seconds == 30.0


def test_settings_toml_overrides_defaults(tmp_path: Path) -> None:
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        'discord_app_id = "1111111111111111111"\nlog_level = "DEBUG"\n',
        encoding="utf-8",
    )

    s = AppSettings(_toml_file=str(toml_file))  # type: ignore[call-arg]
    assert s.discord_app_id == "1111111111111111111"
    assert s.log_level == "DEBUG"


def test_settings_init_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POE2RPC_CONNECT_RETRY_ATTEMPTS", "10")

    s = AppSettings(connect_retry_attempts=2)
    assert s.connect_retry_attempts == 2


def test_process_name_string_env_coerced_to_list(monkeypatch: pytest.MonkeyPatch) -> None:
    # Back-compat: legacy single-string env var must be promoted to a
    # single-element list so users with POE2RPC_PROCESS_NAME=Foo.exe in
    # an existing config keep working after the type change to list[str].
    monkeypatch.setenv("POE2RPC_PROCESS_NAME", "Foo.exe")
    reload(settings_mod)
    s = settings_mod.AppSettings()
    assert s.process_name == ["Foo.exe"]


def test_process_name_init_string_coerced_to_list() -> None:
    s = AppSettings(process_name="OnlyOne.exe")  # type: ignore[arg-type]
    assert s.process_name == ["OnlyOne.exe"]


def test_process_name_init_list_passes_through() -> None:
    s = AppSettings(process_name=["A.exe", "B.exe"])
    assert s.process_name == ["A.exe", "B.exe"]
