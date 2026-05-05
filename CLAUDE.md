# CLAUDE.md — Path-Of-Exile-2-RPC

Project-level guidance for Claude Code working in this repository. Pair with the hierarchical `AGENTS.md` files for directory-specific detail.

## Project at a glance
- **What it is:** A Discord Rich Presence integration for Path of Exile 2. Tails the game's `Client.txt`, parses level-up and area-generation events, and pushes presence updates via `pypresence`.
- **Shape:** Hexagonal Python package at `src/poe2_rpc/` with `domain/`, `application/`, `infrastructure/`, and `cli.py` (composition root). The Typer app in `cli.py` is the runtime entrypoint; `pyproject.toml` exposes it as the `poe2-rpc` console script and `python -m poe2_rpc`.
- **Distribution:** End users grab a prebuilt Windows `.exe` from GitHub Releases. The `.exe` is produced by `.github/workflows/build.yml` via PyInstaller `--onefile` against `PathOfExile2DiscordRPC.spec`. CI re-runs whenever `src/**`, `pyproject.toml`, `locations.json`, the spec file, or the workflow itself changes.

## Build & Test

```bash
pip install -e ".[dev]"
poe2-rpc run                            # continuous monitor loop
poe2-rpc once                           # single log-stream pass
poe2-rpc validate-config --no-discord   # smoke check (no Discord IPC)
```

Discord must be running for `run` / `once`. `infrastructure/detection.py::PsutilGameDetector` blocks until `PathOfExileSteam.exe` is detected (`log_path()` polls every 5s).

The full gate suite (mirrors CI):

```bash
pytest tests -ra
mypy --strict src/poe2_rpc
lint-imports               # enforces hexagonal layering
ruff check src tests
ruff format --check src tests
```

Optional config: `%APPDATA%\poe2-rpc\config.toml` on Windows, `~/.config/poe2-rpc/config.toml` on macOS/Linux for cross-platform dev. Defaults work without one — see `infrastructure/settings.py::AppSettings` for the schema.

## Architecture Overview

Hexagonal layering is enforced by `import-linter` (see `[tool.importlinter]` in `pyproject.toml`):

```
poe2_rpc.cli           ← composition root; only layer that imports infrastructure
poe2_rpc.application   ← orchestration, event bus, throttle, handlers — Protocols only
poe2_rpc.infrastructure ← psutil/watchdog/pypresence/pydantic-settings/structlog adapters
poe2_rpc.domain        ← pure value objects, events, ports — no I/O, no third-party
```

Key modules:

- `domain/models.py` — frozen pydantic VOs (`LevelInfo`, `InstanceInfo`).
- `domain/events.py` — `CharacterLevelChanged`, `AreaEntered`, etc.
- `domain/ports.py` — runtime-checkable Protocols (`GameDetector`, `LogStream`, `LogParser`, `PresencePublisher`, `EventBus`, `LocationCatalogPort`, `Settings`).
- `domain/locations.py` — `LocationCatalog.resolve(area_code)` returns a `Location` VO.
- `domain/classes.py` — `CharacterClass` / `ClassAscendency` enums (matches in-game strings verbatim).
- `application/orchestrator.py` — composes bus + throttle + handlers; calls `catalog.resolve()` between parse and emit so handlers see resolved display names.
- `application/handlers.py` — `on_level_changed` / `on_area_entered`; structlog `bind_contextvars` carries `username` / `character_class` / `area`.
- `application/throttle.py` — `PresenceThrottle` (Discord IPC rate-limit guard).
- `infrastructure/parsing.py` — `regex_level` / `regex_instance` (verbatim from `main.py:273-274`) + `RegexLogParser` adapter.
- `infrastructure/detection.py` — `PsutilGameDetector` (`is_running()` / blocking `log_path()`).
- `infrastructure/log_stream.py` — `WatchdogLogStream` (event-driven via `ReadDirectoryChangesW`; thread-safe enqueue via `loop.call_soon_threadsafe`).
- `infrastructure/presence.py` — `PypresencePublisher` (`AioPresence` + tenacity split-retry: connect 5×wait_exponential(2,32), publish 3×wait_exponential(1,8)).
- `infrastructure/catalog.py` — `load_bundled_catalog()` reads bundled `locations.json` via `importlib.resources`.
- `infrastructure/settings.py` — `AppSettings` (pydantic-settings BaseSettings).
- `infrastructure/logging.py` — structlog config (ConsoleRenderer dev / JSONRenderer prod).
- `cli.py` — Typer app (`run`, `once`, `validate-config`, `--version`); `build_orchestrator(settings)` factory + `_SyncLineIterator` adapter bridging async `WatchdogLogStream` to the sync `LogStream` Protocol.

## Conventions & Patterns

- **Hexagonal layering is non-negotiable.** Don't import infrastructure from application or domain — `lint-imports` will fail. The composition root in `cli.py` is the *only* place where adapters and application code meet.
- **Frozen pydantic v2 VOs everywhere in `domain/`.** No mutable state, no `dataclass`. `tests/unit/test_no_mutable_state.py` AST guard enforces this.
- **`mypy --strict`** is mandatory. 4-space indent, type hints on every signature.
- **`structlog` not `logging`.** Use `bind_contextvars(username=, character_class=, area=)` so events carry context through the call graph (AC#7).
- **`pathlib.Path` + explicit `encoding="utf-8"`** for file I/O. Bundled JSON via `importlib.resources.files("poe2_rpc")` — never `Path("locations.json")` cwd-relative.
- **Tenacity for retries**, not hand-rolled `time.sleep(2 ** retries)`. Split policies for connect vs publish (see `infrastructure/presence.py`).

## Adding a new ascendancy

1. Add the enum member to `ClassAscendency` in `src/poe2_rpc/domain/classes.py` — value must match the in-game string verbatim (e.g. `"Smith of Kitava"`).
2. Add the mapping in `ClassAscendency.get_class()`.
3. Append it to the right list in `CharacterClass.get_ascendencies()`.
4. Upload the matching Discord asset using the **lowercase + underscore** key, since the formatter derives `small_image` as `ascension_class.lower().replace(" ", "_")` (commit `5ae14e6` enforced this).

Reference commit: `fe9c494` ("Add new character classes: Smith of Kitava, Lich, and Tactician").

## Adding/updating zones

- Edit `src/poe2_rpc/locations.json` (bundled into the package via `[tool.setuptools.package-data]`); the root-level `locations.json` is kept in sync as the human-edit source of truth.
- Schema: `{"areas": {"<internal_code>": "<display name>"}}`. Internal codes look like `G1_1`, `G1_4_Brambleghast`, etc.
- `LocationCatalog.resolve()` strips a leading `Map` prefix and splits on `_` for map-tier areas, so map-name lookups don't require a dictionary entry.
- The `.exe` reads the bundled JSON via `importlib.resources` — no runtime URL fetch. To override locally for testing, set `AppSettings.locations_url` (env var `POE2_RPC_LOCATIONS_URL`).

## Regex contracts

Don't break these without checking a real `Client.txt` sample (G-1 enforces this via `tests/integration/test_regex_real_sample.py` once the fixture is captured):

- `regex_level`: `r": (\w+) \(([\w\s]+)\) is now level (\d+)"` → `(username, base_or_ascendancy_class, level)`.
- `regex_instance`: `r'Generating level (\d+) area "([^"]+)" with seed (\d+)'` → `(level, area_code, seed)`.

Both target the Steam-build log format. Defined in `src/poe2_rpc/infrastructure/parsing.py`.

## CI / Release flow

- Push to `main` touching `src/**`, `pyproject.toml`, `locations.json`, `PathOfExile2DiscordRPC.spec`, or the workflow → `.github/workflows/build.yml` runs lint+test on `ubuntu-latest`, then build on `windows-latest`.
- The build job runs `pyinstaller PathOfExile2DiscordRPC.spec`, then deep-smoke `dist\PathOfExile2DiscordRPC.exe validate-config --no-discord`, then the cold-start benchmark (continue-on-error: budget breach files a follow-up bd issue, doesn't block release).
- A timestamp tag (`vYYYYMMDD-HHMMSS`) is created and pushed; the release job uploads `PathOfExile2DiscordRPC.exe` as a GitHub Release asset.

## Open work (from README)

All four originally-listed README items have been implemented locally on
stacked feature branches and submitted as draft PRs upstream
(`ezbooz/Path-Of-Exile-2-RPC` #6, #7, #8, #9):

- [x] Support the official PoE2 client (`PathOfExile.exe` alongside Steam).
- [x] Detect which player started the script (owner auto-pin).
- [x] Show AFK status (with `[AFK]` suffix + small-image override + restore).
- [x] Launch as a background service (pystray tray + Windows Startup shortcut).

Remaining work: end-of-campaign Windows live-smoke screenshots to flip the
4 upstream draft PRs to ready-for-review.

## See also

- `AGENTS.md` — hierarchical directory guide.
- `.github/AGENTS.md`, `.github/workflows/AGENTS.md`, `.github/ISSUE_TEMPLATE/AGENTS.md` — directory-specific notes.
- `README.md` — end-user instructions.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:ca08a54f -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->
