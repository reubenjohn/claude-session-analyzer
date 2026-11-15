# session-analyzer v2 — standing context

Answers TWO questions about Claude Code sessions: where is my context going
(`context_delta`) and what did it cost (`spend`), from the JSONL transcripts
under `~/.claude/projects`. Stdlib, Python 3.8.
TIME/scheduling questions are deferred: design for them, do not add them.
Standing premise: NO USERS, NO DEPLOYMENTS — breaking changes are free,
legacy is deleted, published numbers move when the old one was wrong.

## Build charter (rulings: `references/DECISION_LOG.md`)

Owner directive: an elegant, simple implementation from which powerful
capabilities emerge. The ported ranking engine is RETIRED (D-ENGINE).

Package `sa/`, one module per stage (`corpus` read+dedup, `windows`
the cut, `walk` attribution, `heads`, `schema` METRICS, vocabularies,
`query`, `headline`, `tables`, `render`, `cli`, `usage` the ported helpers); each
docstring is its spec. The parser IS the product: probes import it, never copy it.

One data model, `Fact`, specified in `schema.py`: `kind` is `call` or
`increment`; `metrics`; `dims`; `locator` `file:line:uuid` with `file`
relative to the corpus root; `window` its `WindowKey`; `evidence` (not a
dimension: `candidates`, a fork's parent window and branch call). Every metric
names its one carrier kind (`spend` -> call,
`context_delta` -> increment) and is read only from that kind: no
double-counting. A window is ONE CONTEXT WINDOW (D-CONTEXT-WINDOW): from
a session start, subagent, fork, replay or a compaction a call follows, to
its file's end or the next compaction; cut after dedup, never by marking
records; identity (file, start line). Window dimensions `project`,
`session`, `agent` (none on a main window), `window` (8 hex of the key:
display and `--where` only) and `start` are on both kinds; `cause`, `tool`, `head`, `reason`
on increments only. A head
is `<tool>:<summary>`: a Bash command's first COMMAND word (past keywords,
wrappers, builtins) as a basename (`Bash:pytest`), or a file tool's
extension (`Read:py`); never a path (R5). Unknown names, undeclared
values and a `--where` value no fact carries exit 2 (`query.narrow`),
naming what is present. `window_head` (never split by content) and
`ambiguous` are rows, never spread, never a lever. A fork's copy is one
`inherited` increment, counted once (D-INHERITED-ONCE).

CLI: `python3 -m sa -h`. Order: scope (`read:`, `kept:`; `--since` 7d
unless `all`), answer, tables, one dimmed key, `✓ checks`. Under one
total (D-HEADLINE-TWO-LINES): starting context by `start` (mass that
entered, not a window size), then growth down `View.levers` (context
`tool`, `head`; spend `agent`) whatever `--by` shows (`headline._top`);
shares of the mass added. A `--where` pin omits every table and lever whose facts share one
value (a head implies its tool); a drill pin is named on the headline. A
table repeating the one above row for row is one relabel line.
D-OUTPUT-CAP caps the default output.
`schema.GLOSSARY` drives `sa explain`, `°`, `--help`. The reconciliation
holds by construction (`walk`): MISMATCH is a bug, exit 1.

## Non-negotiables

- Forest-level dedup at the aggregation boundary, by uuid and, across
  files only, by a call's `message.id` (D-MESSAGE-ID-DEDUP) — never
  per-file, never content-keyed. A session is not a file (bg, /branch,
  forks); per-file reading inflates totals by 94%.
- The tree INVERTS under these metrics: the injected subtree (~95% of
  observed chars) carries ZERO mass. Design output for that first.
- No estimated attribution: exact by subtracting the feed-forward term,
  everything else to ONE residual bucket, `ambiguous`, never a silent spread.
- Every figure names its population; the exact/ambiguous/shrink rates are
  measured per run, never hard-coded.
- Tests derive assertions from the schema (never enumerate metric names as
  literals); every negative assertion has a vacuity guard.
- Never sum a peak; a peak reports no value at a node. Never quote dollars.
- Shrink is a signed row: excluded from shares, always in the reconciliation
  footer. The residual row `∅` and signed rows never hide behind `--limit`;
  a table with no base prints `share` alone.

## Measured corrections — stay pinned by tests

`sa/usage.py` docstrings carry these (D-USAGE-DOCSTRINGS);
`tests/test_usage.py` pins the bodies. Any engine-level choice changes
only via a logged ruling in `references/DECISION_LOG.md` (argument or
measurement, plus an opus second opinion). The recorded failure mode: a
confident in-place "improvement" that deletes a measured correction.

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
  tool_result block; counting 2.1.28x bookkeeping attachments drops the
  exact rate from 84% to <1%; their text folds into the remainder.
- Local figures (batched results, call spans, shared-tool ambiguity,
  re-mints, parentUuid links never cross files, windows, forks): dated
  snapshots by `python3 -m sa.sweep`, `sa.probe_window_model`.

## Clean-room boundary — binds every session and subagent

v1 is frozen at the installed `~/.claude/skills/session-analyzer/`
(`v1-legacy` branch: PUBLISHING_PLAN step 1). The ONLY files you may open:
`references/PURPOSE.md`, `references/ENGINE_CONTRACT.md`,
`references/glossary.md` (never invent synonyms for its terms), v1's
own `CLAUDE.md`, `scripts/lib/lib_drill.py`, `scripts/sa_schema.py`,
`tests/generate_fixtures.py`, and only the usage helpers of
`scripts/lib/lib_parse.py` (`usage_context`, `max_merge_usage`,
`usage_spend`, `context_delta`, `usage_cache_tier`). Everything else is OFF
LIMITS: code, tests, docs, history (its docs contradict its tests). Need
another file? STOP AND ASK.

## Repo gates

Pre-commit warns on `.py` > 15,000 bytes and `.md` > 20,000. Privacy gate
FAILS CLOSED (`tests/test_privacy.py`): no literal `/home/...` or
`/Users/...` paths, no real-looking UUIDs, no transcript text in any tracked
file. `.githooks/pre-push` does not fire (global `core.hooksPath`): run
the suite before pushing. Tested: doc caps in bytes (README 5,000,
SKILL.md 6,000, this file 7,000); examples = fixture output, synced by
`scripts/resync_examples.py`.

## Pointers, never copies

`references/`: `DESIGN_BRIEF.md` §2 (the attribution walk, the spec),
`DECISION_LOG.md` (rulings; `_HISTORY.md` as proposed),
`PHASE0_MEASUREMENT.md`, `PUBLISHING_PLAN.md`, `DESIGN_COMPETITION.md`.
