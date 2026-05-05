<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-04 | Updated: 2026-05-04 -->

# ISSUE_TEMPLATE

## Purpose
GitHub issue form templates surfaced when a user opens "New Issue" on the repository.

## Key Files
| File | Description |
|------|-------------|
| `config.yml` | Sets `blank_issues_enabled: true` (users can still open a free-form issue alongside the templates). |
| `help-wanted.yml` | Form template titled `[HELP] ` with a game-version dropdown (Steam / Official / Epic), a "What happened?" textarea, and an optional log file textarea. Auto-assigns to `ezbooz` and applies the `help wanted` label. |

## For AI Agents

### Working In This Directory
- Files use GitHub's [Issue Forms YAML schema](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms). Validate locally before pushing — broken templates silently fall back to the blank issue UI.
- The default game-version dropdown index is `0` (Steam). If you reorder the options, update the `default:` field accordingly.
- Don't put log file uploads inside the form — GitHub Issue Forms can't accept attachments. The current template asks the user to attach manually after creation, which is the correct workaround.
- Auto-assignment to `ezbooz` is intentional (project owner). Don't reassign without coordinating.

<!-- MANUAL: -->
