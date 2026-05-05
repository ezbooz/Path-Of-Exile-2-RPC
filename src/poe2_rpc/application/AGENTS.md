<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-05 | Updated: 2026-05-05 -->

# application

## Purpose
Orchestration layer: composes domain ports into the runtime pipeline. Imports `domain.*` only — never `infrastructure`. Houses the event bus, throttle, handlers, and the main `Orchestrator` that ties `LogStream → LogParser → EventBus → handlers → PresencePublisher` together. `import-linter` enforces this layering.

## Key Files
| File | Description |
|------|-------------|
| `orchestrator.py` | `Orchestrator.run_once()` / `run_forever()`; resolves `area_code → display name` via `LocationCatalogPort` between parse and emit; `stop()` signals sync close so the watchdog stream releases. |
| `bus.py` | `InMemoryEventBus` — synchronous pub/sub over typed event classes; handlers register via `subscribe(event_type, handler)`. |
| `throttle.py` | `PresenceThrottle` — Discord-IPC rate-limit guard (default 15s window per `pypresence` recommendation). |
| `handlers.py` | `on_level_changed` / `on_area_entered` / `on_afk_changed` / `on_local_area_entered`; structlog `bind_contextvars` carries `username` / `character_class` / `area` through the call graph. |

## For AI Agents

### Working In This Directory
- **Never import from `infrastructure`.** This layer sees Protocols only. The `cli.py` composition root is the only place adapters get instantiated and wired.
- Handler signatures take the event VO + the `PresencePublisher` Protocol — keep them that shape so tests can swap in a `FakePresencePublisher`.
- New events: define the frozen pydantic VO in `domain/events.py`, subscribe a handler here, and let the orchestrator publish via `bus.publish(event)` after parsing.
- The `Orchestrator.stop()` sync close-stream design (PR-4) is intentional: it sets a sentinel on the line iterator so `for line in stream.lines()` returns naturally, allowing the tray-thread shutdown path to exit cleanly. Do not async-ify the orchestrator.

### Testing Requirements
- `tests/unit/test_orchestrator_layering.py` — AST guard preventing `infrastructure` imports.
- `tests/unit/test_orchestrator_stop.py` — covers the sync close-stream signal.
- `tests/unit/test_bus.py`, `test_throttle.py`, `test_handlers.py` — per-module unit coverage.
- `tests/integration/test_orchestrator.py` — wires real `RegexLogParser` + `InMemoryEventBus` + fakes for I/O ports.

### Common Patterns
- `bind_contextvars(username=..., character_class=..., area=...)` so structured logs carry pipeline context (AC#7 of the migration).
- Throttle is consulted before every `presence.publish()` call.
- Orchestrator owns the catalog resolution step — handlers receive already-resolved display names.

## Dependencies

### Internal
- `domain.ports` — `GameDetector`, `LogStream`, `LogParser`, `PresencePublisher`, `EventBus`, `LocationCatalogPort`, `Settings`.
- `domain.events`, `domain.models` — typed payloads.

### External
- `structlog` — `bind_contextvars` for pipeline context.
- Stdlib: `time`, `threading`, `typing`, `collections.abc`.

<!-- MANUAL: Manually added notes below this line are preserved on regeneration -->
