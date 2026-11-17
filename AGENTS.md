# session-analyzer v2 — standing context

Purpose (README): what did it cost (`spend`); cost aside (were
inference free), is context rotting my model, what fills it, what to
cut (`context`). From `~/.claude/projects`; stdlib, Python 3.8.
TIME/scheduling questions are deferred: design for them, add none.
Standing premise: NO USERS, NO DEPLOYMENTS — breaking changes are free,
legacy is deleted, published numbers move when the old one was wrong.

## Build charter (rulings: `references/DECISION_LOG.md`)

Owner directive: an elegant, simple implementation from which powerful
capabilities emerge. The ported ranking engine is RETIRED (D-ENGINE).

Package `sa/`, one module per stage (`corpus` read+dedup, `windows`
the cut, `walk` attribution, `heads`, `schema` METRICS, vocabularies,
`glossary`, `query`, `reconciliation`, `grammar`, `cli`, `render`,
`headline`, `tables`, `leaves`, `notes`, `checks`, `style`, `usage`
ported); each docstring is its spec. The parser IS the product:
`sa.sweep` imports it.

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
`session`, `subagent` (none on a main window, else `<type> <8 hex>`),
`window` (8 hex of its key), `started_by`, `peak` (its largest call's
band, D-PEAK-BAND) are on both kinds; `cause`,
`tool`, `command`, `reason` on increments only (printed: changes). A command is `<tool>:<summary>`: a Bash command's first command word
(`Bash:pytest`) or a file tool's extension (`Read:py`); never a path. Unknown names, undeclared values and a pin value no fact
carries exit 2 (`query.narrow`), naming the nearest.
`starting_context` (never split by content) and `ambiguous` are rows,
never spread or a lever. A fork's copy is one `inherited`
increment, held by the fork's calls; a parentless fork is counted, not
fixed (D-MISSING-PARENT).

CLI: `python3 -m sa -h`, one grammar. Order: scope (`read:`, `in view:`;
`--since` 7d unless `all`), answer, `View.tables`, the `by DIM` and
`-v` commands, the `✓` lines (`checks`). Context is
per call (D-PER-CALL): each change x the calls that held it
(`context_held`) over the calls in view; rows add up to the headline's
average, shares of it before shrink; `query.per` refuses it without one
population. Under it: starting context by `started_by`, then growth down
`View.levers` (context `tool`, `command`; spend `subagent`) whatever
`by` shows. `*` marks terms, not values. A pin omits every
table and lever whose facts share one value (a command implies its
tool); the headline names a pin. `glossary` drives `-v`, `*`.
Both identities hold by construction (`walk`): MISMATCH is a bug, exit 1.

## Non-negotiables

- Forest-level dedup by uuid and, across files only, by a call's
  `message.id` (D-MESSAGE-ID-DEDUP) — never per-file, never
  content-keyed. A session is not a file (bg, /branch, forks); per-file
  reading inflates totals by 94%.
- The tree INVERTS: the injected subtree (~95% of observed chars)
  carries ZERO mass. Design output for that first.
- No estimated attribution: exact by subtracting the previous reply,
  everything else to ONE residual bucket, `ambiguous`, never a silent spread.
- Every figure names its population; exact/ambiguous/shrink rates are
  measured per run.
- Tests derive assertions from the schema (never metric names as
  literals); every negative assertion has a vacuity guard.
- Never sum a peak, nor a per-call figure across populations. No dollars.
- Shrink is a signed row, in no share; checks: in `-v`, and on trigger. The
  catch-all row (`schema.residual_label`), signed rows and cause rows never fold
  into `+N more`; a share is of the `= 100%` row.

## Measured corrections — stay pinned by tests

`sa/usage.py` docstrings carry these (D-USAGE-DOCSTRINGS);
`tests/test_usage.py` pins the bodies. An engine-level choice changes
only by a logged ruling (argument or measurement, plus an opus
second opinion). Display labels, phrasing and
styling need no ruling. The recorded failure mode: a confident in-place
"improvement" that deletes a measured correction.

- Split `message.id`s are MAX-MERGED field-wise: 80.5% of ids split,
  73% of those disagree on `output_tokens`.
- `cache_creation` is NOT the increment: the identity (input + cache_read +
  cache_creation) holds on only 92.21% of pairs.
- Peak is never summed: 4,950,327 summed vs 131,612 true peak.
- Cache tiers priced per call: 1h write x2.0, 5m x1.25, read x0.1; one
  tier per call (0 mixed of 47,419).
- Shrinks are real and unclamped: 830 of 45,555 pairs.
- Reply subtraction (`delta_occ >= out_prev`) holds on 97.79% of pairs.
- Physical line numbers, not parsed index. A filename is no session.
- Contributors are token-relevant only (tool_result + user text), one per
  tool_result block; counting 2.1.28x bookkeeping attachments drops the
  exact rate from 84% to <1%; their text folds into the remainder.
- Local figures: a dated `python3 -m sa.sweep` snapshot.

## Clean-room boundary — binds every session and subagent

v1 is frozen at the installed `~/.claude/skills/session-analyzer/`
(`v1-legacy` branch: PUBLISHING_PLAN step 1). The ONLY files you may open:
`references/PURPOSE.md`, `references/ENGINE_CONTRACT.md`,
`references/glossary.md` (never invent synonyms for its terms), v1's
own `CLAUDE.md`, `scripts/lib/lib_drill.py`, `scripts/sa_schema.py`,
`tests/generate_fixtures.py`, and only the usage helpers of
`scripts/lib/lib_parse.py` (`usage_context`, `max_merge_usage`,
`usage_spend`, `context_delta`, `usage_cache_tier`). Everything else is OFF
LIMITS: code, tests, docs, history. Need another file? STOP AND ASK.

## Repo gates

Pre-commit warns: `.py` > 15,000 bytes, `.md` > 20,000. Privacy gate
FAILS CLOSED (`tests/test_privacy.py`): no literal `/home/...` or
`/Users/...` paths, no real-looking UUIDs, no transcript text in any tracked
file. CI (`.github/workflows/ci.yml`) runs the suite; you, before
pushing (`.githooks/pre-push` is inert). `tests/test_docs.py`: byte
caps (README 5,000, SKILL.md 6,000, this file 7,000); examples =
fixture output (`scripts/resync_examples.py`).

## Pointers, never copies

`references/`: `DESIGN_BRIEF.md` (the walk: the spec),
`DECISION_LOG.md` (rulings, Filed),
`PHASE0_MEASUREMENT.md`, `PUBLISHING_PLAN.md` (release, `CHANGELOG.md`).
`UX_PRINCIPLES.md` binds every screen and file: read first.
`scripts/screens.py` (every screen), `evals/README.md`.
