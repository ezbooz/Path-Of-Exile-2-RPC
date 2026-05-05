# RALPLAN: Path-Of-Exile-2-RPC — Aggressive DDD / Hexagonal Migration

**Mode:** consensus / DELIBERATE
**Source spec:** `.omc/specs/deep-dive-architecture-libraries.md`
**Target:** Migrate `main.py` (~330 LOC, single-file) to `src/poe2_rpc/` hexagonal package; ship as `PathOfExile2DiscordRPC.exe` via PyInstaller `--onefile`.
**Mandate:** Aggressive DDD already chosen; 4 priorities locked (latency, reliability, testability, observability). No conservative/balanced re-litigation.

---

## 1. RALPLAN-DR Summary

### 1.1 Principles (design constants for the migration)

1. **Domain purity over framework convenience.** `domain/` imports nothing from `infrastructure/`, no I/O, no `pypresence`/`watchdog`/`psutil`. Ports are `typing.Protocol`, not ABCs. This is the load-bearing rule — every other choice serves it.
2. **Frozen-by-default, immutable VOs.** All domain models are `pydantic.BaseModel(model_config=ConfigDict(frozen=True))` or `Enum`. Dict-based "state bags" (`current_status`, `level_info`) are eradicated; equality replaces ad-hoc dict comparison.
3. **Log streaming is event-driven via watchdog (Windows ReadDirectoryChangesW). Process detection (`PsutilGameDetector`) is allowed to poll psutil at 3s interval — this is an explicit narrow exception because there is no Win32 process-creation event API equivalent for non-elevated processes.** If the watchdog observer fails to start, we **fail loudly** (`RuntimeError`) — there is no silent fallback to polling for log streaming, because an undetected polling fallback would invalidate the latency principle.
4. **Production wiring lives exclusively in `cli.py`. Tests may inject alternative factories. The application layer accepts factories/protocols, never constructs infrastructure adapters.** No service-locators, no DI container, no globals.
5. **regex_level and regex_instance constants are preserved verbatim from main.py. Additionally, the streaming pipeline must process every log line that matches either regex — drop policy applies only to non-matching lines (back-pressure on domain-relevant lines is blocking, not lossy).**

### 1.2 Decision Drivers (top 3, ranked)

1. **Sub-second latency for level/area changes.** The single biggest user-visible win. `watchdog` + Windows `ReadDirectoryChangesW` is the only Context7-backed path that hits this without a polling thread.
2. **Reliability of Discord IPC under reconnect storms.** `tenacity` with `retry_if_exception_type((ConnectionError, OSError, InvalidPipe))` + `before_sleep_log` replaces hand-rolled `2**retries` loop, and gives observable retry telemetry via `structlog`.
3. **Testability without an actual game running.** Domain logic must be 100% unit-testable (parsers, classes, locations, throttle, bus) with zero `psutil`/`pypresence` mocks. This forces the port/adapter split to be real, not cosmetic.

### 1.3 Viable Options

#### Option A — **Aggressive DDD / Hexagonal (CHOSEN)**

Full `src/poe2_rpc/` with `domain/`, `application/`, `infrastructure/` layers; async event-bus; AioPresence; pydantic VOs; mypy --strict; 7-phase migration.

- **Pros:** Hits all 4 priorities. Clean test boundary. Future-proof for non-Steam client, AFK detection, party-conflict resolution. Idiomatic Python 3.11+.
- **Cons:** ~1500 LOC of new package code for a 330-LOC script. Higher PyInstaller surface (~5–8 MB binary growth). Onboarding friction for casual contributors.

#### Option B — **Hexagonal-Lite (single package, no application/event-bus split)**

`src/poe2_rpc/` with `domain.py`, `adapters.py`, `app.py`, `cli.py`. Direct adapter calls from a single `App` class instead of an event-bus.

- **Pros:** ~40% less scaffolding than Option A. Still typed, tested, watchdog-driven. Faster to ship.
- **Cons:** Couples parsing to presence-publishing in `App`. Adding handlers (e.g. AFK detection) means editing one growing class instead of subscribing a new handler. Throttle and bus-fanout logic blur.

#### Option C — **Single-file Evolution (INVALIDATED on technical grounds)**

Stay in `main.py`, swap `time.sleep(5)` → `watchdog`, swap `Presence` → `AioPresence`, add `tenacity` decorators, keep dict state.

**Re-defended invalidation rationale:**

- ✓ Could hit Priority 1 (latency): yes, watchdog swap in `monitor_log()` is ~10 LOC.
- ✓ Could hit Priority 2 (reliability): yes, tenacity decorator on `rpc_connect` is ~3 LOC.
- ✓ Could hit Priority 4 (observability): yes, structlog drop-in is ~5 LOC + config.
- ✗ **CANNOT hit Priority 3 (testability) without protocol/port refactor:**
  - `main.py` `monitor_log()` couples 4 concerns (discovery + streaming + parsing + presence).
  - Cannot mock `pypresence` for unit tests without injecting `Presence` — which IS a port pattern.
  - Cannot test parsing without invoking I/O — which IS layer separation.
  - Therefore single-file evolution requires partial DDD refactor for testability anyway.
- ✗ **CANNOT support Future Open Work without significant restructuring:**
  - AFK detection (open work in README) requires event subscription model.
  - Non-Steam client support requires `GameDetector` abstraction.
  - Party-conflict detection requires correlated-event handling.

**Conclusion:** 3 of 4 priorities are achievable in single-file form, but Priority 3 (testability) plus the README open-work backlog require structural separation. Going to full DDD now is cheaper than retrofitting incrementally. Spec Acceptance Criterion #1 also mandates `src/poe2_rpc/` with explicit layers — Option C cannot satisfy it. **Documented as invalidated, not chosen.**

#### Why A over B

The user picked all 4 priorities (no compromise). Option B compromises **testability** (App class becomes God-object after AFK + non-Steam) and **observability** (no event-bus → no central place to bind contextvars per event-type). Option A's extra cost is one-time scaffolding; Option B's extra cost recurs every time we add a handler.

### 1.4 Pre-Mortem (3 failure scenarios)

#### Scenario PM-1: `watchdog` doesn't fire on `Client.txt` writes

**What:** PoE2 writes via memory-mapped I/O or buffered/append with NTFS-specific flush behavior; `ReadDirectoryChangesW` doesn't deliver `FileModifiedEvent` reliably during gameplay.

**Probability:** Medium. The `watchdog` issue tracker has historical reports of memory-mapped writes not triggering. PoE2 is observed to write `Client.txt` as plain append (current `readlines()` polling works), but we have no measurement on event-frequency.

**Mitigation:**
- Phase B test E-2 (live-game smoke) is the empirical gate before cutover.
- Phase C task C-4b ("stall detector") implements: on missing `FileSystemEvent` past `presence_min_interval_seconds * 4`, attempt one `Observer.stop()` + `Observer.schedule()` recovery; if the next stall window is also silent, raise `LogStreamStalled`. No silent polling fallback — would violate Principle 3.
- Add a `--debug-watchdog` CLI flag that prints every `FileSystemEvent` for triage.

#### Scenario PM-2: PyInstaller `--onefile` misses a watchdog hidden import on Windows

**What:** `watchdog.observers` lazy-imports `watchdog.observers.read_directory_changes` only on Windows; `pyinstaller --onefile` hooks may miss it, causing the .exe to import-fail at runtime with `ModuleNotFoundError: watchdog.observers.read_directory_changes` — but only on user machines, not the CI build, because CI runs on `windows-latest` *and* runs the final build artifact only via tag-push.

**Probability:** High at first build attempt. `watchdog` Windows backend is a known PyInstaller gotcha.

**Mitigation:**
- `PathOfExile2DiscordRPC.spec` declares expanded `hiddenimports=['watchdog.observers.read_directory_changes', 'watchdog.observers.winapi', 'pydantic_core._pydantic_core', 'pydantic._internal._model_construction', 'pydantic_settings.sources.providers.toml', 'structlog._log_levels', 'tenacity']` plus `--collect-submodules` for pydantic, pydantic_settings, structlog, watchdog, tenacity, pypresence (F-1).
- Phase F task F-3 adds a CI smoke step: `dist\PathOfExile2DiscordRPC.exe validate-config --no-discord` on the Windows runner before tagging — exercises the full pydantic-settings + TOML + structlog + watchdog import chain end-to-end.
- Phase F task F-4 measures cold-start (5 runs of `validate-config --no-discord`); p95 ≤ 8s budget; budget breach files `bd` issue and annotates release notes.
- Phase G task G-4 runs the explicit live-smoke checklist on a real Windows VM with PoE2 + Discord before release.

#### Scenario PM-3: `pypresence.AioPresence` async-context leaks during reconnect storms

**What:** Discord client restart → `AioPresence` raises `InvalidPipe` mid-`update()`. `tenacity` retries; on retry, the underlying `_rpc.connect()` may not reset cleanly because the previous socket reader task is still holding the loop. Memory and FD usage grow.

**Probability:** Medium-low — but probability **rises** with user behavior of "restart Discord 5x in a session."

**Mitigation:**
- `PypresencePublisher.connect()` calls `await self._rpc.close()` *before* re-`connect()` if `self._connected`.
- Add `application/orchestrator.py` graceful-shutdown: on `KeyboardInterrupt`, call `publisher.close()` and `observer.stop()` in a `finally` block.
- Integration test (Phase B test I-3): mock `AioPresence` to raise `InvalidPipe` 3 times then succeed; assert no orphan `asyncio.Task` after final retry (`asyncio.all_tasks()` baseline check).

### 1.5 Expanded Test Plan (DELIBERATE)

| Tier | Scope | Examples | Tooling |
|------|-------|----------|---------|
| **Unit** | Pure domain — parsers, classes, locations, throttle, bus | `test_regex_level_matches_spec_sample`, `test_witchhunter_resolves_to_mercenary`, `test_throttle_drops_within_window`, `test_bus_dispatches_to_multiple_handlers` | `pytest`, `pytest-mock` |
| **Integration** | Adapters with real I/O against `tmp_path` / loopback | `test_watchdog_emits_lines_on_append` (write to tmp file, assert line arrives ≤500ms), `test_json_catalog_loads_bundled_via_importlib_resources`, `test_settings_toml_overrides_env` | `pytest`, `pytest-asyncio`, `tmp_path` |
| **End-to-end** | Composition root with all adapters except external Discord | `test_orchestrator_full_flow` — fake Discord publisher counts calls, real watchdog watches a tmp `Client.txt`, append 3 log lines, assert 1 connect + 2 updates + 15s throttle gap | `pytest-asyncio`, fake `PresencePublisher` adapter |
| **Live smoke** | Real game, real Discord (manual, gated on Phase G-4) | Numbered 10-step G-4 checklist: launch order, `time_to_first_presence ≤ 8s`, `time_to_level_update ≤ 1.5s`, `time_to_reconnect ≤ 64s`, zero errors over 10-min idle | G-4 inline checklist (no separate `docs/SMOKE.md`) |
| **Cold-start** | `.exe` startup-time budget on clean Windows VM | F-4: 5 runs of `validate-config --no-discord`; p50 + p95 recorded; **p95 ≤ 8s** | `subprocess.run` in `tests/integration/test_cold_start.py` |
| **Observability** | Structured-log assertions | `test_level_change_emits_structured_event` — `structlog`'s `capture_logs()` asserts JSON record has `event="character_level_changed"`, `level=42`, `username=...`; `test_retry_logs_warning_before_sleep` | `structlog.testing.capture_logs` |
| **Type** | Static safety | `mypy --strict src/poe2_rpc tests` — must pass with zero errors. Strict-optional, no implicit-Any. | `mypy ≥1.10` |
| **Lint/Format** | Style | `ruff check src tests`, `ruff format --check src tests` | `ruff ≥0.5` |
| **Build** | Distribution | `pyinstaller PathOfExile2DiscordRPC.spec` produces `.exe`; `dist\PathOfExile2DiscordRPC.exe validate-config --no-discord` exits 0 (deeper smoke than `--version`) | `PyInstaller ≥6.14` |

---

## 2. Implementation Plan

The plan is decomposed into 7 epic phases (A–G). Each task is a 2–5 min focused unit suitable for `bd create -t task` with `bd dep add` for ordering. Tasks within a phase that have no inter-dep can be claimed in parallel; cross-phase deps are explicit.

**Epic:** `bd create -t epic "Migrate poe2-rpc to DDD/hexagonal architecture (Aggressive)"`

### Phase A — Project Skeleton

| ID | Title | Deps | TDD cycle | Files | Acceptance |
|----|-------|------|-----------|-------|------------|
| **A-1** | Add `pyproject.toml` with src-layout, deps, optional `[dev]` group | — | n/a (config) | `pyproject.toml` | `pip install -e ".[dev]"` succeeds; `[project.scripts] poe2-rpc = "poe2_rpc.cli:app"` registered |
| **A-2** | Create `src/poe2_rpc/` package skeleton with empty `__init__.py`, `__main__.py`, `__version__.py`, `py.typed`; subdirs `domain/`, `application/`, `infrastructure/` each with empty `__init__.py` | A-1 | n/a (scaffolding) | `src/poe2_rpc/**/__init__.py`, `__main__.py`, `__version__.py`, `py.typed` | `python -c "import poe2_rpc; print(poe2_rpc.__version__)"` works after `pip install -e .` |
| **A-3** | Add `tests/` skeleton with `conftest.py`, `tests/unit/`, `tests/integration/` | A-1 | RED: `tests/unit/test_smoke.py::test_package_importable` → GREEN: trivial assert → REFACTOR: none | `tests/conftest.py`, `tests/unit/test_smoke.py` | `pytest` runs and 1 test passes |
| **A-4** | Add `ruff.toml` (or `[tool.ruff]` in pyproject) — line-length 100, target-version py311, rules `E,F,W,I,N,UP,B,SIM,RET,ARG,PL` | A-1 | n/a | `pyproject.toml` (`[tool.ruff]`) | `ruff check src tests` exits 0 |
| **A-5** | Add `[tool.mypy]` strict block — `strict = true`, `python_version = "3.11"`, `mypy_path = "src"` | A-1 | n/a | `pyproject.toml` (`[tool.mypy]`) | `mypy --strict src/poe2_rpc` exits 0 (empty package = trivially strict) |
| **A-6** | Update `.github/workflows/build.yml` — split into `lint-and-test` (ubuntu) + `build` (windows, `needs: lint-and-test`). **Split path-filters per job:** `lint-and-test` paths = `['src/**', 'tests/**', 'pyproject.toml', 'locations.json']`; `build` paths = `['src/**', 'PathOfExile2DiscordRPC.spec', 'pyproject.toml', 'locations.json']` (excludes `tests/**`). Add CI step `lint-imports` (import-linter check) to `lint-and-test`. | A-1, A-4, A-5 | n/a (CI) | `.github/workflows/build.yml` | CI runs lint + typecheck + pytest + `lint-imports` before build; `tests/**`-only changes do NOT trigger build job; on `main.py` change alone, CI does NOT trigger |

**Phase A Exit gate:** `pip install -e ".[dev]" && ruff check src tests && mypy --strict src/poe2_rpc && pytest` all pass on a fresh clone.

---

### Phase B — Domain Layer (Pure Logic)

All B-tasks land 100% unit-tested. Domain imports only stdlib + `pydantic`.

| ID | Title | Deps | TDD cycle | Files | Acceptance |
|----|-------|------|-----------|-------|------------|
| **B-1** | `domain/classes.py` — port `CharacterClass` + `ClassAscendency` enums verbatim from `main.py` (lines 20–100) | A-2 | RED: `test_witchhunter_resolves_to_mercenary`, `test_smith_of_kitava_resolves_to_warrior` → GREEN: copy enums + `get_class()` → REFACTOR: keep dict mapping shape | `src/poe2_rpc/domain/classes.py`, `tests/unit/test_classes.py` | All 17 ascendancies + 7 base classes mapped; `get_ascendencies()` returns full list per class |
| **B-2** | `domain/models.py` — frozen `LevelInfo(username, base_class, ascension_class: str \| None, level: int)` + `InstanceInfo(area_code, area_display_name, level: int, seed: int)` | A-2 | RED: `test_level_info_is_frozen` (assigning to `.level` raises `ValidationError`), `test_level_info_eq_by_value` → GREEN: `BaseModel(model_config=ConfigDict(frozen=True))` → REFACTOR: ensure `__hash__` works | `src/poe2_rpc/domain/models.py`, `tests/unit/test_models.py` | Mutation raises; `LevelInfo(...) == LevelInfo(...)` by value; both models pass `mypy --strict` |
| **B-3** | `domain/locations.py` — `Location(area_code: str, display_name: str)` VO + `LocationCatalog` Protocol-friendly mapping with `resolve(area_code: str) -> str` (Map-prefix-strip + underscore-split logic from `determine_location()` lines 163–176) | A-2, B-2 | RED: `test_resolve_strips_map_prefix` (input `MapHerald_4` → matches `Herald`), `test_resolve_returns_input_when_unknown` → GREEN: port logic → REFACTOR: extract `_normalize_area_code()` helper | `src/poe2_rpc/domain/locations.py`, `tests/unit/test_locations.py` | All 4 branches of `determine_location()` covered; behavior identical to `main.py` |
| **B-4** | `domain/events.py` — frozen pydantic events: `GameStarted(log_path: Path)`, `GameStopped()`, `CharacterLevelChanged(level_info: LevelInfo)`, `AreaEntered(instance_info: InstanceInfo)` | A-2, B-2 | RED: `test_event_is_frozen`, `test_events_are_distinct_types` → GREEN: 4 BaseModels → REFACTOR: shared base `DomainEvent(BaseModel, frozen=True)` | `src/poe2_rpc/domain/events.py`, `tests/unit/test_events.py` | All 4 events frozen; `isinstance(e, DomainEvent)` works for dispatch |
| **B-5** | `domain/ports.py` — `Protocol`s: `GameDetector.detect() -> Path`, `LogStream.lines() -> AsyncIterator[str]`, `LogParser.parse(line: str) -> Iterable[DomainEvent]`, `PresencePublisher.publish(...)` + `close()`, `EventBus.subscribe/publish`, `LocationCatalog.resolve(area_code) -> str` | A-2, B-3, B-4 | RED: `test_ports_are_runtime_checkable` (or `runtime_checkable` decorator) → GREEN: define Protocols → REFACTOR: ensure no `infrastructure` import sneaks in | `src/poe2_rpc/domain/ports.py`, `tests/unit/test_ports.py` | `mypy --strict` passes; `domain/` does not import any `infrastructure/` symbol (enforced via `tests/unit/test_layering.py` walking imports) |
| **B-6** | Layering guard via **import-linter** (`pyproject.toml` config). Add `[tool.importlinter]` block with `root_package = "poe2_rpc"` and a `layers` contract `["poe2_rpc.cli", "poe2_rpc.application", "poe2_rpc.infrastructure", "poe2_rpc.domain"]`. CI step `lint-imports` runs in A-6 pipeline. **Plus** AC#2 enforcement test:
- test_no_module_level_mutable_state_in_domain: AST-scan recursively walks every `.py` file under `src/poe2_rpc/domain/` (including subpackages and `exceptions.py`). Every module-level assignment must be `Final`-typed, an `Enum` member, a `Literal`, a `type` alias, or a frozen pydantic model class definition. Plain `x = ...` at module scope fails the test. | B-5 | RED: write tests → introduce violating import / mutable state → see RED → revert → see GREEN | `pyproject.toml` (`[tool.importlinter]`), `tests/unit/test_layering.py`, `tests/unit/test_no_mutable_state.py` | `lint-imports` exits 0 on clean tree, exits non-zero if any infra import sneaks into domain; `test_no_module_level_mutable_state_in_domain` fails if any future commit adds non-`Final` module-level assignment to `domain/` |

**Phase B Exit gate:** `pytest tests/unit/` ≥ 25 tests passing; `mypy --strict src/poe2_rpc/domain` clean; `tests/unit/test_layering.py` enforces purity.

---

### Phase C — Infrastructure Adapters

Each C-task has an adapter + integration test. Where possible, adapters take filesystem paths or fakes so tests don't need a running game/Discord.

| ID | Title | Deps | TDD cycle | Files | Acceptance |
|----|-------|------|-----------|-------|------------|
| **C-1** | `infrastructure/settings.py` — `AppSettings(BaseSettings)` with `discord_client_id`, `process_name`, `presence_min_interval_seconds=15.0`, `log_level`, `log_json`, `locations_url: str \| None`; sources order: init → CLI → env (`POE2RPC_*`) → TOML → defaults. **Default config path:** `Path(os.environ["APPDATA"]) / "poe2-rpc" / "config.toml"` if `APPDATA` env var is set (Windows production); else `Path.home() / ".config" / "poe2-rpc" / "config.toml"` (cross-platform dev/test on macOS/Linux only). Note: spec snippet at `.omc/specs/deep-dive-architecture-libraries.md:253` references `~/.config/poe2-rpc/config.toml`; user can apply spec edit later to align. | A-2 | RED: `test_settings_env_overrides_defaults` (set `POE2RPC_LOG_JSON=true`, assert `True`), `test_settings_toml_overrides_default_when_no_env`, `test_default_config_path_uses_appdata_on_windows` (mock `os.environ["APPDATA"]`, assert resolved path), **AC#6 enforcement** `test_cli_arg_overrides_env_setting` (set `POE2RPC_LOG_LEVEL=ERROR`, invoke CLI with `--log-level=DEBUG`, assert effective level = DEBUG) → GREEN: implement `settings_customise_sources` with init→CLI→env→TOML→defaults order → REFACTOR: extract toml-path resolution helper | `src/poe2_rpc/infrastructure/settings.py`, `tests/integration/test_settings.py` | Defaults match spec verbatim (Discord ID `1315800372207419504`); priority order verified including CLI > env > TOML; Windows APPDATA path resolution verified |
| **C-2** | `infrastructure/logging.py` — `configure_structlog(level: str, json_output: bool)` — `ConsoleRenderer` if `not json_output and sys.stderr.isatty()` else `JSONRenderer`; processors include `add_log_level`, `TimeStamper(fmt="iso")`, `contextvars.merge_contextvars` | A-2 | RED: `test_json_renderer_emits_valid_json` (capture stderr, parse), `test_console_renderer_when_tty` (mock isatty=True) → GREEN: implement → REFACTOR: factor processors list | `src/poe2_rpc/infrastructure/logging.py`, `tests/integration/test_logging.py` | Both renderers work; `bind_contextvars(username="x")` propagates into log record |
| **C-3** | `infrastructure/detection.py` — `PsutilGameDetector(process_name)` implements `GameDetector`; `async def detect() -> Path` polls `psutil.process_iter` every 3s until found, returns `<game_dir>/logs/Client.txt` | A-2, B-5 | RED: `test_detect_returns_log_path_when_process_running` (mock `psutil.process_iter` returning fake process) → GREEN: implement → REFACTOR: extract `_iter_processes()` helper | `src/poe2_rpc/infrastructure/detection.py`, `tests/integration/test_detection.py` | Mocked `psutil` test passes; on no process, `detect()` keeps polling (test with `asyncio.wait_for(..., timeout=0.2)` raises `TimeoutError`) |
| **C-4** | `WatchdogLogStream` (event-driven log tail with bounded queue + thread-safe enqueue)

TDD:
  RED:
    - test_watchdog_emits_modified_event_on_append
    - test_observer_thread_never_blocks_on_loop          (new — mocks slow loop, asserts handler returns within 50ms)
    - test_queue_blocks_on_domain_relevant_line_when_full (back-pressure preserves AC#14 / Principle 5)
    - test_queue_drops_non_domain_lines_when_full_and_increments_metric
    - test_enqueue_retry_respects_deadline_and_raises_log_stream_stalled (reuses C-4b exception)
  GREEN:
    Implementation contract:
    - Watchdog observer thread NEVER directly touches the asyncio.Queue. All enqueues are scheduled onto the asyncio loop via `loop.call_soon_threadsafe(self._enqueue, line)`.
    - `_enqueue(self, line)` runs on the loop thread:
        1. Try `self._queue.put_nowait(line)`.
        2. On `asyncio.QueueFull`:
            - If `regex_level.search(line) or regex_instance.search(line)` (domain-relevant):
                exponential-backoff retry via `loop.call_later(delay, self._enqueue, line)` with delay starting at 0.05s, doubling each attempt, capped at 0.5s. Track per-line elapsed time; if elapsed > `AppSettings.log_stream_enqueue_deadline_seconds` (default 2.0), raise `LogStreamStalled` (the same domain exception C-4b raises).
            - Else (non-domain): drop the line, increment `dropped_non_domain_count` metric, emit `structlog.warning("log_line_dropped", offset=...)`.
    - Queue is `asyncio.Queue(maxsize=10000)`.
    - The watchdog observer thread's only operation per event is: re-read file delta from saved offset, split into lines, schedule each via `call_soon_threadsafe`. No blocking, no `run_coroutine_threadsafe`, no `Future.result()`.
  REFACTOR:
    - Extract `_enqueue` retry helper to keep `_Handler.on_modified` minimal.

Files touched:
  - src/poe2_rpc/infrastructure/streaming.py
  - src/poe2_rpc/infrastructure/settings.py  (new field log_stream_enqueue_deadline_seconds: float = 2.0)
  - tests/integration/test_streaming.py (5 tests above)

Acceptance:
  - All 5 RED tests fail before impl, pass after.
  - import-linter / B-6 still green (no domain→infra leak).
  - Observer thread is non-blocking under any queue state — verified by `test_observer_thread_never_blocks_on_loop`. | A-2, B-5 | (see above) | (see above) | (see above) |
| **C-4b** | **Stall detector** in `WatchdogLogStream`. Timer fires if no `FileSystemEvent` received within `presence_min_interval_seconds * 4`. On fire: `Observer.stop()` then `Observer.schedule()` once (recovery attempt). On retry-failure (next stall window also silent): raise `LogStreamStalled` exception (new domain-level exception in `domain/exceptions.py`). | A-2, B-5, C-4 | RED: `test_watchdog_raises_log_stream_stalled_after_silent_period` (no events → trigger one auto-recovery → still no events → assert `LogStreamStalled`); `test_watchdog_recovers_after_first_stall` (no events → recovery schedules → events flow again → assert no exception) → GREEN: implement stall timer + single retry → REFACTOR: extract `_StallWatchdog` helper | `src/poe2_rpc/infrastructure/streaming.py` (extended), `src/poe2_rpc/domain/exceptions.py`, `tests/integration/test_streaming.py` (extended) | Silent watchdog after `4 * presence_min_interval_seconds` triggers exactly one re-`schedule()`; second silent window raises `LogStreamStalled` |
| **C-5** | `infrastructure/parsing.py` — `RegexLogParser` implements `LogParser` with class-level constants `REGEX_LEVEL = re.compile(r": (\w+) \(([\w\s]+)\) is now level (\d+)")` and `REGEX_INSTANCE = re.compile(r'Generating level (\d+) area "([^"]+)" with seed (\d+)')` (verbatim from CLAUDE.md); `parse(line)` yields `CharacterLevelChanged` and/or `AreaEntered` events; resolves base→ascendancy via `ClassAscendency._value2member_map_` | A-2, B-1, B-2, B-4, B-5 | RED: `test_regex_level_matches_spec_sample("...: Foo (Witchhunter) is now level 42")` → assert `CharacterLevelChanged(level_info.username='Foo', base_class='Mercenary', ascension_class='Witchhunter', level=42)`; `test_regex_instance_matches_spec_sample('Generating level 5 area "G1_4_Brambleghast" with seed 12345')` → GREEN: port logic from `find_last_level_up` + `find_instance` → REFACTOR: split private helpers `_classify_level()` + `_resolve_area()` | `src/poe2_rpc/infrastructure/parsing.py`, `tests/unit/test_parsing.py` | Both regexes byte-identical to CLAUDE.md; ascendancy resolution covers all 17 from B-1; unknown class → `ascension_class=None` (was `"Unknown"` string in main.py — convert to `None` for type-safety, presence layer handles None branch) |
| **C-6** | `infrastructure/catalog.py` — `JsonLocationCatalog` implements `LocationCatalog`; `from_bundled()` uses `importlib.resources.files("poe2_rpc") / "locations.json"`; `from_url(url)` fetches once at construct-time; both delegate `resolve()` to domain logic from B-3 | A-2, B-3, B-5 | RED: `test_catalog_from_bundled_loads_known_area` (uses `importlib.resources` against a tiny `locations.json` fixture under `tests/fixtures/`) → GREEN: implement → REFACTOR: share resolve-logic with B-3 | `src/poe2_rpc/infrastructure/catalog.py`, `tests/integration/test_catalog.py`, fixture `tests/fixtures/locations.json` | Bundled catalog reads via `importlib.resources` (no `Path("locations.json")` cwd-relative read); URL override works |
| **C-7a** | `infrastructure/presence.py` — `PypresencePublisher(client_id)` implements `PresencePublisher` using `AioPresence`. **Connect retry policy (separate from publish):** `@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=32), retry=retry_if_exception_type((ConnectionError, OSError, BrokenPipeError, InvalidPipe, asyncio.IncompleteReadError)), before_sleep=before_sleep_log(_stdlib_logger, logging.WARNING))`. `connect()` calls `await self._rpc.close()` first if `self._connected` (PM-3 mitigation); `close()` cleans up. **Pre-close gate:** before C-7a closes, query `mcp__plugin_compound-engineering_context7__query-docs` (library_id `/websites/qwertyquerty_github_io_pypresence_html`) for `InvalidPipe` MRO and `asyncio.IncompleteReadError` wrapping behavior. Update `retry_if_exception_type` tuple per finding. | A-2, B-5 | RED: `test_connect_retries_5_times_with_exponential_backoff` (fake `AioPresence` raises `InvalidPipe` 4x then succeeds, assert exactly 5 attempts and ≥ (2+4+8+16) seconds between first and last sleep); `test_connect_gives_up_after_5_attempts`; `test_reconnect_closes_previous_socket` (PM-3) → GREEN: implement → REFACTOR: factor connect-retry decorator into module-level constant `_CONNECT_RETRY` | `src/poe2_rpc/infrastructure/presence.py`, `tests/integration/test_presence.py` | All 3 tests pass; `before_sleep_log` emits `WARNING`-level structured record per attempt; Context7 verification recorded in commit message |
| **C-7b** | **Publish retry policy (split from connect):** `publish()` decorated with `@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), retry=retry_if_exception_type((BrokenPipeError, InvalidPipe, OSError)), before_sleep=before_sleep_log(_stdlib_logger, logging.WARNING))`. **Critical:** publish retries are NOT multiplied through nested connect retries — if publish needs to reconnect mid-publish, the connect call uses its own (already-spent) retry budget without restarting publish's. | A-2, B-5, C-7a | RED: `test_publish_does_not_multiply_retries_through_connect` (force `publish()` to invoke `connect()` once internally; assert at most 3 publish attempts total even when each one calls connect); `test_publish_retries_on_broken_pipe` (raise `BrokenPipeError` 2x then succeed; assert 3 total attempts); `test_publish_gives_up_after_3_attempts` → GREEN: implement decorator with isolated retry budget → REFACTOR: factor publish-retry decorator into module-level constant `_PUBLISH_RETRY` | `src/poe2_rpc/infrastructure/presence.py` (extended), `tests/integration/test_presence.py` (extended) | Publish capped at 3 attempts (not 3×5=15); both decorators co-exist without retry-multiplication |

**Phase C Exit gate:** All adapters tested with fakes/`tmp_path`; no test requires a real game or real Discord; `mypy --strict src/poe2_rpc` still clean.

---

### Phase D — Application Layer

| ID | Title | Deps | TDD cycle | Files | Acceptance |
|----|-------|------|-----------|-------|------------|
| **D-1** | `application/bus.py` — `AsyncioEventBus` implements `EventBus`; `subscribe(event_type, handler)` registers async callable; `publish(event)` dispatches to all matching handlers concurrently via `asyncio.gather` (errors logged, not raised — one bad handler doesn't kill the bus) | A-2, B-4, B-5 | RED: `test_bus_dispatches_to_multiple_handlers`, `test_bus_isolates_handler_exceptions` (one handler raises, other still called) → GREEN: implement → REFACTOR: type the registry as `dict[type[DomainEvent], list[Handler]]` | `src/poe2_rpc/application/bus.py`, `tests/unit/test_bus.py` | Multi-handler dispatch + exception isolation verified |
| **D-2** | `application/throttle.py` — `PresenceThrottle(min_interval_seconds: float)` — async-aware: `should_publish(now: float) -> bool` returns False if last publish < min_interval ago; also exposes `default_state_text()` pure function (the `random_status()` list from main.py lines 119–132) | A-2 | RED: `test_throttle_drops_within_window`, `test_throttle_allows_after_window`, `test_default_state_text_is_one_of_known` → GREEN: implement → REFACTOR: inject clock for testability (`Callable[[], float] = time.monotonic`) | `src/poe2_rpc/application/throttle.py`, `tests/unit/test_throttle.py` | 15s default; injectable clock makes tests deterministic |
| **D-3** | `application/handlers.py` — `on_level_changed(event, *, publisher, throttle, current_state)` and `on_area_entered(event, *, publisher, throttle, current_state)` async functions. Format: `details = f"{username} ({base_class}" + opt(" \| {ascension}") + f" - Lvl {level})"` (preserves main.py format for non-None ascendancy; None branch yields `"Foo (Mercenary - Lvl 42)"` — see ADR §3 Behavior Changes #1); `state = f"In: {area_display_name} (Lvl {level})"` or `default_state_text()`; compute `small_image = ascension_class.lower().replace(" ", "_")` (preserve commit `5ae14e6` enforcement). Handlers must `bind_contextvars(username=..., character_class=..., area=...)` before any logging call so observability principle (AC#7) is satisfied. | A-2, B-2, B-4, C-7a, C-7b, D-2 | RED: `test_on_level_changed_formats_details_with_ascendancy`, `test_on_level_changed_omits_ascendancy_pipe_when_none` (None branch — was "Unknown" in main.py), `test_on_area_entered_formats_in_state`, `test_small_image_lowercases_and_underscores` ("Smith of Kitava" → "smith_of_kitava"), **AC#7 enforcement** `test_handlers_bind_username_class_area_into_logs` (trigger `CharacterLevelChanged` + `AreaEntered`; capture structlog output via `capture_logs()`; assert all three keys `username`, `character_class`, `area` present in the structured event) → GREEN: implement → REFACTOR: extract `_format_details()` pure helper | `src/poe2_rpc/application/handlers.py`, `tests/unit/test_handlers.py` | All format strings byte-identical to current main.py output for non-None ascendancy; None branch yields `"Foo (Mercenary - Lvl 42)"` (no pipe); structured logs carry `username`, `character_class`, `area` per AC#7 |
| **D-4** | `application/orchestrator.py` — `Orchestrator(detector, parser, publisher, catalog, bus, settings, log_stream_factory)`. **Factory injection (Principle 4 enforcement):** instead of constructing `WatchdogLogStream` from `log_path`, the orchestrator accepts `log_stream_factory: Callable[[Path, asyncio.AbstractEventLoop], LogStream]` injected by `cli.py`. The application layer never imports `WatchdogLogStream` directly. async `run()` method: 1) detect game → `bus.publish(GameStarted)`, 2) `stream = log_stream_factory(log_path, loop)`, 3) `async for line in stream.lines(): for event in parser.parse(line): await bus.publish(event)`, 4) on cancel/`KeyboardInterrupt`: `await publisher.close()`, observer.stop in finally; subscribes handlers from D-3 to the bus at startup. | A-2, B-5, C-3, C-4, C-4b, C-5, C-6, C-7a, C-7b, D-1, D-2, D-3 | RED: `test_orchestrator_full_flow` (e2e) — fake detector returns tmp Client.txt path; fake `log_stream_factory` returns a queue-backed `LogStream`; append 3 lines; assert publisher received exactly: 1 connect, level-change update, area update; assert ≥15s gap between consecutive updates. **Layering test** `test_orchestrator_does_not_import_infrastructure` — `ast.parse(application/orchestrator.py)`, walk `Import`/`ImportFrom` nodes, assert no symbol from `poe2_rpc.infrastructure` is imported. → GREEN: implement → REFACTOR: factor wiring into `_subscribe_handlers()` private | `src/poe2_rpc/application/orchestrator.py`, `tests/integration/test_orchestrator.py`, `tests/unit/test_orchestrator_layering.py` | E2E test passes with injected factory; graceful shutdown verified (no orphan tasks via `asyncio.all_tasks()`); `test_orchestrator_does_not_import_infrastructure` proves Principle 4 |

**Phase D Exit gate:** `pytest tests/integration/test_orchestrator.py` green; orchestrator never imports from `infrastructure/*` directly (only via constructor params, types are Protocols from `domain/ports`).

---

### Phase E — CLI + Composition Root

| ID | Title | Deps | TDD cycle | Files | Acceptance |
|----|-------|------|-----------|-------|------------|
| **E-1** | `cli.py` — Typer `app`; commands `run` (default), `once` (single update + exit), `validate-config` (loads + prints settings, exit 0), version via `--version` callback. **Add `--no-discord` flag to `validate-config`:** when set, the command loads settings + bundled `locations.json` + initializes `structlog` WITHOUT contacting Discord IPC. This validates the `pydantic-settings` + TOML loader + structlog + watchdog import chain end-to-end (used by F-3 smoke step). Composition root assembles all adapters + orchestrator (provides `log_stream_factory=lambda path, loop: WatchdogLogStream(path, loop)` per Principle 4). | A-2, C-1, C-2, C-3, C-4, C-4b, C-5, C-6, C-7a, C-7b, D-1, D-2, D-3, D-4 | RED: `test_cli_validate_config_exits_zero` (Typer `CliRunner`), `test_cli_validate_config_no_discord_skips_ipc` (assert no `AioPresence` instantiated when `--no-discord` is set), `test_cli_version_prints_version`, `test_cli_once_runs_one_iteration` (fake factories injected via patching) → GREEN: implement → REFACTOR: extract `build_orchestrator(settings) -> Orchestrator` factory for testability | `src/poe2_rpc/cli.py`, `tests/integration/test_cli.py` | All CLI commands tested via `typer.testing.CliRunner`; `poe2-rpc --help` shows all commands; `validate-config --no-discord` exits 0 without Discord IPC |
| **E-2** | `__main__.py` — `from .cli import app; app()` so `python -m poe2_rpc` works | A-2, E-1 | RED: `test_module_runs_via_python_dash_m` (`subprocess.run([sys.executable, '-m', 'poe2_rpc', '--version'])` exit 0) → GREEN: 2-line implementation → REFACTOR: none | `src/poe2_rpc/__main__.py` | `python -m poe2_rpc --version` prints version |

**Phase E Exit gate:** `poe2-rpc run` boots end-to-end against fakes; `poe2-rpc validate-config` returns 0; `python -m poe2_rpc` works.

---

### Phase F — Packaging

| ID | Title | Deps | TDD cycle | Files | Acceptance |
|----|-------|------|-----------|-------|------------|
| **F-1** | `PathOfExile2DiscordRPC.spec` — Analysis points at `src/poe2_rpc/__main__.py`, `pathex=['src']`, `datas=[('locations.json', '.')]`, **expanded `hiddenimports`** = `['watchdog.observers.read_directory_changes', 'watchdog.observers.winapi', 'pydantic_core._pydantic_core', 'pydantic._internal._model_construction', 'pydantic_settings.sources.providers.toml', 'structlog._log_levels', 'tenacity']`. Use `--collect-submodules` for: `pydantic`, `pydantic_settings`, `structlog`, `watchdog`, `tenacity`, `pypresence`. `name='PathOfExile2DiscordRPC'`, `onefile=True`, `console=True`. **Acceptance includes** explicit `pyinstaller --debug=imports` smoke run on a clean Windows VM that succeeds without `ModuleNotFoundError`. | A-2, E-2 | n/a (build artifact); validated by F-2/F-3/F-4 | `PathOfExile2DiscordRPC.spec` | File matches spec snippet; `--debug=imports` build produces no missing-module diagnostics |
| **F-2** | Bundle `locations.json` for `importlib.resources` access — copy `locations.json` into `src/poe2_rpc/` (or add MANIFEST.in / pyproject.toml `[tool.setuptools.package-data]` entry); `JsonLocationCatalog.from_bundled()` reads via `importlib.resources.files("poe2_rpc") / "locations.json"` | A-1, C-6, F-1 | RED: `test_bundled_catalog_works_in_dev_install` — after `pip install -e .`, `from_bundled()` resolves a known area → GREEN: add package-data entry → REFACTOR: none | `pyproject.toml` (`[tool.setuptools.package-data]`), `src/poe2_rpc/locations.json` (or symlink/copy from root) | Test passes both in dev-install and in the .exe (validated by F-3) |
| **F-3** | Update `.github/workflows/build.yml` build job: `pip install -e .` + `pip install pyinstaller`; `pyinstaller PathOfExile2DiscordRPC.spec`; **deeper smoke step** `dist\PathOfExile2DiscordRPC.exe validate-config --no-discord` (validates pydantic-settings + TOML loader + structlog + watchdog import chain end-to-end; replaces shallow `--version` check); upload artifact `dist/PathOfExile2DiscordRPC.exe`. | A-6, F-1, F-2 | n/a (CI); evidence: green run | `.github/workflows/build.yml` | CI build job green on a `workflow_dispatch` trigger; `validate-config --no-discord` smoke step exits 0 — proves all hidden imports resolve and TOML+structlog+watchdog chain initializes without IPC |
| **F-4** | **Cold-start benchmark** (positioned between F-3 and Phase G). Run `dist\PathOfExile2DiscordRPC.exe validate-config --no-discord` 5 times on a clean Windows VM; record p50 and p95 cold-start (process spawn → first stdout line). **Budget: p95 ≤ 8s on Windows runner.** Failure action: file follow-up `bd` issue, do NOT block release of first DDD .exe but mark as known regression in release notes. | F-3 | RED: `tests/integration/test_cold_start.py` invokes `subprocess.run([exe_path, "validate-config", "--no-discord"], capture_output=True)` 5 times, asserts each `< 8.0` seconds → GREEN: implement test → if cold-start exceeds budget, the test fails on the Windows runner | `tests/integration/test_cold_start.py`, `.github/workflows/build.yml` (cold-start step) | p95 cold-start ≤ 8s recorded in CI logs; budget breach files `bd` issue and annotates release notes (does not block first release) |

**Phase F Exit gate:** A CI run produces `PathOfExile2DiscordRPC.exe`, the deep smoke `validate-config --no-discord` step exits 0, and F-4 cold-start measurement is recorded (p95 ≤ 8s, or follow-up `bd` issue filed if budget exceeded).

---

### Phase G — Cutover

| ID | Title | Deps | TDD cycle | Files | Acceptance |
|----|-------|------|-----------|-------|------------|
| **G-1** | Validate regex contracts against a real `Client.txt` sample — capture sample, write `tests/fixtures/sample_client.txt`, add `test_regex_against_real_sample` that runs both regexes over the file and asserts ≥1 match each (or skip with reason if fixture absent) | C-5 | RED: write test (skipped without fixture) → GREEN: capture fixture, test passes → REFACTOR: none | `tests/fixtures/sample_client.txt`, `tests/integration/test_regex_real_sample.py` | Regexes match real-world log lines verbatim |
| **G-2** | Delete `main.py`, delete `requirements.txt` (replaced by pyproject), update `.gitignore` if needed. **Dependency: blocked-by G-4 — `bd dep add G-2 G-4 --type blocks`.** G-2 cannot close until G-4 (live smoke) passes. | G-3, G-4 | n/a (deletion) | (deleted) `main.py`, `requirements.txt` | Repo no longer contains `main.py`; CI still green; G-4 live-smoke checklist already passed |
| **G-3** | Update `README.md` and `CLAUDE.md` — replace "single-file" guidance with `src/poe2_rpc/` layout, update install command to `pip install -e ".[dev]"`, update run command to `poe2-rpc run`, document `%APPDATA%\poe2-rpc\config.toml` on Windows (and `~/.config/poe2-rpc/config.toml` for cross-platform dev), update "Adding a new ascendancy" section to point at `domain/classes.py`, update "Regex contracts" section to point at `infrastructure/parsing.py`. (Smoke checklist lives inline in G-4 acceptance, not in a separate `docs/SMOKE.md`.) | G-1 | n/a (docs); reviewed via `compound-engineering:document-review` or peer review | `README.md`, `CLAUDE.md` | Docs accurately describe new layout; "Build & Test" section runs green on a clean clone |
| **G-4** | **Live smoke run on a real Windows box.** Run the explicit numbered checklist below; capture screenshots and logs into release notes. | F-3, F-4, G-3 | n/a (manual) | Release notes | Every checklist item passes within its budget; release notes attach the captured timings |

**G-4 Acceptance Checklist (run on a Windows VM with PoE2 + Discord):**

1. Launch Discord; wait until status pane shows "Connected".
2. Launch PoE2 Steam build; wait for character-select screen.
3. Start `dist/PathOfExile2DiscordRPC.exe`; record `t0`.
4. Within 8s: presence detail string visible in Discord — record `time_to_first_presence`.
5. Enter game world; level character once.
6. Within 1.5s of in-game level-up notification: Discord presence reflects new level — record `time_to_level_update`.
6b. Open the JSON log written during steps 5-6. Locate the structlog event named `character_level_changed`. Assert that keys `username`, `character_class`, `area` are present and non-empty in that record. (This proves AC#7 holds in the wired-up binary, not just in unit-test isolation.)
7. Kill Discord client; wait 5s; relaunch Discord.
8. Within 64s of relaunch: presence reconnects — record `time_to_reconnect`.
9. Run for 10 minutes idle; tail JSON log; assert zero `level=error` records.
10. **Acceptance:** `time_to_first_presence ≤ 8s` AND `time_to_level_update ≤ 1.5s` AND `time_to_reconnect ≤ 64s` AND zero errors during the 10-minute idle window AND character_level_changed log record carries username/character_class/area.

**Phase G Exit gate:** `main.py` deleted; live smoke recorded in release notes; tag pushed.

---

## 3. Architecture Decision Record (ADR)

### Behavior Changes vs main.py

1. **Unknown-ascendancy detail string.** `main.py` renders `"Foo (Mercenary | Unknown - Lvl 42)"` (line 188 sets `ascension_class = "Unknown"` sentinel; line 258 stringifies it). New code renders `"Foo (Mercenary - Lvl 42)"` — omits the `| Unknown` segment. Deliberate UX improvement: the literal `"Unknown"` was inadvertent leakage of an internal sentinel; new model uses `ascension_class: str | None` and the formatter omits the pipe segment when None.
2. **`locations.json` source.** `main.py` line 137 falls back to fetching `locations.json` from the GitHub `main` branch URL when the local file is missing. New code uses bundled `locations.json` (via `importlib.resources.files("poe2_rpc")`) as the canonical source; URL fetch is opt-in only via `AppSettings.locations_url`. No silent network fetch at startup.
3. **Retry policies (split).** `connect()` uses `5 × wait_exponential(min=2, max=32)`; `publish()` uses `3 × wait_exponential(min=1, max=8)`. Two distinct policies because connect failure is rare-and-recoverable (large window, more attempts), publish failure is frequent-and-rate-limited (small window, fewer attempts) — and to prevent 3×5=15 attempt amplification.
4. **Config file location.** New addition (no prior config existed). Default `%APPDATA%\poe2-rpc\config.toml` on Windows; `~/.config/poe2-rpc/config.toml` on macOS/Linux for dev/test.
5. **Config path spec drift (intentional).** The source spec at `.omc/specs/deep-dive-architecture-libraries.md:253` literally writes `toml_file=str(Path.home() / ".config" / "poe2-rpc" / "config.toml")`. The implementation uses `Path(os.environ["APPDATA"]) / "poe2-rpc" / "config.toml"` on Windows (production target). The `~/.config/...` path is retained as a cross-platform dev/test fallback only. Rationale: Windows users have no `~/.config` convention; defaulting there would orphan their config. Follow-up: file a `bd` issue post-consensus to amend the spec snippet to match. The migration does NOT block on the spec edit.

### Decision

Migrate Path-Of-Exile-2-RPC from a single-file Python script to a hexagonal/DDD package (`src/poe2_rpc/`) with strict layer separation (`domain/` pure, `application/` orchestrating, `infrastructure/` adaptive), an asyncio event-bus, watchdog-driven event-stream replacing 5s polling, AioPresence with tenacity-decorated reconnect, pydantic-settings for config, structlog for observability, typer for CLI, and PyInstaller `--onefile` distribution unchanged. Single binary `PathOfExile2DiscordRPC.exe` retained.

### Drivers

- **Latency** — sub-second presence updates via `watchdog.Observer` + `ReadDirectoryChangesW`, replacing `time.sleep(5)` polling.
- **Reliability** — `tenacity` exponential-backoff reconnect with structured retry telemetry; explicit graceful shutdown of `AioPresence` socket.
- **Testability + Observability** — domain layer 100% unit-testable without I/O; `structlog.contextvars` carries (`username`, `area`, `level`) through every event; `mypy --strict` enforced.

### Alternatives Considered

| Alternative | Why not |
|---|---|
| **Conservative — single-file evolution.** Stay in `main.py`; swap libraries (watchdog, tenacity, structlog) but keep flat structure. | User explicitly rejected in interview Round 2 ("Aggressive DDD"). Cannot satisfy Acceptance Criteria #1 (`src/poe2_rpc/` with explicit layers). `mypy --strict` against a 330-LOC script with global `rpc` is uneconomic. Observability via `bind_contextvars` requires a real call-graph. |
| **Balanced — minimal package (Hexagonal-Lite).** Single `src/poe2_rpc/` with `domain.py + adapters.py + app.py + cli.py` (no application-layer split, no event-bus). | Compromises testability (App becomes God-object as we add AFK detection, non-Steam client support, party-conflict resolution from README) and observability (no central event-typed dispatch → no clean place to bind contextvars per event-type). User picked all 4 priorities (no compromise). |
| **Aggressive DDD — full hexagonal (CHOSEN).** | All 4 priorities satisfied; future-proof for known follow-ups. |
| **Dependency-injection container (`punq` / `dependency-injector`).** | Spec explicitly excludes ("конструкторная инъекция руками в `cli.py`"). Adds a runtime dependency without buying anything for a 1-binary app with 1 composition root. |
| **Multi-process / IPC.** | Out of scope (Non-Goals section of spec). |

### Consequences

**Positive:**
- Sub-second presence updates (vs 5s polling).
- Domain logic 100% unit-testable with no `psutil`/`pypresence` mocks.
- `structlog` + JSON logs unblock future telemetry without code changes.
- Adding AFK detection / non-Steam client / party-conflict-resolution becomes a new handler subscription, not a `monitor_log()` rewrite.
- `mypy --strict` catches refactoring errors before runtime.

**Negative:**
- ~1500 LOC of new package code for a 330-LOC script. Higher onboarding cost for a casual contributor.
- `.exe` size grows by ~5–8 MB (pydantic + watchdog + structlog + typer). Acceptable for desktop tool.
- More CI surface (lint + typecheck + pytest + build) → longer CI wall-time.
- Watchdog-on-Windows is a known PyInstaller gotcha; managed via `hiddenimports` (PM-2).

**Neutral:**
- Discord App ID `1315800372207419504` and binary name `PathOfExile2DiscordRPC.exe` unchanged — release-asset URLs continue to work.
- `locations.json` becomes bundled (no runtime fetch); existing installs upgrade via new `.exe` release.

### Follow-ups (deferred — explicit non-goals of this migration)

- AFK detection (README open work) → new `application/handlers.py::on_idle_detected` + `infrastructure/idle_detector.py`.
- Non-Steam PoE2 client support → second `GameDetector` adapter; CLI `--client` flag selects.
- Party-conflict / multi-player detection → enrich `RegexLogParser` with player-identity match; route via event-bus.
- Tray-icon / background-service launch (README open work) → separate epic; `pystray` or Windows service wrapper.
- Telemetry export → `structlog` JSON → file → optional log-shipper.

---

## 4. Acceptance Criteria Coverage Matrix

| # | Acceptance Criterion (from spec) | Satisfied by |
|---|---|---|
| 1 | `src/poe2_rpc/` package with `domain/`, `application/`, `infrastructure/`, `cli.py` | A-2 |
| 2 | All domain models frozen pydantic or Enum; no global mutable state | B-1, B-2, B-4, plus B-6 (`test_no_module_level_mutable_state_in_domain` AST scan) |
| 3 | All ports as `typing.Protocol` in `domain/ports.py`; domain doesn't import infrastructure | B-5, B-6 (import-linter layered contract) |
| 4 | `WatchdogLogStream` event-driven via `Observer + FileModifiedEvent`; raises `RuntimeError` on observer-start failure (no silent polling fallback); bounded queue with selective drop honoring Principle 5; stall detector | C-4, C-4b |
| 5 | `PypresencePublisher` uses `AioPresence` + tenacity-backed retries; **split policies** — `connect`: `5 × wait_exponential(min=2, max=32)`; `publish`: `3 × wait_exponential(min=1, max=8)`; `before_sleep_log` on both | C-7a, C-7b |
| 6 | `AppSettings(BaseSettings)` priority: init → CLI → env (`POE2RPC_*`) → TOML → defaults; Windows default `%APPDATA%\poe2-rpc\config.toml`; verified by `test_cli_arg_overrides_env_setting` | C-1 |
| 7 | `structlog` configured: `ConsoleRenderer` if TTY else `JSONRenderer`; `bind_contextvars` for username/class/area; verified by `test_handlers_bind_username_class_area_into_logs` | C-2 (renderer); D-3 (binding + AC#7 enforcement test) |
| 8 | Typer CLI: `run` (default), `once`, `validate-config` (with `--no-discord`), `--version` | E-1 |
| 9 | Pytest unit tests on parsers, classes, locations, throttle, bus; integration on `WatchdogLogStream` via `tmp_path`; cold-start benchmark | B-1..B-5 (units) + C-4 / C-4b (watchdog integration) + D-1, D-2 (units) + F-4 (cold-start) |
| 10 | `mypy --strict src/poe2_rpc` passes | A-5 (config); enforced in CI by A-6; verified at every phase exit gate |
| 11 | `ruff check` + `ruff format` pass | A-4 (config); enforced in CI by A-6 |
| 12 | `pyinstaller PathOfExile2DiscordRPC.spec` builds working `.exe` with all hidden imports + collected submodules | F-1, F-2, F-3, F-4 |
| 13 | CI workflow updated with **split path-filters per job** (`lint-and-test` vs `build`) + `lint-imports` + `lint`, `typecheck`, `test` jobs before `build` | A-6, F-3, F-4 |
| 14 | `regex_level` and `regex_instance` preserved verbatim in `infrastructure/parsing.py` as class-level constants | C-5; validated against real sample by G-1 |

**Coverage:** 14 / 14 acceptance criteria mapped to specific tasks. Task ID changes from iteration 1: C-7 split into C-7a + C-7b; C-4b added (stall detector); F-4 added (cold-start benchmark). No criterion is unattributed.

---

## 5. Plan Metadata

- **Estimated tasks:** 35 (A: 6, B: 6, C: 9, D: 4, E: 2, F: 4, G: 4) plus 1 epic. Iteration-2 additions: C-4b (stall detector), C-7a/C-7b (split retry), F-4 (cold-start benchmark).
- **Estimated complexity:** HIGH (full architectural migration; live-target verification required).
- **Critical path:** A-1 → A-2 → B-2 → B-4 → B-5 → C-5 / C-7a / C-7b → D-3 → D-4 → E-1 → F-1/F-2/F-3 → F-4 → G-4 → G-2 (G-3 runs in parallel before G-2; G-2 blocked-by G-4).
- **Parallelizable:** B-1/B-2/B-3/B-4 (independent within domain); C-1/C-2/C-3 (independent infra); C-4 + C-4b sequenced; C-7a → C-7b sequenced; F-1/F-2 prep for F-3.
- **Open questions** — to be appended to `.omc/plans/open-questions.md`:
  - Should `ascension_class=None` (typed) or `ascension_class="Unknown"` (current main.py string) be the type used in `LevelInfo`? **Plan assumes `None`** for type-safety; presence-handler omits the `| {ascension}` segment when None. Confirm before B-2 close.
  - Where does the bundled `locations.json` live in source tree — `src/poe2_rpc/locations.json` (canonical) or root-level + `package-data` mapping? **Plan assumes the latter** for single source of truth at repo root. Confirm before F-2.
  - Does `--debug-watchdog` CLI flag stay or get cut for v1? **Plan assumes stays** as a triage aid for PM-1; cheap to add at E-1. Confirm before E-1.

---

## Plan Summary

**Plan saved to:** `.omc/plans/ralplan-architecture-libraries.md`

**Scope:**
- 35 tasks across 7 epic phases (A–G), spanning ~26 new files in `src/poe2_rpc/` and ~28 new test files
- Estimated complexity: HIGH

**Key Deliverables:**
1. `src/poe2_rpc/` hexagonal package with strict domain/application/infrastructure separation; orchestrator uses factory injection (Principle 4)
2. Sub-second log streaming (`watchdog`) replacing 5s polling; bounded queue with selective drop policy + stall detector
3. `tenacity`-backed Discord IPC reconnect with split policies (connect: 5×, publish: 3×) and structured telemetry
4. `pydantic-settings` config (Windows `%APPDATA%` default) + `structlog` observability + `typer` CLI with `validate-config --no-discord`
5. PyInstaller `--onefile` build emitting `PathOfExile2DiscordRPC.exe` (unchanged artifact name) with expanded `hiddenimports` + `--collect-submodules`
6. CI split into `lint-and-test` (Ubuntu) + `build` (Windows) with **per-job path-filters** + import-linter layered contract
7. Cold-start benchmark (F-4) and 10-step live-smoke checklist (G-4) gating release

**Consensus mode (Iteration 2):**
- RALPLAN-DR: 5 Principles (3/4/5 reworded), 3 ranked Drivers, 3 Options (Option C invalidation re-defended on technical grounds), 3-scenario Pre-mortem, 9-tier Test Plan (added Cold-start)
- ADR: Behavior Changes vs main.py (4 items), Decision, 3 Drivers, 5 Alternatives considered with why-not, Positive/Negative/Neutral consequences, 5 Follow-ups
- DELIBERATE additions: Pre-mortem (PM-1/PM-2/PM-3) + Expanded test plan + AC#2/#6/#7 enforcement tests + cold-start benchmark + live-smoke checklist all present
