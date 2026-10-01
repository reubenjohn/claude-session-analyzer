# session-analyzer v2 — standing context

Answers TWO questions about Claude Code sessions: where is my context going
(`context_delta`) and what did it cost (`spend`), from the JSONL transcripts
under `Path.home()/".claude"/"projects"` (computed at runtime, never a
literal path). Standard library only, Python 3.8. TIME/scheduling questions
are deliberately deferred: design so they can be added, do not add them.
Standing premise: NO USERS, NO DEPLOYMENTS — breaking changes are free,
legacy is deleted not accommodated, published numbers move when the old
number was wrong. Branch: `v2-build`.

## Build charter (rulings of 2026-09-30, `references/DECISION_LOG.md`)

Owner directive: an elegant, simple implementation from which powerful
capabilities emerge. The ported ranking engine is RETIRED (D-ENGINE).

Package `sa/`, one module per stage (`corpus` read+dedup, `walk`
attribution, `heads`, `schema` the one METRICS table and vocabularies,
`query`, `render`, `cli`, `usage` the ported helpers); each docstring is
its spec. The parser IS the product: probes import it, never copy it.

One data model, `Fact`, specified in `schema.py`: `kind` is `call` or
`increment`; `metrics`; `dims`; `locator` `file:line:uuid` with `file`
relative to the corpus root; `evidence` (not a dimension: an ambiguous
increment's `candidates` locators, a fork's parent ids). Every metric
names its one carrier kind (`spend` -> call,
`context_delta` -> increment) and is read only from that kind, so
double-counting is impossible. Window dimensions `project`,
`session`, `agent` are on both kinds (a main window has no `agent`,
D-AGENT-DIM); `cause`, `tool`, `head`, `reason` on increments only. A head
is `<tool>:<summary>` (`Bash:pytest`, `Read:py`; R5 as amended), never a
path. Unknown names and undeclared `cause`/`reason` values fail closed. A
window IS a file (R2): `window_head` is the first usage-carrying call's
occupancy — inherited for a fork, boot context for a fresh session — its
own row, never spread, never the headline.

CLI surface: `python3 -m sa context --help`; README.md and SKILL.md mirror
live output. The headline names
the top splittable row of the first table shown, its mass, and its share's
base when that is not the total.

## Non-negotiables

- Forest-level uuid-keyed dedup at the aggregation boundary — never
  per-file, never content-keyed. A session is not a file (bg, /branch,
  --fork-session, sibling forks); per-file reading inflates totals by 94%.
- The tree INVERTS under these metrics: the injected subtree (~95% of
  observed chars) carries ZERO mass. Design output for that first.
- No estimated attribution: exact by subtracting the feed-forward term,
  everything else to ONE residual bucket, `ambiguous`, never a silent spread.
- Every figure names its population; exact/ambiguous/shrink/window-head
  rates are measured per run, never hard-coded.
- Tests derive assertions from the schema (never enumerate metric names as
  literals); every negative assertion has a vacuity guard beside it.
- Never sum a peak; a peak reports no value at a node. Never quote dollars.
- Shrink is a signed row: excluded from shares, always in the reconciliation
  footer. The residual row `∅` and signed rows never hide behind `--limit`;
  a table with no base prints `share` alone.

## Measured corrections — stay pinned by tests

`sa/usage.py` docstrings carry these (D-USAGE-DOCSTRINGS: the fact, its
population and date, nothing else); `tests/test_usage.py` pins the
bodies. Any engine-level choice (fact shape, carriers, causes, the
attribution walk, a measured correction) changes only via a logged ruling in
`references/DECISION_LOG.md` (argument or new measurement, plus an opus
second opinion). The recorded failure mode is the confident in-place
"improvement" that deletes a measured correction.

- Split `message.id`s are MAX-MERGED field-wise: 80.5% of ids split,
  73% of those disagree on `output_tokens`.
- `cache_creation` is NOT the increment: the identity (input + cache_read +
  cache_creation) holds on only 92.21% of pairs.
- Peak is never summed: 4,950,327 summed vs 131,612 true peak.
- Cache tiers priced per call: 1h write x2.0, 5m x1.25, read x0.1; one
  tier per call (0 mixed of 47,419).
- Shrinks are real and unclamped: 830 of 45,555 pairs.
- Feed-forward subtraction (`delta_occ >= out_prev`) holds on 97.79% of pairs.
- Physical line numbers, not parsed index. A filename is not a session.
- Contributors are token-relevant only (tool_result + user text), one per
  tool_result block; counting 2.1.28x bookkeeping attachments collapses the
  "exactly one non-assistant record" rate from 84% to under 1%, and their
  text folds into the one contributor's remainder.
- parentUuid links never cross files (0 of 1,523; 21 files, 2026-09-30):
  no parentUuid-chain window model.
- Local corpus (33 files, 2026-10-01): 67 user records sit inside 44 of 588
  calls' spans, so contributors come from the previous call's FIRST
  constituent; 0 of 808 tool_result records batch blocks; 79 of 127
  multi_contributor intervals (404k of 634k ambiguous tokens) share one
  tool, which `ambiguous` carries (D-AMBIGUOUS-TOOL).

## Clean-room boundary — binding on every session and subagent

v1 is frozen: `git show v1-legacy:<path>` (until that branch is pushed, the
installed `~/.claude/skills/session-analyzer/`). The ONLY files you may open
there:
`references/PURPOSE.md`, `references/ENGINE_CONTRACT.md`,
`references/glossary.md` (never invent synonyms for its terms), v1's
own `CLAUDE.md`, `scripts/lib/lib_drill.py`, `scripts/sa_schema.py`,
`tests/generate_fixtures.py`, and only the usage helpers of
`scripts/lib/lib_parse.py` (`usage_context`, `max_merge_usage`,
`usage_spend`, `context_delta`, `usage_cache_tier`). Everything else is OFF
LIMITS: code, tests, docs, history; v1's most authoritative documents tell a
reader to build what its tests forbid. Need another file? STOP AND ASK.

## Repo gates

Pre-commit warns on `.py` > 15,000 bytes and `.md` > 20,000. Privacy gate
FAILS CLOSED (`tests/test_privacy.py`): no literal `/home/...` or
`/Users/...` paths, no real-looking UUIDs, no transcript text in any tracked
file. `.githooks/pre-push` does not fire under the global `core.hooksPath`:
run `python3 -m pytest -q tests/` before every push. Doc caps: README ≤
5,000, SKILL.md ≤ 6,000, this file ≤ 7,000; example lines match live CLI
output (placeholder ids), so resync after any output change.

## Pointers, never copies

- `references/DESIGN_BRIEF.md` — §2 (the attribution walk) is the spec;
  the rest, 94.98% exact rate included, is dated.
- `references/DECISION_LOG.md` — rulings and status table;
  `DECISION_LOG_HISTORY.md` beside it — the rows as proposed.
- `references/DESIGN_COMPETITION.md`, `references/designs/` — design
  charter, competing designs, panel report.
- `references/PHASE0_MEASUREMENT.md` — what the raw transcripts carry.
- `references/PUBLISHING_PLAN.md` — extraction and distribution.
