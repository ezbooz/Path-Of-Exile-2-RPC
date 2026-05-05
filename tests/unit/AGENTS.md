<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-05 | Updated: 2026-05-05 -->

# unit

## Purpose
Fast, isolated tests with no real I/O. Covers domain VOs, application orchestration with fakes, and infrastructure adapters mocked at the third-party seam (psutil, watchdog, pypresence). Includes the AST guards that fail CI if hexagonal contracts drift.

## Key Files
| File | Description |
|------|-------------|
| `test_no_mutable_state.py` | AST guard — fails if any `dataclass` or non-`frozen=True` `BaseModel` lands in `domain/`. |
| `test_layering.py` | AST guard — fails if `application/` or `domain/` imports from `infrastructure`. |
| `test_orchestrator_layering.py` | AST guard — narrower check on `application/orchestrator.py` specifically. |
| `test_models.py`, `test_events.py`, `test_classes.py`, `test_locations.py`, `test_exceptions.py` | Pure-domain VO/enum coverage. |
| `test_owner.py` | `OwnerTracker` state-machine + auto-pin transitions (PR-2). |
| `test_ports.py`, `test_log_parser_protocol.py` | `runtime_checkable` Protocol structural-typing checks. |
| `test_bus.py`, `test_throttle.py`, `test_handlers.py` | Application-layer unit coverage with fakes. |
| `test_orchestrator_stop.py` | Sync close-stream signal end-to-end (sentinel queue value, idempotent close). |
| `test_parsing.py` | Regex-contract checks against synthesized log lines. |
| `test_detection.py` | `PsutilGameDetector` with mocked `psutil.process_iter`; covers `process_name: list[str]` (PR-1). |
| `test_log_stream.py` | Watchdog → asyncio-queue bridge with a fake observer. |
| `test_presence_connect.py`, `test_presence_publish.py` | Split-retry policy coverage (5×wait_exponential(2,32) connect, 3×wait_exponential(1,8) publish). |
| `test_afk.py` | `small_image_override` set/clear/restore (PR-3). |
| `test_settings.py` | Env-var coercion (`Annotated[list[str], NoDecode]` + `field_validator(mode="before")` for legacy single-string `process_name`). |
| `test_catalog.py` | `load_bundled_catalog()` + `LocationCatalog.resolve()` with map-prefix stripping. |
| `test_logging.py` | structlog config (Console renderer for dev, JSON for prod). |
| `test_tray.py`, `test_autostart.py` | pystray + pylnk3 with the third-party imports patched (PR-4). |
| `test_extras_missing.py` | Optional-extras gate — `pip install poe2-rpc` (no `[tray]`) must `typer.Exit(code=1)` instead of `ImportError`. |
| `test_smoke.py` | One-liner smoke import of `poe2_rpc` to detect packaging breakage. |

## For AI Agents

### Working In This Directory
- AST guards (`test_no_mutable_state.py`, `test_layering.py`) are non-negotiable architectural enforcement. Don't add `# noqa` or per-file ignores — fix the source.
- Mock at the **third-party seam**, not the Protocol seam, so we still exercise our adapter glue (e.g. patch `psutil.process_iter`, not `PsutilGameDetector`).
- New domain VO → new test file matching the module name. New port → add a `runtime_checkable` instance check.
- The split-retry tests for `presence` use `tenacity.retry.wait_none()` overrides via `monkeypatch` to keep tests fast.

### Testing Requirements
- Each test file maps 1:1 to a module under `src/poe2_rpc/`. Adding a new module without a test is a review-blocker.
- Run a focused subset locally with `pytest tests/unit/test_<module>.py -ra`.

### Common Patterns
- `pytest.fixture` over class-based test setup.
- `monkeypatch.setattr` for third-party patches; keep `unittest.mock` for cases that genuinely need spec-checking.
- `freezegun` (already a dev dep) is used in throttle tests to deterministically advance the clock.

## Dependencies

### Internal
- `poe2_rpc.*` modules under test.

### External
- `pytest`, `pytest-asyncio`, `freezegun`.

<!-- MANUAL: Manually added notes below this line are preserved on regeneration -->
