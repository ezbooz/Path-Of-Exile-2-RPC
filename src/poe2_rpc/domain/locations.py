"""Location value object and catalog — pure domain logic, no I/O."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Location(BaseModel):
    model_config = ConfigDict(frozen=True)

    area_code: str
    display_name: str


class LocationCatalog:
    """Resolves area codes to display names using injected mapping."""

    def __init__(self, areas: dict[str, str]) -> None:
        self._areas = areas

    def resolve(self, area_code: str) -> Location:
        normalized = area_code

        if area_code.startswith("Map"):
            normalized = area_code[3:].split("_", maxsplit=1)[0]

        if normalized in self._areas.values():
            return Location(area_code=area_code, display_name=normalized)

        for key, value in self._areas.items():
            if normalized in (key, value):
                return Location(area_code=area_code, display_name=value)

        return Location(area_code=area_code, display_name=normalized)
