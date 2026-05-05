<!-- Generated: 2026-05-04 | Updated: 2026-05-05 -->

# Path-Of-Exile-2-RPC

## Purpose
A Discord Rich Presence integration for Path of Exile 2. Detects the running game process (Steam **and** official client), tails its `Client.txt` log, parses level-up + zone-generation + AFK events, and pushes a live presence update (character / class / ascendancy / zone / AFK status) to Discord via `pypresence`.

The runtime is a hexagonal Python package at `src/poe2_rpc/` with `domain/`, `application/`, `infrastructure/`, and `cli.py` (composition root). The Typer app in `cli.py` is the entrypoint, exposed as the `poe2-rpc` console script and `python -m poe2_rpc`. The legacy single-file `main.py` at the repo root is the upstream-compatible form: it carries the same features re-encoded as module globals + inline branches and is the surface used by the `ezbooz/Path-Of-Exile-2-RPC` upstream PRs.

End users grab a prebuilt Windows `.exe` from GitHub Releases (built by `.github/workflows/build.yml` via PyInstaller `--onefile` against `PathOfExile2DiscordRPC.spec`).

## Key Files
| File | Description |
|------|-------------|
| `main.py` | Upstream-form single-file runtime (re-encoded hexagonal features as module globals + inline branches). Backport target for `ezbooz/Path-Of-Exile-2-RPC` PRs #6–#9. |
| `pyproject.toml` | Package metadata, dev/tray extras, Typer console script, ruff/mypy/import-linter config. |
| `PathOfExile2DiscordRPC.spec` | PyInstaller `--onefile` spec; bundles `src/poe2_rpc/locations.json`. |
| `locations.json` | Human-edit source-of-truth for area-code → display-name mapping; mirrored into `src/poe2_rpc/locations.json` for packaging. |
| `requirements.txt` | Upstream-form runtime deps; mirrors the runtime subset of `pyproject.toml`. |
| `README.md` / `README.ru.md` / `README.ua.md` | End-user instructions in EN / RU / UA. |
| `CLAUDE.md` | Project instructions for Claude Code. |
| `LICENSE` | MIT. |
| `.gitignore` | Ignores caches, build artifacts, `.omc/state/`, `.idea/`. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `src/poe2_rpc/` | Hexagonal package (see `src/poe2_rpc/AGENTS.md`). |
| `tests/` | Unit + integration test suites (see `tests/AGENTS.md`). |
| `.github/` | CI workflows + issue templates (see `.github/AGENTS.md`). |
| `.omc/` | OMC planning artifacts: `.omc/specs/` (deep-interview specs) and `.omc/plans/` (ralplan consensus plans) are tracked; `.omc/state/` is gitignored. |
| `.beads/` | Beads issue-tracker state (`issues.jsonl` is the file-based backup). |

## For AI Agents

### Working In This Directory
- **Hexagonal layering is non-negotiable.** `lint-imports` enforces `domain ← application ← infrastructure ← cli`. Only `cli.py` may import from `infrastructure`. AST guards in `tests/unit/test_layering.py` and `test_orchestrator_layering.py` back this up.
- **Frozen pydantic v2 VOs in `domain/`** — no `dataclass`, no mutable state. `tests/unit/test_no_mutable_state.py` AST guard fails CI on violations.
- **`mypy --strict` is mandatory.** 4-space indent, type hints on every signature.
- **`structlog` not `logging`.** Use `bind_contextvars(username=, character_class=, area=)` so events carry context through the call graph.
- **`pathlib.Path` + explicit `encoding="utf-8"`** for file I/O. Bundled assets via `importlib.resources.files("poe2_rpc")` — never cwd-relative.
- **Tenacity for retries**, with split policies for connect vs publish (see `src/poe2_rpc/infrastructure/presence.py`).
- **The dual-form (hexagonal + main.py) is intentional.** When changing both, treat the cross-form contract as the state-transition table, not the class hierarchy. See memory `feedback_backport_divergence_pattern.md`.
- **Optional extras pattern:** hexagonal modules import third-party deps at module top behind `try import / except ImportError as e: raise ... from e`. Upstream-form lazy-imports inside helpers. See memory `feedback_optional_deps_backport_idiom.md`.

### Testing Requirements
The full gate (mirrors CI):

```bash
pytest tests -ra
mypy --strict src/poe2_rpc
lint-imports
ruff check src tests
ruff format --check src tests
```

143 tests pass on `feature/background-launcher`; new code should not lower this baseline.

### Common Patterns
- Composition root in `cli.py::build_orchestrator(settings)` wires Protocols → adapters.
- All Typer command callbacks return `None`; errors raise `typer.Exit(code=...)`.
- Optional-deps imports are deferred to inside the function body so headless installs never hit the import.
- Domain events are nouns-in-past-tense (`CharacterLevelChanged`, `AreaEntered`, `AFKStatusChanged`).

## Dependencies

### Internal
- `domain/` — pure VOs, events, Protocols (see `src/poe2_rpc/domain/AGENTS.md`).
- `application/` — orchestration, bus, throttle, handlers (see `src/poe2_rpc/application/AGENTS.md`).
- `infrastructure/` — psutil, watchdog, pypresence, pydantic-settings, structlog, pystray, pylnk3 adapters (see `src/poe2_rpc/infrastructure/AGENTS.md`).

### External
- `typer` — CLI framework.
- `psutil` — process discovery.
- `watchdog` — `ReadDirectoryChangesW` log tailing.
- `pypresence` — Discord IPC.
- `pydantic` v2 + `pydantic-settings` — VOs, env-var coercion.
- `structlog` — structured logging.
- `tenacity` — split-policy retries.
- `pystray` + `Pillow` + `pylnk3` — optional `[tray]` extra (Windows tray + Startup shortcut).

### Runtime
- Discord desktop client must be running and authorized for app ID `1315800372207419504`.
- Path of Exile 2 (Steam **or** official client) must be installed and running.

## Build & Test

```bash
pip install -e ".[dev]"
poe2-rpc run                            # continuous monitor loop
poe2-rpc once                           # single log-stream pass
poe2-rpc validate-config --no-discord   # smoke check (no Discord IPC)

# Optional tray service (Windows)
pip install "poe2-rpc[tray]"
poe2-rpc tray
poe2-rpc install-autostart
poe2-rpc uninstall-autostart
```

Optional config: `%APPDATA%\poe2-rpc\config.toml` on Windows, `~/.config/poe2-rpc/config.toml` on macOS/Linux for cross-platform dev. Defaults work without one — see `src/poe2_rpc/infrastructure/settings.py::AppSettings`.

## CI / Release flow

Push to `main` touching `src/**`, `pyproject.toml`, `locations.json`, `PathOfExile2DiscordRPC.spec`, or the workflow → `.github/workflows/build.yml` runs lint+test on `ubuntu-latest`, then build on `windows-latest`. The build job runs `pyinstaller PathOfExile2DiscordRPC.spec`, then deep-smokes the `.exe` with `validate-config --no-discord`, then a cold-start benchmark (continue-on-error: budget breach files a follow-up bd issue, doesn't block release). A timestamp tag (`vYYYYMMDD-HHMMSS`) is created and pushed; the release job uploads `PathOfExile2DiscordRPC.exe` as a GitHub Release asset.

## Upstream PR campaign

Four small, sequential PRs against `ezbooz/Path-Of-Exile-2-RPC` carry the same feature work to upstream's single-file form:

- **#6** Official PoE2 client support (`process_name: list[str]`).
- **#7** Owner detection via auto-pin (`OwnerTracker` re-encoded as module globals).
- **#8** AFK status with `small_image_override`.
- **#9** Background launcher (pystray tray + Windows Startup shortcut).

All four are open as drafts pending end-of-campaign Windows live-smoke. See memory `project_upstream_pr_campaign.md`.

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**
```bash
# Force overwrite without prompting
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file

# For recursive operations
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**
- `scp` - use `-o BatchMode=yes` for non-interactive
- `ssh` - use `-o BatchMode=yes` to fail instead of prompting
- `apt-get` - use `-y` flag
- `brew` - use `HOMEBREW_NO_AUTO_UPDATE=1` env var

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

<!-- MANUAL: Manually added notes below this line are preserved on regeneration -->
