# session-analyzer v2 — standing context

> **Moved out of the dotfiles. Read `references/PUBLISHING_PLAN.md` first.**
> It has the open extraction steps and the distribution decision. Until step 2
> there is done, any mention below of the dotfiles branch, the worktree, or v1's
> dotfiles path is stale: v1 now lives on this repo's `v1-legacy` branch.

Clean-room rebuild of session-analyzer, built on the disposable branch
`session-analyzer-v2`. Never checkout or commit to main from this worktree.

**Scope of build v1: TWO questions** — where is my context going
(`context_delta`) and what did it cost (`spend`). TIME/scheduling questions are
real and deliberately DEFERRED: design so they can be added, do not add them.

**Standing premise, inherited from v1 and still in force:** this tool has NO
USERS and NO DEPLOYMENTS. Breaking changes are free, legacy is deleted not
accommodated, published numbers may move when the old number was wrong.

## The clean-room boundary — binding on every session and subagent

v1 lives at `user_home/.claude/skills/session-analyzer/`. The ONLY files you
may open there:

- `references/PURPOSE.md` — why anyone cares; read first
- `references/ENGINE_CONTRACT.md` — what is true, and what kind of claim each
  invariant is (ARITHMETIC / MEASURED / RULING / OPEN)
- `references/glossary.md` — the nouns; never invent a synonym for a term that
  exists
- `CLAUDE.md` (v1's own) — the standing premise above
- `scripts/lib/lib_drill.py`, `scripts/sa_schema.py`,
  `tests/generate_fixtures.py` — already ported verbatim into this tree
- `scripts/lib/lib_parse.py` — the usage helpers only (`usage_context`,
  `max_merge_usage`, `usage_spend`, `context_delta`, `usage_cache_tier`)

Everything else under the v1 directory is OFF LIMITS — code, tests, docs, git
history. Several of its most authoritative-sounding documents instruct a reader
to build what a test forbids (ENGINE_CONTRACT §10). Wanting to see how v1
solved something is the exact impulse this boundary exists to catch. If you
need a file not on this list, STOP AND ASK the owner.

## Ported verbatim — the starting state, not a frozen ceiling

`scripts/lib/lib_drill.py` and `scripts/sa_schema.py` are the engine, taken as
files per ENGINE_CONTRACT §9. Their docstrings ARE the specification, and each
docstring in `scripts/lib/lib_usage.py` carries a measured correction. The rule
here is about the CHANNEL of change, not changeability: the engine's
[OPEN]-tagged choices (score combinator, cover definition, residual
unification, the purity boundary, …) are legitimate challenge targets — raise
them in a design brief's decision log with argument or new measurement, and
they land only after an owner ruling. What is forbidden is the silent in-place
rewrite: this domain's recorded failure mode is the confident, plausible
"improvement" that deletes a measured correction, and the ported files are the
ones that survived mutation testing.

## Non-negotiables (from the owner's build brief)

- Forest-level uuid-keyed dedup at the aggregation boundary from day one —
  never per-file, never content-keyed. A window is not a file (bg, /branch,
  --fork-session, sibling forks); per-file reading inflates totals by 94%.
- The tree INVERTS under these metrics: the injected subtree (~95% of observed
  chars) carries ZERO mass. Design output for that before drawing any.
- No estimated attribution in build v1. ~77% of intervals attribute exactly by
  subtracting the feed-forward term; the other ~23% gets ONE residual bucket
  named *ambiguous*, never a silent spread.
- Every figure names the population it was measured over; estimates are
  labelled estimates.
- Tests, from the first one: derive assertions from the schema (never
  enumerate metric names as literals) and put a vacuity guard beside every
  negative assertion.

## Repo gates

The global pre-commit hook warns on .py > 15,000 chars and .md > 20,000
(verbatim ports are the accepted exception), and the privacy gate FAILS CLOSED:
no literal /home/... or /Users/... paths, no real-looking UUIDs, no transcript
text in any tracked file. Compute the corpus root at runtime as
`Path.home()/".claude"/"projects"`.

## Where everything else lives — pointers, never copies

- `references/DESIGN_COMPETITION.md` — the design-phase charter: the two open
  problems, design gates, the owner's four required brief questions.
- `references/PHASE0_MEASUREMENT.md` — what the raw transcripts actually carry
  (attribution-join feasibility). If absent, Phase 0 has not landed yet.
- Design decisions await OWNER RULINGS before any build starts; the decision
  log travels with the design brief.
