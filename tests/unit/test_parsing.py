"""Unit tests for infrastructure parsing functions."""

from __future__ import annotations

from poe2_rpc.infrastructure.parsing import parse_instance_event, parse_level_event


def test_parse_level_event_extracts_username_class_level() -> None:
    line = ": Foo (Witch) is now level 42"
    result = parse_level_event(line)
    assert result is not None
    assert result.username == "Foo"
    assert result.base_class == "Witch"
    assert result.level == 42


def test_parse_level_event_handles_two_word_ascendency() -> None:
    line = ": Bar (Smith of Kitava) is now level 67"
    result = parse_level_event(line)
    assert result is not None
    assert result.base_class == "Smith of Kitava"


def test_parse_level_event_returns_none_on_non_match() -> None:
    line = "some unrelated log line"
    assert parse_level_event(line) is None


def test_parse_instance_event_extracts_level_area_seed() -> None:
    line = 'Generating level 81 area "Map_T15_Crypt" with seed 12345'
    result = parse_instance_event(line)
    assert result is not None
    assert result.level == 81
    assert result.area_code == "Map_T15_Crypt"
    assert result.seed == 12345


def test_parse_instance_event_returns_none_on_non_match() -> None:
    assert parse_instance_event("foo") is None
