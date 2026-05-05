"""G-1: validate regex contracts against a real Client.txt sample.

The fixture `tests/fixtures/sample_client.txt` is captured manually during
the G-4 Windows live smoke. Without it this test skips with reason — once
captured, it locks in regex compatibility with real-world log lines.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from poe2_rpc.infrastructure.parsing import regex_instance, regex_level

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample_client.txt"


def _load_fixture() -> str:
    if not _FIXTURE.exists():
        pytest.skip(f"fixture absent: {_FIXTURE} (capture during G-4 live smoke)")
    return _FIXTURE.read_text(encoding="utf-8")


def test_regex_level_matches_real_log_lines() -> None:
    text = _load_fixture()
    matches = regex_level.findall(text)
    assert len(matches) >= 1, "expected >=1 level-up event in real Client.txt sample"


def test_regex_instance_matches_real_log_lines() -> None:
    text = _load_fixture()
    matches = regex_instance.findall(text)
    assert len(matches) >= 1, "expected >=1 area-generation event in real Client.txt sample"
