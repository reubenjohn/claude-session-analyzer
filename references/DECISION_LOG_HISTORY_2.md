# session-analyzer v2 — decision log history 2: rows moved verbatim out of
`DECISION_LOG.md` once `DECISION_LOG_HISTORY.md` reached its cap. Still in
force unless a later ruling amends them.

## Rulings — 2026-11-16 (moved 2026-11-16, verbatim)

Owner-approved. [M]: the mean-context proposal (Sources), measured by
`python3 -m sa.sweep` (`LOCAL SWEEP 2026-11-16T01:14Z`: 610 windows,
24,517 calls; the fork marks `LOCAL SWEEP 2026-11-16T02:29Z`: 614
windows, 24,771 calls). [O]: its `## Second opinion` (an independent
opus review, `LOCAL SWEEP 2026-11-16T01:21Z`). The purpose they serve:
were inference free, is context rotting the model's intelligence, what
causes it, how to fix it; the path is `sa context` -> `--where
peak=200K+` -> `--by session` -> `--where command=... --by fact`.

**D-MEAN-CONTEXT — the average context per call.** RULED. What a call
held (its `context_tokens`), averaged over the calls of the whole
windows in view, printed with that population: `average context per
call* N tokens, over C calls in W windows`. It replaces the `largest
single-call context` line; never phrased "added per call". A FUNCTION,
`query.mean(facts, metric)`, over the existing PEAK metric, not a new
metric on every call fact and not a `MEAN` class (the proposal's
`context_mean` and D-PEAK-NOT-MEAN are not built) [O]. A mean is one
population's: never summed nor merged; a combined population is
recomputed from its facts. (Amended by D-PER-CALL: it is the headline's
first line, and every context figure a part of it.) `query.total` refuses a PEAK metric as
`query.group` did, closing the hole [O] found. Measured: 110,119 tokens
over 24,517 calls; main 120,545, subagent 108,309 [M][O]. [O] second
opinion 2026-11-16: AGREE-WITH-CHANGE, applied.

**D-PEAK-BAND — `peak`, a window dimension.** RULED. On both kinds,
constant per window: the band of the window's largest call
`context_tokens` over its live calls. Measured, not built, to hold under
`--since`: a dropped parent makes a fork's copies live, each no larger
than the branch call its first own call exceeds (LOCAL SWEEP
2026-11-16T02:53Z: 0 of 43 windows of a 7d read differ,
`sweep.since_bands`). Declared, ASCII, shell-safe: `0-50K`, `50-100K`,
`100-200K`, `200K+` (K = 1,000; each band includes its lower edge). A
label, never a summed peak. `--by peak` and `--where peak=200K+` use the
existing grammar; `spend --where peak=` too. Basis: a window filter by
peak moves the cause table 17.7 points where the call-weighted
breakdown moves it 2.3: 49 windows peaking above 200,000 hold 5,794
calls, tool_result first (37.0%), starting_context 34.1% -> 16.4% [O]. Rows print in
the dimension's declared order, fullest first, in every view
(`schema.ORDERED`). [O] second opinion 2026-11-16: AGREE-WITH-CHANGE, applied.

**D-MISSING-PARENT — a fork without its parent is counted, not
fixed.** RULED, amended from the proposal (force-reading the parent is
not built: a deleted parent cannot be read, and the copies cannot be
told from live records without a detector [O]). A fork says so in its
own file: a `fork-context-ref` record, or an `api-request` whose
`querySource` is `agent:builtin:fork` (`windows.marked_fork`); either
labels the window `fork` with its parent absent. A fork window in view
with no `inherited` change prints a scope line per reason
(`query.orphan_forks`), each ending `: its copy counts as its own`: no
main window of its parent session (the ref's, else its own) was read,
`N fork(s) whose parent is missing`; one was, but not the branch call,
`... whose branch call is not found in its parent` (said, not hidden:
the copy then sits in the fork's starting context). An unmarked fork (a
subagent replaying a prefix only) whose parent is missing reads as
`subagent_start`, unwarned. Measured: 10 of 10
fork windows marked (api-request 9, ref 1), 10 of 10 with their parent
found, so 0 warned [M]. A replay with its parent absent is known only by
that parent: it reads as a session start, unwarned (`sa explain
replayed`). [O] second opinion 2026-11-16: AGREE-WITH-CHANGE, applied.

**Deferred.** D-HELD-WEIGHT (option B; built by the owner's ruling
D-PER-CALL below); D-INHERITED-HELD
(option C: expanding `inherited` by reference in tables, 0.60% of the
held sum [M]); copy detection for a parentless fork; D-OCCUPANCY-FILTER
(a call-level `--where`); D-PEAK-SHAPE (window-peak percentiles: they
are percentiles of the final sizes the total already sums [O]).
