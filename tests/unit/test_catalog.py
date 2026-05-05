"""Unit tests for BundledLocationCatalog."""

from __future__ import annotations

import json

import httpx
import pytest

from poe2_rpc.infrastructure.catalog import BundledLocationCatalog
from poe2_rpc.infrastructure.settings import AppSettings


@pytest.fixture()
def catalog() -> BundledLocationCatalog:
    return BundledLocationCatalog(settings=AppSettings())


def test_bundled_catalog_loads_from_package(catalog: BundledLocationCatalog) -> None:
    result = catalog.lookup("G1_4_Brambleghast")
    assert result == "The Brambleghast"


def test_bundled_catalog_returns_none_for_unknown_code(catalog: BundledLocationCatalog) -> None:
    assert catalog.lookup("ZZ_FAKE") is None


def test_map_area_lookup_strips_prefix_and_splits(catalog: BundledLocationCatalog) -> None:
    result = catalog.map_area_lookup("Map_T15_Crypt")
    assert result == "T15 Crypt"


def test_locations_url_override_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    custom_data = json.dumps({"areas": {"CUSTOM_1": "Custom Area One"}})

    class _FakeResponse:
        text = custom_data

        def raise_for_status(self) -> None:
            pass

    monkeypatch.setattr(httpx, "get", lambda url, **kw: _FakeResponse())
    settings = AppSettings(locations_url="http://example.com/locations.json")
    cat = BundledLocationCatalog(settings=settings)
    assert cat.lookup("CUSTOM_1") == "Custom Area One"
    assert cat.lookup("G1_1") is None  # bundled data NOT used when URL override active
