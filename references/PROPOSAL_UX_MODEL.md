# Proposal — the UX model change (track B of `UX_FEEDBACK.md`)

Items 4, 5, 6, 9, 13. Status: PROPOSED, awaiting owner rulings; nothing
here is built. Every figure is one run of `python3 -m sa.probe_ux`
(stamped `UX PROBE 2026-11-15T08:04Z`), which imports `sa.corpus` and
`sa.walk`, over this machine's live corpus: 591 files, 577 windows (files
with a call), 23,556 calls, 22,979 intervals. A snapshot, not reproducible
elsewhere; the small populations (9 markers, 10 forks) are named beside
each figure and should be re-measured before any figure is quoted in code.
The probe was folded into `python3 -m sa.sweep`, which measures with the engine.

## 1. Compaction (items 4, 5)

**Measured.**

| Question | Result (population) |
|---|---|
| Markers | 9 `compact_boundary` system records, all live (owned); 0 inside replayed copies, because no main file in this corpus replays another (§3) |
| Windows holding one | 8, all main windows |
| Drop aligns with the marker | 5 of 5 markers with a call after: the occupancy drops at the NEXT call. The other 4 end the file: the session stopped after compacting |
| `preTokens` vs the previous call | within 1% on 4 of 5, differs on 1 |
| `postTokens` vs the next call | the next call is 10k–100k larger on 5 of 5: `postTokens` does not measure the new head |
| Summarizing call in the transcript | NO: 0 assistant records between marker and next call; 0 of 23,379 `api-request` records carry a compact `querySource`. The summary arrives as an `isCompactSummary` user record (9 of 9) |
| Shrinks | 8 intervals (-764,300 tokens): 5 with a marker between the calls (-756,043), 3 without (-8,257; sizes 2 at 1k–10k, 1 under 1k; 2 of the 3 change model between the calls; 2 have user text between) |

**Item 4, quantified.** Net totals hide 756,043 tokens of pre-compaction
context: 1.18% of the 63,834,960 corpus total, 99% of all shrink mass.

**Options.**
- **A. Keep R2; relabel.** A marker-bracketed shrink becomes cause
  `compaction` (a signed row like `shrink`). The total stays net. Cheap,
  but the user still reads "70K" for a 700K session.
- **B. Cut the window at each marker (recommended).** A compaction is a
  new start: the first call after the marker books `window_head` with
  trigger `compaction`; the pre-compaction occupancy stays booked in the
  segment that ended. A segment with no call (4 of 9 here) is no window.
- **C. Cut at every shrink.** Rejected: 3 unmarked shrinks are small and
  2 are model switches; a cut there invents a start no record names.

**Reconciliation under B, measured** (same run, cutting by marking the
records outside each segment as duplicate, then the unchanged `walk`):

| | as files (today) | cut at markers |
|---|---|---|
| windows | 577 | 582 |
| intervals | 22,979 | 22,974 |
| context total | 63,834,960 | 64,889,325 (+1.65%) |
| window_head | 22,637,400 (35.46%) | 22,935,722 (35.35%) |
| growth (total - head) | 41,197,560 | 41,953,603 |
| exact | 19,445 (84.62%) | 19,445 (84.64%) |
| ambiguous | 3,526 (15.34%) | 3,526 (15.35%) |
| shrink | 8 (-764,300) | 3 (-8,257) |
| `holds` | True | True |

The identity telescopes per segment by construction; the +1,054,365 is
exactly the 756,043 shrink no longer netted plus 298,322 of five new
compaction heads. Rates move in the second decimal.

**Spend.** Unaffected in attribution, but the summarizing call is not
recorded, so `spend` silently omits every compaction's cost. The
population line should say so ("compaction calls are not in transcripts:
N compactions unpriced").

## 2. Window starts (item 9)

**Measured** over the 577 windows: every one classifies, 0 unclassifiable,
0 conflicting fields.

| Trigger | Windows | Deciding fields |
|---|---|---|
| session start | 67 | main path layout, no replayed prefix |
| subagent | 500 | `subagents/` path and `agentId` (agree on 577 of 577) |
| fork | 10 | 1 by a `fork-context-ref` record; 9 by a replayed prefix (the first id-bearing record is a forest-dedup duplicate) |
| compaction | 5 (under §1 B) | a live `compact_boundary` |
| resume | 0 | no main file opens with a replayed prefix |

Corroboration: `api-request.querySource` (`agent:builtin:fork` vs the
rest) agrees with the inherited-prefix rule on every window that has it
(567 of 577; 10 older-version windows carry none). Resume appends in place
in the versions recorded here: 39 intervals span an idle gap of 1h or
more, 2 of them shrink; the chain is unbroken, so a resume is not a start
of context (it is a cache event, a spend concern). `resume` stays a
declared value (counted, 0 here) so an older-version replayed main file
is labelled rather than miscounted, as `no_contributor` was.

**Recommendation.** A window dimension `trigger`, constant per window,
on both kinds (so `spend --by trigger` answers "what do forks cost"):
values `session_start`, `subagent`, `fork`, `compaction`, `resume`. It is
exact: read from records, never inferred from sizes.

## 3. Forks and inherited context (item 13)

**Measured** over the 10 fork windows (the parent call found for 10 of
10: the last replayed call, or the call at `parentLastUuid`):

- The parent window's booked increments through the branch call equal the
  parent's occupancy at that call on 10 of 10: the inherited prefix's
  attribution (cause, tool, head) is recoverable exactly from the parent
  window, by reference.
- Fork head / parent occupancy: 1.0058 to 1.0335; head at least the
  parent occupancy on 10 of 10. Subtracting the parent's last output too
  leaves a negative remainder on 6 of 10, so the fork's own addition is
  `head - parent occupancy`, not a feed-forward split.
- Inherited: 1,090,134 tokens, 98.15% of the fork heads' 1,110,679, and
  1.71% of the total: 63,834,960 counted per window, 62,744,826 unique.

**Options.**
- **A. Per window (today).** The fork head is one opaque row.
- **B. Split the head, totals stay per window (recommended).** Book the
  fork's head as two increments: `inherited` (= parent occupancy at the
  branch call; evidence: the parent window and call locator) and
  `window_head` (the remainder). The sum is unchanged, so the
  reconciliation holds; `inherited` is a labelled row like `ambiguous`,
  never re-spread to tool/head in the fork (that would double-book the
  parent's facts). "Where it came from" is a drill to the parent window.
- **C. Unique totals.** Drop inherited mass from corpus-wide totals.
  Rejected for now: a window really carried those tokens (occupancy is per
  window), and at 1.71% the second total costs more reading than it
  saves. Revisit if forks grow.

## 4. window_head content (item 9, second half)

**Measured** over the 567 fresh windows (session start + subagent):

- 558 have an `api-request-shape` record before the first call carrying
  the system blocks and tool definitions: 1,850,953 system characters and
  30,502,442 tool-JSON characters against 21,526,721 head tokens. Those
  are characters; tokens per segment are not recorded.
- The first call reads cache on 341 of 567. Of the 21 `shapeHash` groups
  with a warm first call, 13 show one `cache_read` value and 8 several:
  the cache boundary is not a stable exact system+tools size.
- CLAUDE.md and the first user message have no separate token count.

**Recommendation.** No content split: every available split is an
estimate (characters to tokens, or a cache boundary that varies), and the
non-negotiable forbids estimated attribution. Starting context is broken
down by `trigger` (exact) only. `sa explain window_head` may say in words
that fresh heads are mostly system prompt and tool definitions, quoting
no number.

## 5. Vocabulary: what the user reads (item 6)

The headline becomes two lines, each with one breakdown:

```
starting context  23.0M (35%)  by trigger: subagent …, session_start …, compaction …, fork …
growth            42.0M (65%)  by tool → head: top tool=Bash …, within it head=Bash:pytest …
```

- **starting context** = every `window_head` and `inherited` increment:
  what a window held at its first call. Its breakdown is `trigger`, then
  for forks `inherited` vs the fork's own addition. Not a lever: the user
  cannot shrink a system prompt by drilling; the explain line says why.
- **growth** = everything after the first call (feed-forward, exact,
  ambiguous, the signed shrink row): the part to drill and fix. The
  existing levers (tool, then head) apply here only.
- **window** = a stretch of one transcript file between its start and a
  compaction (or the file's end); a main window without compaction is its
  file, as today. Explain marker `window°`.
- A user reads "700K → compact → 70K" as one 700K window ended by
  compaction plus a 70K `compaction` start, and the total says 770K+:
  what entered, not what was left.

## 6. Rulings this contradicts or amends

| Ruling | Change |
|---|---|
| **R2** (a window is a file) | A window becomes a file segment between compaction markers. Files are still never stitched. v1's glossary already says a window "is not a file"; this moves toward it without the falsified parentUuid model |
| **D-WINDOW-DIM** (`window` = root-relative file name) | A segment after the first needs a value: file name plus `#k` (k ≥ 1), so a marker-less window keeps its name |
| `query.reconcile` / `query.window_count` key windows by `locator.file` | Must key by the `window` dimension; a locator stays `file:line:uuid` (keyed by file, two segments would merge and the mass check would read only the last segment's final occupancy) |
| **R2 consequence** ("no stitching ships"; `window_head` one row) | Option 3B reads the parent's occupancy at the branch call and splits the fork head into `inherited` + `window_head`: reference-only stitching, no re-attribution |
| **P2** (shrink is the signed row) | Unchanged as a rule, but a compaction drop is no longer a shrink; published context totals move +1.65% here (allowed: the old number was net) |
| **D-HEADLINE-SPECIFIC** (levers never a window dimension) | The starting-context line breaks down by `trigger`, a window dimension; it is a second headline line, not a lever, so the lever rule stands for growth |
| `window_head` and `ambiguous` "never a lever" (CLAUDE.md) | Stands; `trigger` splits `window_head` exactly by a record field, which is not a spread |
| Schema vocabulary | New: dimension `trigger` and its five values; cause `inherited`. Glossary check: none of `trigger`, `starting context`, `growth`, `inherited` is a v1 glossary term, so no synonym is invented |

## Recommended order

1. Rule on R2-as-segments (1B) and `trigger` (2): both are exact and
   unlock the two-line headline. 2. `inherited` (3B), small. 3. Item 4
   closes with 1B. 4. Re-run the probe and pin its figures in docstrings
   by date, as `sa.sweep`'s are.

## Second opinion

Re-run `UX PROBE 2026-11-15T08:08Z` (594 files, 580 windows): every
figure reproduces up to corpus growth (9 markers, 5/4 split, 8 shrinks
-764,300, 10 forks, 98.15%, 13/8 shape groups; both `holds` True).
Verdicts:

- **1B, cut at markers: AGREE on the numbers, PREFER a simpler A+.** No
  double count, no estimate: every term is a recorded usage. But the same
  totals come without re-keying windows: at an interval holding a live
  marker, book two exact increments instead of one shrink, a signed
  `compaction` row (-occ prev) and a `window_head` (+occ next). Net sum =
  today's delta, so the reconciliation, R2, D-WINDOW-DIM and
  `query.reconcile`'s file key stay untouched; gross (total minus signed
  rows) = 1B's total exactly (net + sum of pre-compaction occupancy,
  1,054,365). 1B adds only a per-segment `--where window=`; rule on A+
  first. Either way the gross figure is mass that entered, not an
  occupancy: never label it a window size (it is not a summed peak, but
  reads like one), and each compaction head re-counts the system prompt.
- **Spend line "N compactions unpriced": AGREE.** 0 compact-sourced
  `api-request` records shows absence, so name the marker count as the
  population.
- **2, `trigger`: AGREE, one change.** Exact, constant per window, no
  spread. But `resume` is a guess: the probe itself labels the case
  "resume/branch" and `/branch` writes a replayed main file. Name the value
  by the record (`replayed`), not by an intent no field states.
- **3B, split the fork head: AGREE.** inherited = the parent call's
  max-merged occupancy, head - inherited = remainder: an exact subtraction,
  never re-spread. Caveat: "booked through the branch call == occupancy,
  10 of 10" holds by telescoping, so it is construction, not evidence;
  the drill by reference must include the parent's signed rows (or stay
  in its segment) once compaction lands. The inherited-negative-remainder
  check (6 of 10) correctly rules out a feed-forward split.
- **3C rejected: AGREE.** 1.70%, named.
- **4, no content split: AGREE.** Characters and a varying cache
  boundary are estimates; the non-negotiable forbids them.
- **5, two-line headline: AGREE.** Shares stay off signed rows; the
  `compaction` row (A+) or the 3 residual shrinks (1B) sit in the footer.
- **6 ruling table: AGREE under 1B; under A+ only P2 (a second signed
  cause) and the schema rows change.** No measured correction in
  `sa/usage.py` is touched by any option.
