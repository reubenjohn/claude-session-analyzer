# UX feedback — first cold use by the owner (2026-11-14)

The owner ran `python3 -m sa -h` and `python3 -m sa context --since 7d`
with little context about the tool. Goal: a user walks away knowing, at a
high level, what fills their context, and can narrow it to contributors they
can fix. Never more verbose; organise concepts into fewer patterns.

Tracks: **A1** presentation, independent of rulings (do now). **A2**
presentation that depends on B's vocabulary (after rulings). **B** model
changes: measure, propose, owner rules (`DECISION_LOG.md`), then build.

| # | Track | Item | Done when |
|---|---|---|---|
| 1 | A1 | No sense of scope or progress; a full-corpus run is silent for minutes. Default `--since 7d`, `--since all` escape hatch. | First output line names the files, the window (`7d (default)`) and the root; `--since all` reads everything; tests pin both. |
| 2 | A1 | `-h` repeats internal terms and teaches no model (what a dimension, drill, `--where`/`--by` are). | Top-level help says in plain words what each view answers and shows the overview → `--where` → `--by` workflow in about 3 example lines. |
| 3 | A1 | Output is dense and machine-ordered: semicolon sentences carrying five ideas; notes in many formats; a share base that silently changes per table; no visual hierarchy; long IDs and absolute home paths. | Order is scope → answer → tables → checks; one idea per line; notes collapse into one dimmed key; share column names its base; colour only on a TTY and honours `NO_COLOR`; home prints as `~`. |
| 7 | A1 (mechanism) / A2 (labels) | Internal terms (`context_delta`, `feed_forward`, increment facts, …) mean nothing to users. Rule: rename until a term explains itself; an explain marker (`term°`) only for irreducible concepts (window/start, ambiguous, `∅`). | One glossary table in `schema.py` drives `sa explain [term]`, the markers and `--help`; each entry has a "why this number might surprise you" line. |
| 8 | A1 | Top-level help hides the subcommand flags (`--by fact` was found only via a note). | The top-level help names the flags or points to `sa context --help` with one example each. |
| 12 | A1 | The reconciliation is a dense sentence separate from the cause table. | The cause table ends with a total row `= N ✓ matches final window sizes`; the interval line collapses to one ✓ checks line; full detail only on failure. |
| 10 | A2 | "by head" is unexplained. `head` is a glossary term (no synonyms), so a display label or a rename ruling. | The table label explains itself (e.g. "command / file type"), or a ruling renames the term. |
| 6 | A2+B | The headline should be *starting context vs growth*, each with its own breakdown; growth is the part you drill into. | Headline: starting context N (share) by trigger; growth N (share) by tool → head. |
| 4 | B | The context total is net (the sum of final occupancies): compaction and other shrinks hide what entered (700K → compact → 70K reports 70K). Context only; spend is per call and unaffected. | Resolved by 5 plus the shrink presentation. |
| 5 | B | Split a window at each compaction: a compaction is a new start, like a fork. Contradicts R2 (a window is a file). | Probe measures marker/drop alignment, whether the summary call is in the transcript, replayed-copy boundaries, unmarked shrinks; ruling logged; reconciliation still exact. |
| 9 | B | `window_head` is opaque. What triggered the window (session start, subagent prompt, fork/branch, resume, compaction) is exact and can be a dimension; splitting the content (system prompt vs CLAUDE.md vs tools) is an estimate and needs a ruling (no estimated attribution). | Trigger classification measured (coverage, unclassifiable rate); starting context broken down by trigger. |
| 13 | B | A fork's inherited prefix is already attributed exactly in the parent window; reporting it as an opaque head discards that. Totals: unique context vs per-window. | Probe measures the fork prefixes; ruling on how totals count inherited context. |
| 11 | pinned | Qualify agents with their session (and sessions with their project) without becoming verbose. | — |

## Acceptance for every item

The full suite passes, as do the privacy gate and the doc caps; README/SKILL
example lines are resynced to live output. A **cold reader** (a fresh agent
with no repo context, given only `--help` and one live output) can answer:
what fills my context, what should I fix first, and what is a window.

## A2 status (2026-11-15)

Done under D-PLAIN-TERMS: items 6, 7 (labels) and 10. Causes `replies`,
`starting_context`; dimensions `started_by`, `command` ("by command /
file type"), `subagent`; reasons `several`, `less_than_reply`,
`unexplained`; printed `context tokens`, `changes`, `calls`; `-h` says
subcommand and pin. `sa/glossary.py` holds the glossary; key entries are
one clause. Output cut below pre-A1 (one read line, share base named
once, `--limit 5`, the cause table whole). Cold-reader check passed twice
(2026-11-15): all three questions answered from `-h` plus one live output.

## Filed for a later pass (triaged 2026-11-15)

- Residual cold-reader guesses: `changes` never defined on screen; `incl.
  ambiguous` lets tool=Bash exceed cause=tool_result (D-AMBIGUOUS-TOOL);
  each table's own `all but ∅` base; `exact`/`shrink` in the checks line;
  `replayed`; encoded project names (`~--home…`).
- Starting line's total includes `inherited` when the parent is out of
  scope, while the cause table splits them.
- `subagent` is both a dimension and a `started_by` value.
- No CLI filter shows a parent's breakdown up to a branch call except a
  pinned fork.
- Fixture corpus is thin (one head at 100%); fixture output now sits well
  under D-OUTPUT-CAP (lowering it is an owner ruling).
- Size headroom: SKILL.md 6,000/6,000, CLAUDE.md ~6,970/7,000,
  DECISION_LOG*.md near 20,000; schema-adjacent tests near 15,000.
- Fork/compaction/`/branch` counts are small (10/9/0): re-measure before
  pinning; `replayed` is declared with 0 observed.
