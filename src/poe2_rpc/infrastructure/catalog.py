"""Bundled locations.json catalog adapter implementing LocationCatalogPort."""

from __future__ import annotations

import importlib.resources
import json

import httpx

from poe2_rpc.domain.locations import LocationCatalog
from poe2_rpc.infrastructure.settings import AppSettings


def load_bundled_catalog() -> LocationCatalog:
    """Load the bundled locations.json into the domain LocationCatalog.

    Used by the composition root and by `validate-config` to prove that the
    bundled JSON is present and parsable without contacting Discord.
    """
    text = (
        importlib.resources.files("poe2_rpc").joinpath("locations.json").read_text(encoding="utf-8")
    )
    data = json.loads(text)
    return LocationCatalog(areas=dict(data.get("areas", {})))


class BundledLocationCatalog:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._areas = self._load_areas()

    def _load_areas(self) -> dict[str, str]:
        if self._settings.locations_url is not None:
            response = httpx.get(self._settings.locations_url)
            response.raise_for_status()
            data = json.loads(response.text)
        else:
            text = (
                importlib.resources.files("poe2_rpc")
                .joinpath("locations.json")
                .read_text(encoding="utf-8")
            )
            data = json.loads(text)
        return dict(data.get("areas", {}))

    def lookup(self, area_code: str) -> str | None:
        return self._areas.get(area_code)

    def map_area_lookup(self, raw_area: str) -> str:
        """Strip Map prefix and join remaining parts with spaces."""
        without_prefix = raw_area[3:].lstrip("_")
        return " ".join(without_prefix.split("_"))
