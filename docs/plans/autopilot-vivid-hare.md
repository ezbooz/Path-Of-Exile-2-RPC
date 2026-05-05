# Architecture Plan: Path-Of-Exile-2-RPC → Layered Modulith

## Context

`main.py` is currently a 330-line single-file script that mixes enums, regex parsing, file I/O, process discovery, Discord IPC, and a tail loop with a module-level mutable `rpc` global. The README's open roadmap (background service, official-client support, per-player detection, AFK) cannot be added cleanly without architectural seams: each item touches multiple of the currently-fused concerns.

Constraints making this non-trivial:
- CI is path-filtered to `paths: ['main.py']` and PyInstaller is invoked as `--onefile main.py`.
- No tests, type checker, or linter exist today; the regex parsers (the part most likely to silently break on a game patch) have no safety net.
- Single distributable artifact: one Windows `.exe` from GitHub Releases.

The chosen direction is the **smallest possible split** that (a) makes parsing testable, (b) removes the global, and (c) makes each roadmap item a localized change instead of a rewrite. No DDD, no hexagonal layering, no event bus — this is a 330-LOC log tailer and stays that way.

## Target layout

```
Path-Of-Exile-2-RPC/
  main.py                         # thin: build Config, RpcClient, Monitor; run
  locations.json                  # unchanged
  requirements.txt                # unchanged (psutil, pypresence)
  requirements-dev.txt            # NEW: pytest
  pyrightconfig.json              # NEW: IDE-only type checking, no CI gate
  poerpc/
    __init__.py
    config.py                     # frozen dataclass Config + env-var overrides
    classes.py                    # CharacterClass, ClassAscendency
    parsing.py                    # regex parsers + determine_location (pure)
    locations.py                  # JSON loader, local cache, GitHub fallback
    game.py                       # process discovery → Client.txt path
    rpc_client.py                 # RpcClient class, retry, owns Presence
    monitor.py                    # Monitor class: tail loop + state machine
  tests/
    __init__.py
    fixtures/sample_client_lines.txt
    test_parsing.py
  .github/workflows/build.yml     # path filter widened to include poerpc/**
```

## Symbol migration map

| Current location in `main.py` | New home |
|---|---|
| `CharacterClass`, `ClassAscendency` | `poerpc/classes.py` |
| `regex_level`, `regex_instance`, `find_last_level_up`, `find_instance`, `get_last_level_up`, `determine_location`, `random_status` | `poerpc/parsing.py` |
| `load_locations` | `poerpc/locations.py` |
| `find_game_log` | `poerpc/game.py` (reads `config.process_names`) |
| `rpc_connect`, `update_rpc`, global `rpc` | `poerpc/rpc_client.py` as `RpcClient` |
| `monitor_log` | `poerpc/monitor.py` as `Monitor` |
| Hardcoded constants: `"PathOfExileSteam.exe"`, `"1315800372207419504"`, locations URL, `3`, `5`, `2**retries`, `5` retries | `poerpc/config.py` |
| `if __name__ == "__main__":` | `main.py` (~15 lines: build Config → RpcClient → Monitor; call `Monitor.run()`) |

## Key design decisions

**1. `RpcClient` class replaces the global `rpc`.**
Owns the `pypresence.Presence` instance. Public surface: `connect()`, `update(level_info, instance_info, status)`, `clear()`. `Monitor` receives it via constructor. The retry loop and exponential backoff move inside `connect()`. Result: parsing has zero hidden dependencies; the network layer is mockable.

**2. `Config` is a frozen dataclass with env-var overrides at construction.**

```python
@dataclass(frozen=True)
class Config:
    process_names: tuple[str, ...]      # ("PathOfExileSteam.exe",) initially
    discord_app_id: str                 # env: POERPC_DISCORD_APP_ID
    locations_url: str
    poll_interval_s: float = 5.0
    process_scan_interval_s: float = 3.0
    rpc_max_retries: int = 5
    afk_timeout_s: int = 180
```

This unlocks:
- **Official PoE2 client support** — extend the `process_names` tuple; `game.py` already iterates.
- **Custom Discord app** — `POERPC_DISCORD_APP_ID` env var read once at startup.

No YAML/TOML config; one .exe + env vars is sufficient for a hobby tool.

**3. Background-service roadmap item stays out of code.**
Recommend Windows Task Scheduler (trigger on process-start of `PathOfExile*.exe`) or NSSM in the README. In-process service wrappers (`pywin32`) bloat the .exe and add platform-specific failure modes. The current .exe + Task Scheduler is a documentation change, not a code change.

**4. Per-player detection lives inside `Monitor`.**
Capture the first level-up line observed after the monitor starts; record `owner_username`; ignore subsequent level-ups for other usernames. Single field, no new module.

**5. AFK detection lives inside `Monitor`.**
Track `last_event_at` timestamp. If `now - last_event_at > config.afk_timeout_s`, call `RpcClient.update(..., status="AFK")`. Single branch in the existing loop.

## CI changes

In `.github/workflows/build.yml`, widen the path filter:

```yaml
paths:
  - 'main.py'
  - 'poerpc/**'
  - 'requirements.txt'
  - 'locations.json'
```

PyInstaller call stays as `pyinstaller --onefile --name PathOfExile2DiscordRPC main.py`. PyInstaller follows imports into `poerpc/` automatically; no spec file or `--add-data` needed. `locations.json` continues to be read from the working directory at runtime.

## Test strategy

`requirements-dev.txt` adds only `pytest`. `tests/test_parsing.py` covers:
- `regex_level`: ordinary class, ascendancy, special characters in usernames.
- `regex_instance`: hideouts, map areas, areas with quotes in the name.
- `determine_location`: `Map*` prefix stripping, exact-key match, fallback when key absent.

No CI test job in v1. Adding a Windows-runner pytest job is a follow-up once a stable fixture set exists — adding it now invites flake before there's anything to check.

Type checking: `pyrightconfig.json` with `include: ["poerpc", "main.py"]`, `strict: false`. IDE-only, no CI gate. Catches obvious `Optional` mistakes without blocking releases.

## Migration sequence (each step ships independently)

1. **Extract `poerpc/parsing.py` + `poerpc/classes.py`; add `tests/test_parsing.py`.** Update CI `paths:` filter. Behavior unchanged, regexes now pinned by tests.
2. **Extract `poerpc/config.py` + `poerpc/locations.py`.** Move URL and process name into `Config`. Add env-var read for Discord app id.
3. **Extract `poerpc/game.py`.** It iterates `config.process_names`. Official-client support now a one-string follow-up PR.
4. **Introduce `poerpc/rpc_client.py` as `RpcClient`.** Kill the global. `main.py` constructs it.
5. **Extract `poerpc/monitor.py` as `Monitor`.** `main.py` becomes ~15 lines.
6. **Add per-player owner detection and AFK tracking inside `Monitor`.** Uses `config.afk_timeout_s` and the level-up parser already extracted in step 1.
7. **Document Task Scheduler / NSSM recipe in `README.md`** for the background-service roadmap item. No code change.

## Critical files to modify

- `/Users/denn/PhpstormProjects/Path-Of-Exile-2-RPC/main.py` — reduce to wiring + entrypoint.
- `/Users/denn/PhpstormProjects/Path-Of-Exile-2-RPC/.github/workflows/build.yml` — widen `paths:` filter on lines 7–8.
- `/Users/denn/PhpstormProjects/Path-Of-Exile-2-RPC/requirements.txt` — unchanged.
- `/Users/denn/PhpstormProjects/Path-Of-Exile-2-RPC/CLAUDE.md` and `AGENTS.md` — update "Keep it one file" guidance after step 1 ships.
- New: `poerpc/` package, `tests/`, `requirements-dev.txt`, `pyrightconfig.json`.

## Verification

After each migration step:

1. `pip install -r requirements.txt` — clean dependency install still succeeds.
2. `python main.py` — launches and reaches `Waiting for the game start..` (or connects RPC if PoE2 is running).
3. `pytest` (from step 1 onward) — parser tests pass.
4. With Discord and PoE2 running: confirm presence updates on level-up and area-change in Discord client.
5. Trigger CI build by editing a file matching the path filter; confirm `dist/PathOfExile2DiscordRPC.exe` is produced and a release tag is pushed.
6. Smoke-run the produced `.exe` on a Windows machine: presence updates appear identical to the pre-refactor build.

End-state acceptance: the Roadmap items (official client, AFK, per-player) each become localized PRs touching one or two files in `poerpc/`, not a re-architecture.
