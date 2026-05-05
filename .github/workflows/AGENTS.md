<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-04 | Updated: 2026-05-04 -->

# workflows

## Purpose
GitHub Actions workflow definitions. Currently a single pipeline that builds the Windows executable and publishes a tagged GitHub Release.

## Key Files
| File | Description |
|------|-------------|
| `build.yml` | Build-and-release pipeline. Triggers on push to `main` when `main.py` changes (or `workflow_dispatch`). Two jobs: `build` (PyInstaller `--onefile`, uploads artifact, creates timestamp tag `vYYYYMMDD-HHMMSS` and pushes it) and `release` (downloads artifact, creates GitHub Release, uploads `.exe` asset). |

## For AI Agents

### Working In This Directory
- The workflow runs on `windows-latest` because PyInstaller produces a native binary; do not switch to `ubuntu-latest`.
- The `paths:` filter is `main.py` — if the project ever splits into multiple source files, broaden the filter (e.g. `'**/*.py'`) or the build will silently stop running on relevant changes.
- The PyInstaller command (`pyinstaller --onefile --name PathOfExile2DiscordRPC main.py`) hardcodes the entrypoint and output name. Renaming `main.py` requires updating this line.
- The release uses the deprecated `actions/create-release@v1` and `actions/upload-release-asset@v1`. If migrating, prefer `softprops/action-gh-release` and verify the tag-creation step still pushes the tag before the release job runs (the `release` job depends on `needs.build.outputs.tag_name`).
- Tags are auto-generated from the build timestamp via PowerShell (`Get-Date -Format yyyyMMdd-HHmmss`). Don't switch to semver without also updating release tooling.
- `permissions: contents: write` is required for both pushing the tag and creating the release.

### Testing Requirements
- Trigger via `workflow_dispatch` from the Actions tab to dry-run without a `main.py` commit.
- Verify the artifact `PathOfExile2DiscordRPC.exe` appears under both the workflow run's artifacts and the new GitHub Release.

## Dependencies

### External
- `actions/checkout@v4`, `actions/setup-python@v4`, `actions/upload-artifact@v4`, `actions/download-artifact@v4`
- `actions/create-release@v1`, `actions/upload-release-asset@v1` (deprecated; see note above)
- `pyinstaller` (installed at job runtime, not pinned)

<!-- MANUAL: -->
