# Proposal: average context per call

Status: RULED 2026-11-16 as amended (`DECISION_LOG.md`: D-MEAN-CONTEXT,
D-PEAK-BAND, D-PEAK-DEFAULT, D-MISSING-PARENT); the proposal as made
follows. Measurements: `python3 -m sa.sweep` (its average-context lines come
from `sa/sweep_mean.py`), stamp `LOCAL SWEEP 2026-11-16T01:14Z`: this
machine's live corpus, 619 files, 610 windows, 24,517 calls (3,626 in main
windows, 20,891 in subagent windows). Every figure below is from that run
unless it names another population.

## 1. Purpose

Assume inference is free. The context question is then: **is my model's
intelligence dropping from context rot, what causes it, and how do I fix
it?** Rot happens per call: at each call the model reasons over everything
in its window. Spend is a separate question (what did it cost; the cache
decides what is re-counted) and is out of scope here.

Today's context total is the sum of increments, which equals the sum of
each window's final size. It measures tokens that ENTERED. It answers
neither question: it cannot tell 800 windows ending at 30K from 30 windows
ending at 800K, and a tool result read at call 2 of a 300-call window
weighs the same as one read at the last call, though the first sat in
front of the model 300 times.

## 2. Design

### 2.1 Average context per call

The user-facing term is **average context per call**; the internal name
`context_mean`. User text never says "residency", "exposure" or
"token-calls", and never "added per call": it is what calls HELD.

A call's occupancy (`context_tokens`) telescopes to the sum of its
window's increments booked up to and including that call. So weight each
increment by `held`, the number of its window's calls from the call it is
booked at through the window's last call. Then, over any set of whole
windows:

    sum over increments (context_delta x held) == sum over calls (context_tokens)

an exact identity, checked per window like the existing reconciliation,
signed shrink rows and `inherited` included. The average is that sum over
the population's call count. Its breakdown by cause, tool, command or
`started_by` is the weighted rows divided by the SAME call count, so the
rows of one table add up to the average (signed rows included) and the
shares are the weighted shares.

Not additive across populations: the denominator changes. Two sessions'
averages never add or average into the pair's. Proposed refusal, as PEAK
is refused today:

- a new aggregation class `MEAN` in `schema` beside `ADDITIVE` and `PEAK`;
  `context_mean` is a `MEAN` call metric reading `usage.usage_context`;
- `query.total` and `query.group` refuse a `MEAN` metric (a schema-derived
  test iterates every `MEAN` metric, with a vacuity guard that one exists);
  `query.mean(facts, metric)` divides the carrier's sum by the carrier's
  count over one population and is the only reader;
- for the breakdown (option B below), an internal ADDITIVE increment metric
  `context_held` (delta x held), never printed raw: printed only divided by
  its population's call count, and that count is printed beside it;
- a combined population is recomputed from facts, never merged from
  printed figures.

This needs an explicit ruling on "never sum a peak". `context_tokens` is a
PEAK because summing it reads as a size (4,950,327 summed vs 131,612 true
peak). The mean sums it over calls and divides by calls, which is a size
again, the size of the average call. Proposal: keep `context_tokens` PEAK
and its refusals untouched; `context_mean` is a separate declared metric
whose only aggregation is the mean.

### 2.2 Inherited context under the average

A fork's calls really hold the parent's prefix, so under the average it
counts once per fork call. That is not a double count: the parent's calls
and the fork's calls each held it. This amends D-INHERITED-ONCE for this
metric only; the sum metric keeps it.

Default: one labelled, unattributable `inherited` row. Expansion by
reference: `query.through` gives the parent window's facts to the branch
call; each part keeps its cause, tool and command, takes the fork's window
dimensions and the fork's `held`, signed rows included, nested inheritance
expanded recursively. Measured below: cheap and exact.

Parent missing (Claude Code's `cleanupPeriodDays` deleted it, or it is
outside `--since`): force-read the parent's file regardless of `--since`,
counting only the selected calls; when it is gone, fall back to the row.
Measured below: on this corpus the case does not occur, but the fallback
today is worse than a row (§3.4).

### 2.3 The shape line

Median, p90 and max of per-window PEAK `context_tokens`: percentiles of
peaks (nearest rank: a value some window reached), never a sum; the max
names its window key. Main and subagent windows are measured separately
below; the default output prints one line over the population in view.

### 2.4 Deferred: a call-level filter

`--where occupancy>200k` (calls holding more than N tokens) is exact and
answers rot's nonlinearity: a long window may be fine until it is not.
Noted, DEFERRED, not designed. Measured scale: 1,860 of 24,517 calls held
more than 200,000 tokens.

## 3. Measurements

### 3.1 The identity holds

Sum of delta x held: 2,699,788,408. Sum of every call's occupancy:
2,699,788,408. Holds in 610 of 610 windows, signed rows and inherited
included. A one-token change to any increment breaks exactly its window
(pinned: `tests/test_sweep_mean.py`).

Average context per call: **110,119 tokens** over 24,517 calls; main
windows 120,545 over 3,626, subagent windows 108,309 over 20,891.

### 3.2 Rankings: today's sum vs the average

Shares of each table's base (sum: D-INHERITED-ONCE applied; average:
inherited kept as a row). "1>1" is rank by sum > rank by average.

All 610 windows:

| table | top-N kept | moved | max swing | largest moves |
|---|---|---|---|---|
| cause | 5 of 5 | 0 | 2.3 pts | replies 18.6% > 16.3% |
| started_by | 4 of 4 | 0 | 3.7 pts | subagent 86.7% > 83.0%; session_start 11.9% > 15.3% |
| tool (top 10) | 8 of 10 | 4 | 0.7 pts | Bash 89.0% > 89.2%; Read 6.4% > 5.8%; changes only below 0.2% |
| command (top 10) | 9 of 10 | 4 | 5.8 pts | Bash:cat 26.7% > 32.5%; Bash:just 5.5% > 4.0%; Read:py 9 > 7 |

Main windows only (74 windows, top 5):

| table | top-5 kept | moved | max swing | largest moves |
|---|---|---|---|---|
| cause | 5 | 0 | 0.7 pts | stable |
| tool | 4 | 2 | 2.0 pts | Bash 79.3% > 77.3% |
| command | 4 | 3 | 5.7 pts | Bash:git 1 > 2 (22.8% > 17.1%); Bash:cat 2 > 1 (15.8% > 18.5%) |

Per session (the drill a user runs): the largest row differs between sum
and average in **12 of 57** sessions by command, **7 of 65** by cause,
**0 of 45** by tool (sessions with at least two rows).

Plainly: corpus-wide, the rankings barely move. Top causes, tools and
started_by keep their order; the largest swing anywhere is 5.8 points
(Bash:cat). The weighting changes the answer at the drill level: about
one session in five gets a different top command.

### 3.3 Inherited under the average

Inherited mass under the average: 16,300,446 of 2,699,788,408, **0.60%**.
`through` expands 10 of 10 inherited increments; the parts sum exactly to
the inherited mass in 10 of 10. Expanding it moves the cause table by at
most 2.1 points against the sum (vs 2.3 unexpanded): the `inherited` row
dissolves into the parent's causes. Cost: one `through` per inheriting
window (a scan of the parent window's facts), 10 per corpus here.

### 3.4 Missing parents

- Fork and replayed windows: 10 (fork 10, replayed 0); parent read: 10.
  Parent file modified no earlier than the fork's: 10 of 10, all in the
  same session directory. So `--since` (by modification time) never keeps
  a fork while dropping its parent on this corpus, and the default 7-day
  view holds 0 forks (an unstamped run the same hour).
- The one `fork-context-ref` fork carries 1 copied record (its parent's
  last call, re-minted), not a replayed prefix; the other 9 carry 1,616
  copied records between them. D-INHERITED-ONCE's "the 1 fork inheriting
  by reference only" is therefore one copied call, not none.
- Parent absent today (fixture pinned in `tests/test_sweep_mean.py`; and
  an unstamped in-process run excluding each parent file): the copied
  records turn live, the fork walks the parent's calls as its own (live
  examples: 9 > 10 calls, 12 > 20 calls) and a replaying subagent is
  labelled `subagent`, not `fork`. Under the sum the total telescopes
  either way; under the average those phantom calls enter the
  denominator. That is why the proposal force-reads the parent.

### 3.5 Shape of the windows

Per-window peak `context_tokens`, nearest rank:

| windows | count | median | p90 | max |
|---|---|---|---|---|
| all | 610 | 97,798 | 185,924 | 375,458 |
| main | 74 | 97,861 | 209,567 | 288,538 |
| subagent | 536 | 97,747 | 180,655 | 375,458 |

The average per call (110,119) exceeds the median window peak (97,798):
long windows hold most calls. The sum total cannot show this.

## 4. Options

- **A. Level and shape.** The average per call and the shape line, read
  from call facts alone (`context_mean`, `MEAN`); no new facts, no weights,
  tables unchanged. About 40 lines plus tests. Answers "is it rotting":
  how much a typical call holds, and how bad the worst windows are.
- **B. A plus the weighted breakdown.** `context_held` booked per increment
  by `walk.forest` after cutting (held needs the window's call count);
  tables and headline levers read it; inherited amended per §2.2 with the
  row. Touches schema, walk, query, headline, tables, glossary, the
  reconciliation footer and the README examples. Answers "what causes it"
  in the call-weighted sense.
- **C. B plus expansion of `inherited` by `through`.** Cheap and exact,
  0.60% of the average here; meaningful only with B.
- **D. Missing parent: force-read.** Independent of A to C; today it
  prevents phantom calls in the average (option A's denominator too).
  Unobserved on this corpus.
- **E. Build nothing.** Keep today's total.

Recommendation: **A, then D**. Defer B and C: corpus-wide they move no top
ranking and at most 5.8 points; they earn their cost only if the owner
values the per-session change (12 of 57 top commands). Re-measure with
`python3 -m sa.sweep` before ruling on B.

### Mock: default `context` on the fixture corpus (option A)

The `largest single-call context` line is replaced by the average line
and the shape line; the key gains one entry. 44 lines, 2,370 chars,
within D-OUTPUT-CAP's 46 / 3,228 (today: 42 / 2,221). Key alignment would
re-pad; the mock does not.

```
context tokens: 4,560 = the 3 windows' final sizes summed (% of the 4,860 added)
  starting_context* 3,000 (61.7%) at window start: session_start 2,000, fork 1,000
  growth 1,860 (38.3%): tool=Bash 750 (15.4%), command=Bash:pytest 750 (100.0% of Bash, 15.4%)
average context per call* 1,376 tokens, over 21 calls in 3 windows
window peaks: median 1,520, p90 1,520, max 1,520 (window=aadeccf6)
→ next: add --where tool=Bash

by cause          context tokens  changes  share of 4,860 added
...  (tables unchanged)

* explained below · more on any of them: python3 -m sa explain window
  window*           = one context window, from its start to its file's end or the next compaction
  starting_context* = already in the first call, not assigned to any tool
  average context per call* = what a call held, averaged over these calls; never summed
  ambiguous*        = growth with no one contributor, left undivided
  unassigned*       = not attributable to this table's dimension; excluded from share
```

Option B on the same corpus (excerpt; headline leads with the average,
`context tokens` moves to the footer). Rows add to the average; shares are
of the 1,433 held before shrink; rounding per row:

```
average context per call*: 1,376 tokens over 21 calls in 3 windows (% of 1,433 held)
  starting_context* 1,000 (69.8%) at window start: session_start 667, fork 333
  growth 433 (30.2%): tool=Bash 214 (15.0%), command=Bash:pytest 214 (100.0% of Bash, 15.0%)
window peaks: median 1,520, p90 1,520, max 1,520 (window=aadeccf6)

by cause          avg per call  changes  share of 1,433 held
starting_context         1,000        3   69.8%
tool_result                214        3   15.0%
ambiguous*                 135        9    9.4%
replies                     60       12    4.2%
user_text                   24        3    1.7%
shrink (signed)            -57        3       -
= average                1,376       33  ✓ = mean call occupancy
```

## 5. Rulings added or amended (all PROPOSED)

| row | kind | text |
|---|---|---|
| D-MEAN-CONTEXT | new | Average context per call (`context_mean`) is the population's summed call occupancy over its call count: what calls held. Printed beside its call count; never "added per call". |
| D-MEAN-NOT-ADDITIVE | new | `MEAN` is an aggregation class; `query.total` and `query.group` refuse it; `query.mean` over one population is its only reader; populations are recomputed from facts, never merged. |
| D-PEAK-NOT-MEAN | amends "never sum a peak" | `context_tokens` stays PEAK with every refusal; the mean is a separate metric reading the same field. |
| D-HELD-WEIGHT | new, option B only | An increment is held by its window's calls from its booking call to the last; `sum(delta x held) == sum(call occupancy)` per window is a reconciliation, MISMATCH exits 1. |
| D-INHERITED-HELD | amends D-INHERITED-ONCE, option B only | Under the average, inherited counts once per fork call (it was held there); one `inherited` row, expanded by `through` under option C. The sum keeps D-INHERITED-ONCE. |
| D-MISSING-PARENT | new | A fork or replayed window whose parent file exists is read with its parent regardless of `--since`, the parent's calls not selected; a deleted parent leaves the row. |
| D-PEAK-SHAPE | amends D-HEADLINE-TWO-LINES (the line after) | The `largest single-call context` line becomes median / p90 / max of window peaks, max naming its window. |
| D-OCCUPANCY-FILTER | DEFERRED | A call-level `--where occupancy>N`; exact; not designed. |

D-OUTPUT-CAP is unchanged: option A fits (44 / 2,370).

## 6. Build order

1. `schema`: `MEAN`, `context_mean`; `query.mean`; refusals and their
   schema-derived tests (D-MEAN-CONTEXT, D-MEAN-NOT-ADDITIVE, D-PEAK-NOT-MEAN).
2. `headline`: the average line and the shape line replace `_peaks`;
   glossary entry; resync README and SKILL examples; cap test unchanged.
3. `corpus`/`cli`: force-read missing parents (D-MISSING-PARENT), with a
   fixture of a fork outside `--since`.
4. Re-measure B with the sweep; only on an owner ruling: `context_held` in
   `walk.forest`, the held reconciliation, tables by average, inherited per
   D-INHERITED-HELD; then C.

## 7. ROI verdict

- **A is worth building.** The level is new information the sum cannot
  give (110,119 tokens per call here; main 120,545), the shape line shows
  the tail (p90 185,924, max 375,458), and it costs no new facts.
- **B is not worth building now.** Corpus-wide rankings barely move (no
  top cause, tool or started_by changes rank; max swing 5.8 points). The
  only material change is at the drill: 12 of 57 sessions' top command.
  If the owner judges that worth a second accounting through every table,
  build B; otherwise do not.
- **C is cheap and exact but small** (0.60% of the average); only with B.
- **D is cheap insurance** for a case not observed here.

## 8. Drafts (not applied)

README purpose (replaces the 6-line opening paragraph under the title;
README 4,495 bytes today, about 4,560 after, cap 5,000):

> Is context rot making your model dumber, what causes it, and how do you
> fix it? Every call reasons over all of its window: `sa context` shows how
> much a call holds on average, how full your fullest windows get, and what
> put the tokens there. `sa spend` asks what it cost. From the transcripts
> under `~/.claude/projects`; every figure names its population. A Claude
> Code plugin or plain `python3 -m sa`; stdlib, Python 3.8+.

CLAUDE.md pointer (one line, under "Pointers, never copies"):

> - `references/PROPOSAL_MEAN_CONTEXT.md`: average context per call (rot is per call); PROPOSED, option A recommended.

## 9. Friction and debt found

- D-PLAIN-TERMS is cited as a ruling but lives only in
  `DECISION_LOG_HISTORY_2.md`; `DECISION_LOG.md` has no row for it or for
  D-UNASSIGNED.
- D-INHERITED-ONCE's "inheriting by reference only" is inexact: that fork
  carries one copied call (§3.4).
- A fork read without its parent today walks copied calls as its own and
  loses its `fork` label (§3.4); harmless to the sum, wrong for any
  per-call figure, including spend's call count.
- `python3 -m sa.sweep` now takes about 35 s on this corpus (it walks the
  forest several times for the per-session comparison).

## Second opinion

Review: `LOCAL SWEEP 2026-11-16T01:21Z` (612 windows, 24,563 calls;
the corpus grew): identity, inherited and peaks reproduce; average
110,108; top command differs in 11 of 57 sessions (was 12).

1. **Identity: AGREE-WITH-CHANGE.** It holds by construction: `walk`
   books each call's occupancy as the running sum of its window's
   increments (0 calls differ), so the identity is algebra. It
   tests `held()`, not the corpus. `held()` is right (replies, shrink,
   compaction cuts, inherited). Call it a test, not evidence.
2. **Rankings: AGREE to defer B, for another reason.** The population
   matters. 8 of the 11 flips were within 5.7 pts under
   the sum (12 of 57 sessions are within 5): near-ties. Today's sum over
   the 49 windows peaking above 200,000 (5,794 calls) moves causes 17.7
   pts (starting_context 34.1% > 16.4%; tool_result first, 37.0%; replies
   26.6%); weighting by the calls above 200,000 agrees (tool_result 41.9%,
   starting_context 15.6%). Average vs sum: 2.3 pts. By command all four
   keep Bash:cat first. §4 "move no top ranking" is false for main windows
   by command (Bash:git 1>2). Cheaper than B: a window filter by peak,
   additive, reconciliation untouched.
3. **Purpose: AGREE-WITH-CHANGE.** A gives the level, not the cause or
   the fix. The shape line does not solve 800 at 30K vs 30 at 800K:
   window percentiles count windows, so the 30 (3.6%) sit above p90 and
   only the max shows them. Every window's last call is its peak (612 of
   612), so the line is percentiles of the final sizes the total already
   sums. Count calls instead: 1,860 of 24,563 calls (7.6%) held over
   200,000; call median / p90 96,628 / 185,578. Cause: item 2's filter.
4. **MEAN vs peak: AGREE-WITH-CHANGE.** Sound: the sum is never printed;
   the mean is a size. But `query.total` does not refuse PEAK today (only
   `group`): add it for both. A second metric on the same field mints a
   copy on every call fact; simpler: `query.mean(facts, context_tokens)`
   over one population. Unenforced on this branch.
5. **Missing parent: AGREE-WITH-CHANGE.** Parents are never older than
   their forks (10 of 10), so `--since` and age-based cleanup drop the
   fork first: insurance only. Gap: with the parent deleted no `inherited`
   row exists today; the copies cannot be told from live records (dedup
   is cross-file), so "a deleted parent leaves the row" needs a copy
   detector or is unbuildable. A force-read file must show on `read:`.
   The D-INHERITED-ONCE wording fix (one copied call): AGREE.
6. **Output: AGREE-WITH-CHANGE.** The mock's figures reproduce
   and fit 44 / 2,370. Vocabulary fine; `average context per call*` is
   the first multi-word key term. README draft 4,561 bytes, plain, but
   promises a fix A does not give. The CLAUDE.md pointer FAILS its cap
   (6,987 + 117 = 7,104 > 7,000); its purpose line has no draft.
7. **Omitted:** one average blends main (120,554) and subagent windows
   (108,295; 85% calls).

Recommendation: A, the call count over a threshold in place of the
window-peak line; then a window filter by peak; defer B, C; D only with a
copy detector.
