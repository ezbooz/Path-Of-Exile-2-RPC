<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-05 | Updated: 2026-05-05 -->

# domain

## Purpose
Pure domain layer: frozen pydantic v2 value objects, runtime-checkable Protocol ports, domain events, and game-domain enums. Zero I/O, zero third-party dependencies beyond pydantic. The `tests/unit/test_no_mutable_state.py` AST guard fails CI if any mutable dataclass or `BaseModel` without `frozen=True` lands here.

## Key Files
| File | Description |
|------|-------------|
| `models.py` | Frozen pydantic VOs: `LevelInfo` (username, base_class, ascendancy_class, level), `InstanceInfo` (level, area_code, seed). |
| `events.py` | Domain events: `CharacterLevelChanged`, `AreaEntered`, `LocalAreaEntered`, `PartyJoined`, `AFKStatusChanged`. Frozen pydantic models published over the application bus. |
| `ports.py` | Runtime-checkable `Protocol` ports: `GameDetector`, `LogStream`, `LogParser`, `PresencePublisher`, `EventBus`, `LocationCatalogPort`, `Settings`. |
| `locations.py` | `Location` VO + `LocationCatalog.resolve(area_code)` — strips `Map` prefix and splits on `_` for map-tier areas so map-name lookups don't require dictionary entries. |
| `classes.py` | `CharacterClass` / `ClassAscendency` enums; values match in-game strings verbatim (e.g. `"Smith of Kitava"`). |
| `owner.py` | `OwnerTracker` frozen VO + state-machine for auto-pinning the player who launched the script (PR-2 hexagonal form; upstream backport uses module globals). |
| `exceptions.py` | Domain-specific exception hierarchy. |

## For AI Agents

### Working In This Directory
- **All VOs must be `frozen=True` pydantic v2 models** — never `dataclass`, never mutable. The AST guard at `tests/unit/test_no_mutable_state.py` enforces this on every test run.
- **No third-party imports beyond pydantic.** No `psutil`, no `pypresence`, no `structlog`, no `pathlib` for file I/O (`Path` as a typed value is fine).
- Adding a new ascendancy: extend `ClassAscendency` enum (value = exact in-game string), update `ClassAscendency.get_class()` mapping, append to the right `CharacterClass.get_ascendencies()` list. Reference commit: `fe9c494`. Upload the matching Discord asset using lowercase + underscore key — `small_image` is derived as `ascension_class.lower().replace(" ", "_")` (commit `5ae14e6`).
- New ports go here as `runtime_checkable` Protocols; concrete adapters in `infrastructure/` implement them. Never import an adapter from this layer.
- New events: frozen pydantic models with explicit field types; published by handlers in `application/`.

### Testing Requirements
- `tests/unit/test_no_mutable_state.py` — AST guard, runs every CI build.
- `tests/unit/test_models.py`, `test_events.py`, `test_classes.py`, `test_locations.py`, `test_owner.py`, `test_ports.py` — per-module unit coverage.
- `tests/unit/test_log_parser_protocol.py` — Protocol structural-typing checks for `LogParser`.

### Common Patterns
- Frozen pydantic v2 VOs with explicit field types and no defaults for required fields.
- `runtime_checkable` Protocols so adapters can be duck-typed in tests.
- Domain events are nouns-in-past-tense (`CharacterLevelChanged`, not `ChangeCharacterLevel`).

## Dependencies

### Internal
- Imported by `application/` (Protocols + VOs + events) and `infrastructure/` (Protocols only — adapters implement them).

### External
- `pydantic` v2 — frozen models.
- Stdlib: `enum`, `typing`, `collections.abc`.

<!-- MANUAL: Manually added notes below this line are preserved on regeneration -->
