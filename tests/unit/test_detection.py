"""Unit tests for PsutilGameDetector — no real psutil scanning."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import psutil
import pytest

from poe2_rpc.infrastructure.detection import PsutilGameDetector
from poe2_rpc.infrastructure.settings import AppSettings


def _make_process(name: str, exe: str) -> MagicMock:
    proc = MagicMock()
    proc.info = {"name": name, "exe": exe}
    return proc


def _fake_iter(*processes: MagicMock):
    def _factory(attrs: list[str]) -> Iterator[MagicMock]:
        return iter(processes)

    return _factory


@pytest.mark.parametrize(
    "process_name,exe_path,expected_log",
    [
        (
            "PathOfExileSteam.exe",
            r"C:/Games/PoE2/PathOfExileSteam.exe",
            r"C:/Games/PoE2/logs/Client.txt",
        ),
        (
            "PathOfExile.exe",
            r"C:/Grinding Gear Games/Path of Exile 2/PathOfExile.exe",
            r"C:/Grinding Gear Games/Path of Exile 2/logs/Client.txt",
        ),
    ],
)
def test_detector_resolves_log_path_for_both_clients(
    process_name: str, exe_path: str, expected_log: str
) -> None:
    proc = _make_process(process_name, exe_path)
    settings = AppSettings()  # default candidates include both clients
    detector = PsutilGameDetector(settings=settings, process_iter_factory=_fake_iter(proc))
    assert detector.find_log_path() == Path(expected_log)


def test_detector_returns_log_path_when_process_running() -> None:
    proc = _make_process("PathOfExileSteam.exe", r"C:/Games/PoE2/PathOfExileSteam.exe")
    settings = AppSettings(process_name=["PathOfExileSteam.exe"])
    detector = PsutilGameDetector(settings=settings, process_iter_factory=_fake_iter(proc))
    result = detector.find_log_path()
    assert result == Path(r"C:/Games/PoE2/logs/Client.txt")


def test_detector_returns_none_when_process_absent() -> None:
    settings = AppSettings(process_name=["PathOfExileSteam.exe"])
    detector = PsutilGameDetector(settings=settings, process_iter_factory=_fake_iter())
    assert detector.find_log_path() is None


def test_detector_skips_inaccessible_processes() -> None:
    # Make the bad proc raise NoSuchProcess when .info is accessed via iteration
    # We simulate this by having the factory raise on first item
    good_proc = _make_process("PathOfExileSteam.exe", r"C:/Games/PoE2/PathOfExileSteam.exe")

    def _raising_iter(attrs: list[str]) -> Iterator[MagicMock]:
        bad = MagicMock()
        bad.info = property(lambda self: (_ for _ in ()).throw(psutil.NoSuchProcess(pid=999)))
        # Simpler: raise from a wrapper
        raise_proc = _RaisingProcess()
        yield raise_proc  # type: ignore[misc]
        yield good_proc

    detector = PsutilGameDetector(
        settings=AppSettings(process_name=["PathOfExileSteam.exe"]),
        process_iter_factory=_raising_iter,
    )
    result = detector.find_log_path()
    assert result == Path(r"C:/Games/PoE2/logs/Client.txt")


class _RaisingProcess:
    """Fake process that raises NoSuchProcess when .info is accessed."""

    @property
    def info(self) -> dict[str, str]:
        raise psutil.NoSuchProcess(pid=999)


def test_detector_uses_settings_process_name() -> None:
    proc = _make_process("OtherGame.exe", r"C:/Games/Other/OtherGame.exe")
    wrong_proc = _make_process("PathOfExileSteam.exe", r"C:/Games/PoE2/PathOfExileSteam.exe")
    settings = AppSettings(process_name=["OtherGame.exe"])
    detector = PsutilGameDetector(
        settings=settings, process_iter_factory=_fake_iter(wrong_proc, proc)
    )
    result = detector.find_log_path()
    assert result == Path(r"C:/Games/Other/logs/Client.txt")
