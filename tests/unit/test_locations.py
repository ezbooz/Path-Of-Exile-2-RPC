"""Tests for Location VO and LocationCatalog.resolve()."""

import pytest
from pydantic import ValidationError

from poe2_rpc.domain.locations import LocationCatalog


@pytest.fixture
def catalog() -> LocationCatalog:
    return LocationCatalog(
        {
            "G1_1": "The Mud Flats",
            "G1_4_Brambleghast": "Brambleghast Hollow",
        }
    )


def test_location_is_frozen(catalog: LocationCatalog) -> None:
    loc = catalog.resolve("G1_1")
    with pytest.raises((TypeError, AttributeError, ValidationError)):
        loc.display_name = "changed"  # type: ignore[misc]


def test_resolve_known_area_code(catalog: LocationCatalog) -> None:
    loc = catalog.resolve("G1_1")
    assert loc.display_name == "The Mud Flats"
    assert loc.area_code == "G1_1"


def test_resolve_map_prefix_strips_and_resolves(catalog: LocationCatalog) -> None:
    # "MapG1_4_Brambleghast" -> strip "Map" -> "G1_4_Brambleghast" -> split on "_" -> "G1"
    # but the exact main.py logic: area_name[3:].split("_")[0]
    # "MapG1_4_Brambleghast"[3:] = "G1_4_Brambleghast", split("_")[0] = "G1"
    # "G1" not in values, not in keys -> fallback to "G1"
    loc = catalog.resolve("MapG1_4_Brambleghast")
    assert loc.area_code == "MapG1_4_Brambleghast"
    assert loc.display_name == "G1"


def test_resolve_unknown_returns_area_code_as_display(catalog: LocationCatalog) -> None:
    loc = catalog.resolve("UNKNOWN_ZONE_XYZ")
    assert loc.area_code == "UNKNOWN_ZONE_XYZ"
    assert loc.display_name == "UNKNOWN_ZONE_XYZ"


def test_resolve_value_match_returns_value(catalog: LocationCatalog) -> None:
    # If normalized name is already a value in the dict, return it directly
    loc = catalog.resolve("The Mud Flats")
    assert loc.display_name == "The Mud Flats"
    assert loc.area_code == "The Mud Flats"
