"""Tests for domain value objects: LevelInfo and InstanceInfo."""

import pytest
from pydantic import ValidationError

from poe2_rpc.domain.models import InstanceInfo, LevelInfo


def _make_level_info(**kwargs: object) -> LevelInfo:
    defaults: dict[str, object] = {
        "username": "Exile",
        "base_class": "Mercenary",
        "ascension_class": None,
        "level": 1,
    }
    defaults.update(kwargs)
    return LevelInfo(**defaults)  # type: ignore[arg-type]


def _make_instance_info(**kwargs: object) -> InstanceInfo:
    defaults: dict[str, object] = {
        "area_code": "G1_4_BrambleghastSlain",
        "area_display_name": "Brambleghast",
        "level": 10,
        "seed": 42,
    }
    defaults.update(kwargs)
    return InstanceInfo(**defaults)  # type: ignore[arg-type]


def test_level_info_is_frozen() -> None:
    info = _make_level_info()
    with pytest.raises((ValidationError, TypeError)):
        info.level = 99  # type: ignore[misc]


def test_level_info_eq_by_value() -> None:
    a = _make_level_info(username="Hero", level=5)
    b = _make_level_info(username="Hero", level=5)
    assert a == b


def test_level_info_ascension_class_optional() -> None:
    none_info = _make_level_info(ascension_class=None)
    str_info = _make_level_info(ascension_class="Witchhunter")
    assert none_info.ascension_class is None
    assert str_info.ascension_class == "Witchhunter"


def test_instance_info_is_frozen() -> None:
    info = _make_instance_info()
    with pytest.raises((ValidationError, TypeError)):
        info.level = 99  # type: ignore[misc]


def test_instance_info_eq_by_value() -> None:
    a = _make_instance_info(seed=1)
    b = _make_instance_info(seed=1)
    assert a == b


def test_level_int_required() -> None:
    with pytest.raises(ValidationError):
        _make_level_info(level="not_an_int")  # type: ignore[arg-type]
