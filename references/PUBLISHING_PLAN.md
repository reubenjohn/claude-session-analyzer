# Publishing and release

Status as of 2026-11-16. Keep this current; a stale step is a bug.

## Where things live

| What | Where |
|---|---|
| v2 (this repo) | `main` on `reubenjohn/claude-session-analyzer`, the only branch; the repo root is the plugin root |
| v1 (frozen) | the installed `~/.claude/skills/session-analyzer/` (from the linux-home dotfiles), until step 1 lands |

History before v2 was deliberately not carried over (owner decision): old
commits might hold session data.

## Remaining steps — owner only, ready to run

1. [ ] **Build and push `v1-legacy`.** Still absent on origin
   (2026-11-16: `git ls-remote --heads origin` lists `main` only): an orphan
   branch holding one commit of the dotfiles' v1 skill with a legacy notice.
   Until it lands, the clean-room allowlist (`AGENTS.md`) is read from the
   installed skill.
   ```
   git worktree add --orphan -b v1-legacy /tmp/v1-legacy && cd /tmp/v1-legacy
   cp -r ~/.claude/skills/session-analyzer/. . && echo "Frozen v1; v2 is main." > LEGACY.md
   git add -A && git commit -m "v1, frozen" && git push -u origin v1-legacy
   ```
   Before the push, read the tree for paths and session data (v1 may hold them).
2. [ ] **Remove v1 from the dotfiles**, once the plugin is installed there
   (else both list as `session-analyzer`): `git rm -r` the skill in the
   dotfiles repo, commit, then `claude plugin install
   claude-session-analyzer@reubenjohn`.
3. [ ] **Tag the release** (CI green on the commit):
   `git tag -a v2.0.0 -m "2.0.0" && git push origin v2.0.0 && gh release create v2.0.0 --notes-file CHANGELOG.md`
4. [ ] **PyPI — blocked on a name.** `claude-session-analyzer` is taken on
   PyPI by an unrelated project (2026-11-16: `pypi.org/pypi/<name>/json`
   200, 0.1.0, another repo). Free that day: `claude-code-session-analyzer`,
   `cc-session-analyzer`. Owner picks; set `name` in `pyproject.toml`, then
   `python3 -m pip install build twine && python3 -m build && python3 -m twine upload dist/*`
   and add `pip install <name>` to the README. Until then the README
   installs from GitHub.
5. [ ] **Announce.** Visibility is already PUBLIC (2026-11-16, `gh repo view`).

Done: `CLAUDE.md` standalone (2026-09-30), `v2-build` merged into `main`,
plugin distribution (2026-09-30, re-verified 2026-10-01); 2026-11-16:
`pyproject.toml` (pip install from a clone or GitHub, wheel = `sa/` only),
`CHANGELOG.md`, README badges and its commands tested (D-PIP, D-README-RUNS).

## Release

- Users: `claude plugin marketplace add reubenjohn/claude-session-analyzer`,
  `claude plugin install claude-session-analyzer@reubenjohn`, later
  `claude plugin update ...` (restart required). The skill lists as
  `claude-session-analyzer:session-analyzer`; `skills/session-analyzer/SKILL.md`
  runs `cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m sa ...`.
- Each release: CI green (`.github/workflows/ci.yml`); bump `__version__`
  in `sa/__init__.py` and, to match (`tests/test_docs.py`), `version` in
  `.claude-plugin/plugin.json` and `marketplace.json`; a `CHANGELOG.md`
  entry; `claude plugin validate .`.
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
