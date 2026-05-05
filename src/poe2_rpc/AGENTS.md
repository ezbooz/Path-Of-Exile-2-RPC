<!-- Parent: ../../AGENTS.md -->
<!-- Generated: 2026-05-05 | Updated: 2026-05-05 -->

# poe2_rpc

## Purpose
Hexagonal package for the Path of Exile 2 Discord Rich Presence integration. The runtime entrypoint is `cli.py` (Typer app, exposed as the `poe2-rpc` console script and `python -m poe2_rpc`). Layering — `domain` ← `application` ← `infrastructure` ← `cli` — is enforced by `import-linter` (`[tool.importlinter]` in `pyproject.toml`); `cli.py` is the only module allowed to import from `infrastructure`.

## Key Files
| File | Description |
|------|-------------|
| `cli.py` | Composition root. Typer commands (`run`, `once`, `validate-config`, `tray`, `install-autostart`, `uninstall-autostart`); `build_orchestrator(settings)` factory; `_SyncLineIterator` adapter that bridges the async `WatchdogLogStream` to the sync `LogStream` Protocol. |
| `__main__.py` | `python -m poe2_rpc` entrypoint; dispatches to the Typer app. |
| `__init__.py` | Package marker; re-exports `__version__`. |
| `__version__.py` | Single source of truth for the package version (read by `cli.py --version` and CI release tagging). |
| `locations.json` | Bundled mapping of internal area codes → display names. Loaded via `importlib.resources.files("poe2_rpc")` so PyInstaller `--onefile` builds keep working without a runtime URL fetch. |
| `py.typed` | PEP 561 marker — downstream consumers get type info. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `domain/` | Pure value objects, events, ports — no I/O, no third-party (see `domain/AGENTS.md`). |
| `application/` | Orchestration, event bus, throttle, handlers — Protocols only (see `application/AGENTS.md`). |
| `infrastructure/` | psutil/watchdog/pypresence/pydantic-settings/structlog/pystray/pylnk3 adapters (see `infrastructure/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- `cli.py` is the **only** layer permitted to import from `infrastructure`. Don't add infrastructure imports anywhere else — `lint-imports` will fail.
- `_SyncLineIterator` exists because the orchestrator runs synchronously over `for line in stream.lines()` while `WatchdogLogStream` is event-driven via an asyncio queue. Don't async-ify the orchestrator; the sync close-stream design (PR-4) is intentional and required for the tray Quit-shutdown path.
- `__version__` must stay a plain string in `__version__.py`; the CI release job (`build.yml`) reads it with `grep`/`sed`, not `import`.
- New CLI commands go in `cli.py` and must wire optional-extras imports in a `try/except ImportError + typer.Exit(code=1)` block (see `tray` / `install-autostart` for the pattern).

### Testing Requirements
- `tests/integration/test_cli.py` covers Typer app surface (help, version, validate-config flows). Add an integration test alongside any new command.
- `tests/unit/test_extras_missing.py` covers the optional-extras gate; extend it whenever a new `[tray]`-style extra is introduced.

### Common Patterns
- Composition root assembles ports → application → handlers via `build_orchestrator(settings)`.
- All Typer command callbacks return `None`; errors raise `typer.Exit(code=...)`.
- Optional-deps imports are deferred to inside the function body so headless installs never hit the import.

## Dependencies

### Internal
- Imports `domain.ports` and concrete `infrastructure.*` adapters at composition time.

### External
- `typer` — CLI framework.
- `structlog` — structured logging (configured via `infrastructure.logging`).
- `importlib.resources` — bundled-asset access.

<!-- MANUAL: Manually added notes below this line are preserved on regeneration -->
