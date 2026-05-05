<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-05 | Updated: 2026-05-05 -->

# tests

## Purpose
Test root for the project. Pytest discovery picks up `unit/` (fast, hexagonal-isolated) and `integration/` (Typer CLI surface, real regexes, bundled catalog). The full gate suite — `pytest tests -ra && mypy --strict src/poe2_rpc && lint-imports && ruff check src tests && ruff format --check src tests` — runs in CI and on every release build.

## Key Files
| File | Description |
|------|-------------|
| `__init__.py` | Marks tests as a package so shared fixtures import cleanly. |
| `conftest.py` | Project-wide fixtures: tmp_path-based fake log file, `FakePresencePublisher`, `FakeEventBus`, settings overrides. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `unit/` | Per-module unit tests + AST guards (no mutable state, no infrastructure imports from application) — see `unit/AGENTS.md`. |
| `integration/` | Typer CLI surface, bundled-catalog roundtrip, real regex against captured `Client.txt` samples — see `integration/AGENTS.md`. |

## For AI Agents

### Working In This Directory
- **Tests are the architecture's enforcement layer.** AST guards in `unit/test_no_mutable_state.py`, `unit/test_layering.py`, `unit/test_orchestrator_layering.py` fail CI if hexagonal contracts drift. Don't disable them — fix the source instead.
- New adapter? Add a Protocol-instance check (`assertIsInstance(adapter, ProtocolType)`) so duck-typing is wired through.
- New feature? Add unit tests for the pure code (parsers, handlers, throttle) and an integration test for the CLI surface.
- Optional-extras gate: any new `[tray]`-style extra needs a row in `unit/test_extras_missing.py` so headless installs surface a friendly `typer.Exit(code=1)` instead of an `ImportError`.

### Testing Requirements
- Run the full gate locally before pushing: `pytest tests -ra && mypy --strict src/poe2_rpc && lint-imports && ruff check src tests && ruff format --check src tests`.
- 143 tests pass on the current branch; new code should not lower this baseline without an accompanying issue documenting why.

### Common Patterns
- Frozen pydantic VOs constructed in tests use named kwargs only (positional args are ambiguous and break refactors).
- `tmp_path` fixture for any test touching the filesystem; never write into the repo.
- `monkeypatch.setenv("POE2_RPC_*", ...)` for settings overrides — keep env-var names spelled out, since they're part of the public CLI contract.

## Dependencies

### Internal
- Imports `poe2_rpc.*` (via the editable install).

### External
- `pytest` — runner.
- `pytest-asyncio` — async test support for the watchdog stream tests.

<!-- MANUAL: Manually added notes below this line are preserved on regeneration -->
