"""Psutil-based game process detector."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import psutil
import structlog

from poe2_rpc.infrastructure.settings import AppSettings

_log = structlog.get_logger(__name__)
_WAIT_INTERVAL_SECONDS = 5.0


class PsutilGameDetector:
    def __init__(
        self,
        settings: AppSettings,
        process_iter_factory: Callable[[list[str]], Iterator[Any]] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._settings = settings
        self._process_iter = process_iter_factory or psutil.process_iter
        self._sleep = sleep or time.sleep

    def find_log_path(self) -> Path | None:
        for proc in self._iter_processes_safely():
            if proc is None:
                continue
            return proc
        return None

    def is_running(self) -> bool:
        return self.find_log_path() is not None

    def log_path(self) -> Path:
        """Block until the game process is found; matches main.py:88-94 semantics."""
        while True:
            path = self.find_log_path()
            if path is not None:
                return path
            _log.info("waiting_for_game_start", process=self._settings.process_name)
            self._sleep(_WAIT_INTERVAL_SECONDS)

    def _iter_processes_safely(self) -> Iterator[Path | None]:
        for proc in self._process_iter(["name", "exe"]):
            try:
                info = proc.info
                if info.get("name") in self._settings.process_name:
                    exe = info.get("exe")
                    if exe:
                        yield Path(exe).parent / "logs" / "Client.txt"
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
