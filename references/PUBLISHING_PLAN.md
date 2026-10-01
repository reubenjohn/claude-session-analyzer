# Publishing and distribution plan

Status as of 2026-10-01. Keep this current: check items off, and record new
decisions here instead of in chat.

## Where things live

| What | Where |
|---|---|
| v2 rebuild (active) | this repo, branch `v2-build` (ready to merge into `main`); `main` is the fresh single-commit snapshot from the linux-home dotfiles branch `session-analyzer-v2` |
| v1 (frozen) | this repo, `v1-legacy`, once built: an orphan branch holding a single-commit snapshot of `user_home/.claude/skills/session-analyzer/`. Not present in this clone or on origin as of 2026-10-01 |
| Origin copies | linux-home dotfiles (`reubenjohn/linux-home`), `user_home/.claude/skills/session-analyzer/` (v1, still the installed skill) |

History was deliberately **not** carried over (owner decision). This avoids
publishing session data that old commits might contain.

## Remaining steps

1. [ ] **Build and push `v1-legacy`.** Owner task. As of 2026-10-01 no
   `v1-legacy` branch exists in this clone, in the dotfiles clone, or on
   origin (`git ls-remote --heads origin` lists `main` only), so the
   snapshot described above has to be (re)built: an orphan branch holding
   one commit of `user_home/.claude/skills/session-analyzer/` with a legacy
   notice in its README. Known breakage outside the dotfiles: two tests in
   `tests/test_v2.py` expect the dotfiles' `settings.json` and the
   `deny-ad-hoc-bash.js` hook next to the directory. Until it lands, the
   clean-room allowlist in `CLAUDE.md` is read from the installed skill.
2. [x] **Rewrite `CLAUDE.md` for standalone use.** Done 2026-09-30: no
   dotfiles-branch or worktree references remain; the clean-room allowlist
   points at `git show v1-legacy:<path>` once step 1 lands, and at the
   installed skill under `~/.claude/skills/session-analyzer/` until then.
3. [ ] **Merge `v2-build` into `main`.** Ready: sixteen judge passes
   accepted, every mention applied, 221 tests pass. Owner merges (fast
   forward or merge commit, their call) and pushes.
4. [ ] **Remove v1 from the dotfiles.** Needs owner approval. The dotfiles'
   v2 copy is already gone from the `session-analyzer-v2` checkout; v1 is
   still the installed `session-analyzer` skill, and step 5 replaces it, so
   remove it when the plugin is installed (both are listed as
   `session-analyzer` otherwise, the plugin's one namespaced as
   `claude-session-analyzer:session-analyzer`).
5. [x] **Distribute as a plugin.** Done 2026-09-30, re-verified 2026-10-01
   from a working tree (`claude plugin validate .`, marketplace add,
   install, `python3 -m sa context` from the plugin root, uninstall,
   marketplace remove). The repo root is the plugin root:
   - `.claude-plugin/plugin.json` (name `claude-session-analyzer`, version
     `2.0.0`) and `.claude-plugin/marketplace.json` (marketplace name
     `reubenjohn`, one entry with `source: "./"`).
   - `skills/session-analyzer/SKILL.md` drives the CLI with
     `cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m sa …`; the installed copy is
     the whole repo, so `sa/` sits at the plugin root.
   - Verified locally: `claude plugin marketplace add <repo path>` then
     `claude plugin install claude-session-analyzer@reubenjohn` installs
     under `~/.claude/plugins/cache/reubenjohn/claude-session-analyzer/2.0.0/`
     and a fresh session lists the skill as
     `claude-session-analyzer:session-analyzer`.
   - Bump `version` in both manifests on every release; `claude plugin
     update claude-session-analyzer@reubenjohn` is how a user picks it up
     (restart required).
   - The install copies the whole plugin root, untracked files included
     (seen 2026-10-01: `.pytest_cache/`, `sa/__pycache__/`,
     `tests/__pycache__/`, besides the tracked `.githooks/`, `CLAUDE.md`,
     `references/`, `tests/`). Claude Code 2.1.286 has no
     `.claudepluginignore`-style mechanism (none in the CLI binary, none in
     `claude plugin --help`), so there is nothing to declare: install from
     the GitHub source rather than a working tree, and keep the plugin root
     free of anything a user must not receive.
   - `claude plugin marketplace remove` leaves an empty
     `"extraKnownMarketplaces": {}` in `~/.claude/settings.json`; delete the
     line by hand after a local round trip.

## Distribution decision (step 5)

Both mainstream installers read the same `SKILL.md` format, so one repo can
serve both:

- **Claude Code plugin marketplace** (first-party, DONE). Users run
  `claude plugin marketplace add reubenjohn/claude-session-analyzer`,
  `claude plugin install claude-session-analyzer@reubenjohn`, and later
  `claude plugin update claude-session-analyzer@reubenjohn`. A plugin can
  bundle skills, hooks and agents, and gets versioned updates.
- **`npx skills add reubenjohn/claude-session-analyzer`** (vercel-labs/skills).
  This cross-agent installer covers Claude Code, Codex, Cursor and others.

**Chosen for the dotfiles: plugin.** The dotfiles declare it in
`user_home/.claude/settings.json` under `extraKnownMarketplaces` and
`enabledPlugins`. Development happens in a normal clone under `~/workspace/`.

Rejected options:
- **git submodule:** every change needs a commit inside the submodule plus a
  pointer bump in the dotfiles, which is too much churn while v2 changes
  quickly.
- **Clone-and-symlink setup script:** more machinery than a settings entry.

## Standing rules

- **Before any push to a public branch:** scan for secrets, real paths
  (`/home/<name>`, `-home-<name>-…` project directories) and real session
  UUIDs. Fixtures must use the synthetic markers listed in v1's
  `public_artifacts.json`.
- **Installing someone else's skill or plugin:** run the owner's
  `skill-install-review` checklist first.
