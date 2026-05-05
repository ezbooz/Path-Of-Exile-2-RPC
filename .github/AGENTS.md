<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-04 | Updated: 2026-05-04 -->

# .github

## Purpose
GitHub-specific configuration: the CI/CD pipeline that builds and releases the Windows `.exe`, and the issue templates surfaced in the repository's "New Issue" UI.

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `workflows/` | GitHub Actions workflows (see `workflows/AGENTS.md`) |
| `ISSUE_TEMPLATE/` | Issue form templates (see `ISSUE_TEMPLATE/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Changes here only take effect when pushed to `main` (or merged via PR).
- The build workflow is path-filtered to `main.py` — adding new source files means updating both `paths:` in `build.yml` and the PyInstaller invocation.

<!-- MANUAL: -->
