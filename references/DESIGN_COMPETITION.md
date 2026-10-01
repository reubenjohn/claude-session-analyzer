# Design competition charter — session-analyzer v2

Process artifact for the clean-room rebuild's design phase. Every designer and
critic agent is pointed at this file. It is disposable with the branch.

## Mission

Design the v2 data model and query/presentation architecture for two questions
only: **where is my context going** (`context_delta`) and **what did it cost**
(`spend`). TIME questions are real and deliberately deferred — design so they
can be added later; do not design them now. A brief that covers time is out of
scope and will be sent back.

Much of the design space is CLOSED — but by claim-kind, not by file. Parsing
corrections are MEASURED. Aggregation-class arithmetic is settled. The engine
(`lib_drill.py`, `sa_schema.py`) is ported verbatim as the STARTING STATE; its
[OPEN]-tagged choices (multiplication as the score combinator, cover as a fact
count, missing-key/null unification, the purity boundary, …) are legitimate
challenge targets — propose changes in your brief's decision-log entries with
argument or a new measurement, and expect them to land only via owner ruling,
never as in-place edits. The two problems where design freedom is widest:

1. **The fact/locator data model.** v1 cannot do attribution because a
   generation's locator is a single index with no end and no constituent list,
   and its tool_result facts carry no `tool_use_id` (all its tool_calls do).
   The v2 model must fix this at the source. See PHASE0_MEASUREMENT.md for what
   the raw transcripts actually carry — ground your design in those numbers.
2. **The query/presentation architecture.** v1's presentation layer is ~40
   hand-maintained tables keyed by view name, three of which fail silently.
   Assume that layer is wrong. PURPOSE.md argues "which one" is usually the
   wrong shape of answer — the biggest lever often lives on a different slice
   than the one the question arrived in. Make cross-slice pivots cheap.

## Clean-room boundary

You may read, under `user_home/.claude/skills/session-analyzer/`:
`references/PURPOSE.md`, `references/ENGINE_CONTRACT.md`,
`references/glossary.md`, and the skill's own `CLAUDE.md`. Under
`user_home/.claude/skills/session-analyzer-v2/`: everything (it is the build).
Nothing else under the v1 directory — not its other code, tests, docs, or git
history. Several of its confident-sounding documents instruct a reader to build
something a test forbids.

## What is closed, and how to challenge

ENGINE_CONTRACT tags every invariant. `[ARITHMETIC]` is not open. `[MEASURED]`
opens only to a new measurement, never an argument. `[RULING]` is the owner's.
`[OPEN]` is fully open — aim creativity there. If an invariant looks MISFILED
(especially ARITHMETIC that is really a design choice), flag it explicitly in a
"suspected misfiles" section — that is a welcome finding, routed to the owner.

Non-negotiable constraints carried from the build brief:

- Port, never rewrite, the engine files. Take the files, not the ideas.
- Forest-level uuid-keyed dedup at the aggregation boundary from day one —
  never per-file, never content-keyed. A window is not a file; bg, /branch,
  --fork-session and sibling forks continue one window in a new file; reading
  those as independent sessions inflates totals by 94%.
- The tree INVERTS under these metrics: the injected subtree that is ~95% of
  observed chars carries ZERO mass under `context_delta`/`spend`. Design output
  for that before drawing anything.
- Do NOT promise estimated attribution in v1 of the build. ~77% of intervals
  attribute exactly by subtracting the feed-forward term; the other ~23% has no
  honest estimator. One residual bucket named *ambiguous*, never silently
  spread.
- Every figure names the population it was measured over. Estimates are
  labelled estimates.
- Tests derive assertions from the schema (never enumerate metric names) and
  every negative assertion carries a vacuity guard.

## Design gates (the complexity auditor scores these)

- **Derivation over enumeration.** Any surface that lists metrics, views, or
  dimensions by hand is a defect unless a test sweeps it and asserts the sweep
  found something. v1's disease: 40 hand-maintained tables, 3 fail-silent.
- Adding a metric touches exactly ONE declaration. Adding a dimension touches
  exactly ONE declaration. A "view" should be a query/preset, not a
  registration surface.
- Zero fail-silent surfaces. Unclassified metric fails closed.
- The engine stays free of CLI, rendering, I/O, clock, randomness.
- Repo gates: .py files < 15,000 chars, .md < 20,000; no literal /home or
  /Users paths; no real-looking UUIDs in tracked files.

## Required answers (the owner's four questions)

1. **The data model.** What is a fact, what does it carry, why that shape.
2. **The question that justifies the rewrite.** Show CONCRETELY how the model
   enables exact attribution: walk one interval from raw records to "this tool
   result added N tokens to the window", naming every field the walk touches.
   Ground it in PHASE0_MEASUREMENT.md. If the walk cannot be completed, say so
   plainly — that is a verdict, not a failure of the brief.
3. **Divergence from v1's [OPEN] choices**, and why, item by item.
4. **What you are deliberately not building.**

## Output format per designer

A single markdown brief, ≤ 12,000 chars, structured as: stance (one line),
answers 1–4, suspected misfiles (may be empty), and a "weakest point" section
naming the one place you expect critics to land. WRITE it to
`references/designs/DESIGN_<letter>.md` in the v2 tree (do not git-commit;
privacy gates apply) and return only a lean completion message: stance,
attribution headline, misfile count, weakest point, file path. Full briefs
never travel through the orchestrator's context — the panel coordinator reads
them from disk, runs critics against them, and manages revision rounds there.

## Phase 0 findings

See `PHASE0_MEASUREMENT.md` in this directory once landed. If it is absent,
STOP and report that upward instead of designing on assumption.
