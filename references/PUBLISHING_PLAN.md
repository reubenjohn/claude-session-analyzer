# Publishing and release

Status as of 2026-11-16. Keep this current; a stale step is a bug.

## Where things live

| What | Where |
|---|---|
| v2 (this repo) | `main` on `reubenjohn/claude-session-analyzer`, the only branch; the repo root is the plugin root |
| v1 (frozen) | the installed `~/.claude/skills/session-analyzer/` (from the linux-home dotfiles), until step 1 lands |

History before v2 was deliberately not carried over (owner decision): old
commits might hold session data.

## Remaining steps

1. [ ] **Build and push `v1-legacy`.** Owner task. Still absent on origin
   (2026-11-16: `git ls-remote --heads origin` lists `main` only): an orphan
   branch holding one commit of the dotfiles' v1 skill with a legacy notice.
   Until it lands, the clean-room allowlist (`AGENTS.md`) is read from the
   installed skill.
2. [ ] **Remove v1 from the dotfiles.** Needs owner approval; do it once the
   plugin is installed there, or both list as `session-analyzer`.

Done: `CLAUDE.md` standalone (2026-09-30), `v2-build` merged into `main`,
plugin distribution (2026-09-30, re-verified 2026-10-01).

## Release

- Users: `claude plugin marketplace add reubenjohn/claude-session-analyzer`,
  `claude plugin install claude-session-analyzer@reubenjohn`, later
  `claude plugin update ...` (restart required). The skill lists as
  `claude-session-analyzer:session-analyzer`; `skills/session-analyzer/SKILL.md`
  runs `cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m sa ...`.
- Each release: CI green (`.github/workflows/ci.yml`), bump `version` in
  `.claude-plugin/plugin.json` and `marketplace.json`, `claude plugin
  validate .`.
- An install copies the whole plugin root, untracked files included, and
  Claude Code has no ignore file for it: install from GitHub, never from a
  working tree. A local `marketplace remove` leaves an empty
  `"extraKnownMarketplaces": {}` in `~/.claude/settings.json`; delete it.
- Rejected (2026-09-30): a dotfiles submodule (two commits per change) and
  a clone-and-symlink script (more machinery than a settings entry).
  `npx skills add` reads the same `SKILL.md`, untested.

## Standing rules

- Before any push to a public branch: the suite, whose privacy gate
  (`tests/test_privacy.py`) refuses real paths and real session UUIDs.
- Installing someone else's skill or plugin: the owner's
  `skill-install-review` checklist first.
