<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-05 | Updated: 2026-05-05 -->

# integration

## Purpose
Cross-layer tests that wire real adapters together: real `RegexLogParser` against captured `Client.txt` samples, real `LocationCatalog` against the bundled `locations.json`, and the Typer CLI driven via `typer.testing.CliRunner`. The cold-start benchmark sets the runtime budget for `validate-config --no-discord` (used by the CI deep-smoke step).

## Key Files
| File | Description |
|------|-------------|
| `test_cli.py` | Typer surface — `--help`, `--version`, `validate-config --no-discord`, optional-extras gating. Source-of-truth for the CLI contract. |
| `test_main_module.py` | `python -m poe2_rpc` dispatches to the same Typer app as the `poe2-rpc` console script. |
| `test_orchestrator.py` | End-to-end pipeline: real `RegexLogParser` + `InMemoryEventBus` + `FakePresencePublisher`; verifies that level-up + area-entered events publish presence in the expected order with throttle applied. |
| `test_bundled_catalog.py` | Bundled `locations.json` loads via `importlib.resources` — guards against PyInstaller `--onefile` packaging regressions. |
| `test_regex_real_sample.py` | Runs `regex_level` / `regex_instance` against a captured `Client.txt` slice; G-1 enforces this once the fixture is available. |
| `test_cold_start.py` | Cold-start benchmark for `validate-config --no-discord`; CI's deep-smoke step compares against this budget. |

## For AI Agents

### Working In This Directory
- Adding a new Typer command in `cli.py`? Add an integration test here. The `--help` output and the optional-extras gate are part of the public contract.
- The cold-start benchmark is `continue-on-error` in CI — a budget breach files a follow-up bd issue rather than blocking the release. Don't suppress the comparison; the trend matters.
- Captured `Client.txt` samples should be sanitized (no real Steam IDs, no real character names) and committed under `tests/fixtures/` if added.

### Testing Requirements
- These tests are slower than unit tests; run them last in your local loop.
- The CLI tests use `typer.testing.CliRunner(mix_stderr=False)` so stderr/stdout assertions stay sharp.

### Common Patterns
- `CliRunner` invocation pattern: `runner.invoke(app, ["validate-config", "--no-discord"])` then assert on `result.exit_code` and `result.stdout`.
- Fakes for I/O ports come from `tests/conftest.py`, not redefined per file.
- `tmp_path` for any test writing to disk; never the repo.

## Dependencies

### Internal
- `poe2_rpc.cli` (Typer app), `poe2_rpc.application.orchestrator`, `poe2_rpc.infrastructure.parsing`, `poe2_rpc.infrastructure.catalog`.

### External
- `pytest`, `typer.testing.CliRunner`.

<!-- MANUAL: Manually added notes below this line are preserved on regeneration -->
