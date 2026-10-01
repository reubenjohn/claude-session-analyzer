# session-analyzer v2 — standing context

Answers TWO questions about Claude Code sessions: where is my context going
(`context_delta`) and what did it cost (`spend`). Reads the JSONL transcripts
under `Path.home()/".claude"/"projects"` (computed at runtime, never a
literal path). Standard library only, Python 3.8. TIME/scheduling questions
are real and deliberately deferred: design so they can be added, do not add
them. Standing premise: NO USERS, NO DEPLOYMENTS — breaking changes are free,
legacy is deleted not accommodated, published numbers move when the old
number was wrong. Work happens on branch `v2-build`.

## Build charter (rulings of 2026-09-30, `references/DECISION_LOG.md`)

Owner directive: an elegant, simple implementation from which powerful
capabilities emerge. The ported ranking engine is RETIRED (D-ENGINE); the
path is a minimal clean implementation.

Package `sa/`: `usage.py` (the ported lib_usage helpers: function bodies
unchanged and pinned by test, docstrings hold only the measured
corrections), `corpus.py` (read files,
dedup, physical line numbers), `walk.py` (calls, intervals, attribution),
`schema.py` (the one METRICS table: name -> class, carrier, unit),
`query.py` (group/aggregate by dims, reconciliation), `cli.py` (two
subcommands: `context`, `spend`); `tests/`. The parser module IS the
product: probes import it, never copy it.

One data model, `Fact`: `kind` is `call` or `increment`; `metrics`; `dims`;
`locator` `file:line:uuid`. Every metric declares its single carrier kind
(`spend` -> call, `context_delta` -> increment) and the query layer reads it
only from that kind, so double-counting is impossible by construction.
Increment `cause` vocabulary: `feed_forward | tool_result | user_text |
ambiguous | shrink | window_head`. Unknown metric or cause fails closed.
A window IS a file in build v1 (R2): `window_head` is the first
usage-carrying call's occupancy — inherited context for a fork, boot context
for a fresh session — always its own labelled row, never spread. The parser
records a fork's `fork-context-ref` (`parentSessionId`, `parentLastUuid`) as
evidence on the window_head fact so stitching can be added later without a
schema change; no stitching ships in v1.

## Non-negotiables

- Forest-level uuid-keyed dedup at the aggregation boundary from day one —
  never per-file, never content-keyed. A window is not a file (bg, /branch,
  --fork-session, sibling forks); per-file reading inflates totals by 94%.
- The tree INVERTS under these metrics: the injected subtree (~95% of
  observed chars) carries ZERO mass. Design output for that before drawing.
- No estimated attribution. Exact attribution by subtracting the feed-forward
  term; everything else goes to ONE residual bucket, `ambiguous`, never a
  silent spread.
- Every figure names its population. Exact/ambiguous/shrink/window-head rates
  are measured per run and printed with their population — never hard-coded.
- Tests derive assertions from the schema (never enumerate metric names as
  literals); every negative assertion has a vacuity guard beside it.
- Never sum a peak; a peak reports no value at a node.
- Never quote dollars. Spend is in weighted tokens.
- Shrink is a signed row: excluded from share percentages, always present in
  the reconciliation footer. The headline names the top non-residual row.

## Measured corrections — stay pinned by tests

Docstrings in `sa/usage.py` carry these (D-USAGE-DOCSTRINGS: the measured
fact with its population and date, nothing else) and `tests/test_usage.py`
pins the function bodies; a change to either is a new measurement plus a
logged ruling, never a plausible rewrite.

- Split `message.id`s are MAX-MERGED field-wise: 80.5% of ids are split, and
  73% of those disagree on `output_tokens`.
- `cache_creation` is NOT the increment; the occupancy identity (input +
  cache_read + cache_creation) holds on only 92.21% of pairs for it.
- Peak is never summed: 4,950,327 summed vs 131,612 true peak.
- Cache tiers priced per call: 1h write x2.0, 5m write x1.25, read x0.1.
  Exactly one tier applies to any one call (0 mixed of 47,419; the tier
  totals equal `cache_creation_input_tokens` on every one).
- Shrinks are real and unclamped: 830 of 45,555 pairs.
- Feed-forward subtraction (`delta_occ >= out_prev`) holds on 97.79% of pairs.
- Physical line numbers, not parsed index. A filename is not a session.
- Contributors are token-relevant only (tool_result + user text): 2.1.28x
  transcripts emit per-turn bookkeeping attachments that collapse the
  "exactly one non-assistant record" rate from 84% to under 1% if counted.
  "Exact" is exact given the feed-forward model: an attachment's text in an
  exact interval folds into the single contributor's remainder.
- parentUuid links never cross files (0 of 1,523; 21-file probe,
  2026-09-30), so no parentUuid-chain window model.
- A split call's constituents interleave with their results (parallel tool
  use): 54 user records sit strictly inside 32 of 362 calls' spans (27-file
  local corpus, 2026-09-30). An interval's contributors are therefore taken
  from the previous call's FIRST constituent; slicing from its last booked
  24 two-contributor intervals (180,817 tokens) as exact on the same corpus.

## Clean-room boundary — binding on every session and subagent

v1 is frozen. Once the `v1-legacy` branch is pushed, read it with
`git show v1-legacy:<path>`; until then the installed skill at
`~/.claude/skills/session-analyzer/`. The ONLY files you may open there:

- `references/PURPOSE.md`, `references/ENGINE_CONTRACT.md`,
  `references/glossary.md` (never invent a synonym for an existing term),
  v1's own `CLAUDE.md`
- `scripts/lib/lib_drill.py`, `scripts/sa_schema.py`,
  `tests/generate_fixtures.py`
- `scripts/lib/lib_parse.py` — usage helpers only (`usage_context`,
  `max_merge_usage`, `usage_spend`, `context_delta`, `usage_cache_tier`)

Everything else is OFF LIMITS: code, tests, docs, history. Several of v1's
most authoritative documents instruct a reader to build what a test forbids.
Wanting to see how v1 solved something is the impulse this boundary catches.
Need another file? STOP AND ASK the owner.

## Channel of change

Engine-level choices (fact shape, carrier table, cause vocabulary, the
attribution walk, any measured correction) change only via a logged ruling
in `references/DECISION_LOG.md` with an argument or a new measurement, plus
an opus second opinion. The recorded failure mode is the confident in-place
"improvement" that deletes a measured correction.

## Repo gates

Pre-commit warns on `.py` > 15,000 chars and `.md` > 20,000. Privacy gate
FAILS CLOSED: no literal
`/home/...` or `/Users/...` paths, no real-looking UUIDs, no transcript text
in any tracked file. The global hook's checker is not yet wired to this
standalone repo, so scan before every push (PUBLISHING_PLAN standing rules).

## Pointers, never copies

- `references/DESIGN_BRIEF.md` — historical design; §2 (the attribution
  walk) is still the spec. The 94.98% exact-rate note is dated, not blessed.
- `references/DECISION_LOG.md` — rulings and their history.
- `references/PHASE0_MEASUREMENT.md` — what the raw transcripts carry.
- `references/PUBLISHING_PLAN.md` — extraction steps and distribution.
