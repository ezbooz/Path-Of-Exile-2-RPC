<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-05 | Updated: 2026-05-05 -->

# infrastructure

## Purpose
Adapter layer: concrete implementations of `domain.ports` Protocols backed by third-party libraries (psutil, watchdog, pypresence, pydantic-settings, structlog, pystray, pylnk3). The composition root in `cli.py` instantiates these and wires them into the application layer. Adapters import from `domain` for Protocols/VOs but never from `application`.

## Key Files
| File | Description |
|------|-------------|
| `detection.py` | `PsutilGameDetector` — `is_running()` / blocking `log_path()`; iterates over both `PathOfExileSteam.exe` and `PathOfExile.exe` per the `process_name: list[str]` setting (PR-1). |
| `log_stream.py` | `WatchdogLogStream` — event-driven via `ReadDirectoryChangesW` on Windows, falls back to polling elsewhere; thread-safe enqueue using `loop.call_soon_threadsafe`. Async-native; bridged to sync `LogStream` Protocol via `_SyncLineIterator` in `cli.py`. |
| `parsing.py` | `regex_level` / `regex_instance` (verbatim from `main.py:273-274`) + `RegexLogParser` adapter implementing `LogParser`. |
| `presence.py` | `PypresencePublisher` (`AioPresence` + tenacity split-retry: connect 5×wait_exponential(2,32), publish 3×wait_exponential(1,8)). Holds `small_image_override` for AFK/DND state (PR-3) with restore-on-clear. |
| `settings.py` | `AppSettings` (pydantic-settings `BaseSettings`); `Annotated[list[str], NoDecode]` + `field_validator(mode="before")` to coerce legacy single-string `process_name` envs into a list. |
| `catalog.py` | `load_bundled_catalog()` reads bundled `locations.json` via `importlib.resources.files("poe2_rpc")` so PyInstaller `--onefile` keeps working. |
| `logging.py` | structlog config — `ConsoleRenderer` for dev TTY, `JSONRenderer` for prod. |
| `tray.py` | `pystray` system-tray service (PR-4); runs orchestrator on a background thread; `Quit` triggers `Orchestrator.stop()` for orderly shutdown. Lazy-imports `pystray` / `Pillow` so headless installs don't pay the cost. |
| `autostart.py` | `pylnk3` Windows Startup-folder shortcut writer (PR-4); points at the running interpreter or packaged `.exe` and passes `tray --quiet`. Lazy-imports `pylnk3`. |

## For AI Agents

### Working In This Directory
- **Never import from `application`.** Adapters know about Protocols and VOs in `domain`, nothing higher.
- All concrete adapters MUST satisfy a `runtime_checkable` Protocol in `domain/ports.py`. Add the Protocol there first; the test in `tests/unit/test_<module>.py` should `assertIsInstance(adapter, ProtocolType)`.
- Optional-extras pattern: hexagonal modules import third-party deps at module top behind `try import / except ImportError as e: raise ... from e` to fail loudly. The upstream-PR backports re-encode this as lazy-import-inside-helper (see memory `feedback_optional_deps_backport_idiom.md`).
- Tenacity split-retry policies live here, not in application code (presence connect vs publish have different retry budgets — see commit history for context).

### Testing Requirements
- `tests/unit/test_detection.py` — covers list-of-process-names + legacy-string coercion.
- `tests/unit/test_log_stream.py` — covers the watchdog → asyncio-queue bridge.
- `tests/unit/test_parsing.py` — regex contract tests; **don't break the contracts in `parsing.py:regex_level` / `regex_instance` without verifying against a real `Client.txt` sample** (`tests/integration/test_regex_real_sample.py`).
- `tests/unit/test_presence_connect.py`, `test_presence_publish.py`, `test_afk.py` — split coverage for the two retry policies + AFK override.
- `tests/unit/test_settings.py` — env-var coercion + defaults.
- `tests/unit/test_tray.py`, `test_autostart.py` — lazy-import + extras-missing gate.

### Common Patterns
- `pathlib.Path` everywhere, with explicit `encoding="utf-8"` on file reads.
- `importlib.resources.files("poe2_rpc")` for bundled assets — never cwd-relative `Path("locations.json")`.
- Tenacity decorators (split policies) over hand-rolled `time.sleep(2 ** retries)`.
- structlog event names are nouns-or-noun-phrases (`presence.publish.success`, `log_stream.line_received`).

## Dependencies

### Internal
- `domain.ports`, `domain.models`, `domain.events`, `domain.locations`, `domain.classes`, `domain.exceptions`.

### External
- `psutil` — process discovery.
- `watchdog` — `ReadDirectoryChangesW` log tailing.
- `pypresence` — Discord IPC (`AioPresence`).
- `pydantic-settings` — `BaseSettings` + env-var coercion.
- `structlog` — structured logging.
- `tenacity` — split-policy retries.
- `pystray`, `Pillow` — optional `[tray]` extra.
- `pylnk3` — optional `[tray]` extra (Windows Startup shortcut).

<!-- MANUAL: Manually added notes below this line are preserved on regeneration -->
