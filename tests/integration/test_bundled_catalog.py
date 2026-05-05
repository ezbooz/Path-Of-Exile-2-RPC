"""F-2: locations.json must be reachable via importlib.resources in a dev install."""

from __future__ import annotations

import importlib.resources
import json

from poe2_rpc.infrastructure.catalog import load_bundled_catalog


def test_bundled_locations_json_is_reachable() -> None:
    """The bundled `locations.json` is accessible through importlib.resources."""
    resource = importlib.resources.files("poe2_rpc").joinpath("locations.json")
    text = resource.read_text(encoding="utf-8")
    data = json.loads(text)
    assert "areas" in data
    assert isinstance(data["areas"], dict)
    assert len(data["areas"]) > 0


def test_load_bundled_catalog_resolves_known_area() -> None:
    """`load_bundled_catalog()` produces a populated catalog that resolves canonical areas."""
    catalog = load_bundled_catalog()
    location = catalog.resolve("G1_1")
    assert location.area_code == "G1_1"
    assert location.display_name == "The Riverbank"
