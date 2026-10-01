# Publishing and distribution plan

Status as of 2026-09-30. Keep this current: check items off, and record new
decisions here instead of in chat.

## Where things live

| What | Where |
|---|---|
| v2 rebuild (active) | this repo, `main`: a fresh single-commit snapshot from the linux-home dotfiles branch `session-analyzer-v2` |
| v1 (frozen) | this repo, `v1-legacy`: an orphan branch holding a single-commit snapshot of `user_home/.claude/skills/session-analyzer/` |
| Origin copies | linux-home dotfiles (`reubenjohn/linux-home`), `user_home/.claude/skills/session-analyzer{,-v2}/` |

History was deliberately **not** carried over (owner decision). This avoids
publishing session data that old commits might contain.

## Remaining steps

1. [ ] **Push `v1-legacy`.** The snapshot is built and its README carries a
   legacy notice. The automatic permission check blocked the agent's push, so
   the owner pushes it. Known breakage outside the dotfiles: two tests in
   `tests/test_v2.py` expect the dotfiles' `settings.json` and the
   `deny-ad-hoc-bash.js` hook next to the directory. 595 tests pass.
2. [ ] **Rewrite `CLAUDE.md` for standalone use.** It still refers to the
   dotfiles branch, "this worktree", and v1's dotfiles path for the clean-room
   boundary. Point the clean-room allowlist at the `v1-legacy` branch instead
   (for example `git show v1-legacy:references/PURPOSE.md`).
3. [ ] **Remove both copies from the dotfiles.** This needs owner approval. v2
   has no `SKILL.md`, so nothing loads it as a skill and it can simply be
   deleted. v1 is still the installed `session-analyzer` skill; remove it
   only once step 4 can replace it.
4. [ ] **Distribute as a skill once v2 has a `SKILL.md`.** See below.

## Distribution decision (step 4)

Both mainstream installers read the same `SKILL.md` format, so one repo can
serve both:

- **Claude Code plugin marketplace** (first-party). Add
  `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`. Users
  run `/plugin marketplace add reubenjohn/claude-session-analyzer`. A plugin
  can bundle skills, hooks and agents, and gets versioned updates.
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
