# session-analyzer v2 — decision log

## Rulings — 2026-09-30

Authority: the owner delegated all design rulings to the lead agent, each
with a claude-opus-5-5 second opinion; both concur on every row unless noted.
Owner directive: "strive for an elegant simple implementation from which
powerful capabilities emerge." Opus independently reviewed the brief and the
ported engine and concurred with the path below.

**D-ENGINE — the ported ranking engine is RETIRED from the build.** RULED.
`scripts/lib/lib_drill.py` and `scripts/sa_schema.py` are not in the tree
(they remain in git history and on the `v1-legacy` branch).
Measured basis: the engine is ~85–90% dimension-ranking machinery (four
filters, entropy and eta-squared statistics, partition-signature collapse)
built for v1's many-shape taxonomy; v2 has two fact kinds and about six
dimensions, which are shown side by side rather than ranked. `sa_schema.py`
also cannot import standalone (it depends on two unported v1 modules).
What survives, pinned by v2's own tests: never sum a peak; a peak reports
no value at a node; signed mass handled explicitly; fail closed on an unknown
metric; the one residual bucket. What the owner loses: the mutation-tested
score rule and the eta-squared door for drilling a peak. Mitigation: v2's
fact shape stays `{attributes, metrics, locator}` so `lib_drill.py` can be
re-attached if dimensions multiply. `sa/usage.py` keeps the ported function
bodies; it carries the measured corrections (D-USAGE-DOCSTRINGS).

**R1 — carrier of attributed mass.** RULED: option 1, made structural. Every
metric declares its single carrier kind in one `METRICS` table (`spend` ->
call fact, `context_delta` -> increment fact); the query layer reads a metric
only from its carrier kind, so the measured 2.000000x double-count is
impossible by construction.

**R4 — attribution headline.** RULED: neither option. No attribution rate is
hard-coded anywhere; the tool computes and prints its own exact / ambiguous
/ shrink rates with their population on every run. The 94.98% figure stays
as a dated note in `DESIGN_BRIEF.md`.

**R5 — the `command` of a tool call.** RULED: `<tool>:<summary>`, one
declared extractor (`heads.py`, cases in `tests/test_heads.py`). Bash: the
first COMMAND word as a basename, past assignments, separators, keywords,
wrappers and the output-less `heads.BUILTINS` and `heads.SILENT` with
their arguments; `shlex` tokenizes. File tools: the extension. Kept only
if it matches `heads.HEAD_SHAPE` (no slash), else `other`; never a path.
Rationale: output goes to the user's own terminal from their own
transcripts; the privacy gate governs tracked files.

R3, R6, P2, P3, P7 and P8 are record-only or moot under D-ENGINE; the rows
as proposed are in `_HISTORY`.

**P1 — METRICS single declaration.** RULED, agreed as the ONLY table:
`METRICS` name -> (class, carrier, unit). No ported dicts to reconcile.

**P4 — `cause.candidates` to evidence.** RULED, agreed. Candidates are
evidence; `candidate_count` is the drillable scalar.

**P5 — shared parser.** RULED, agreed and strengthened: the parser module IS
the product; measuring modules import it.

**P6 — usage-less calls.** RULED, agreed: a usage-less call emits no fact and
does not advance the carry.

**P9 — presets-as-data; computed denominators.** RULED: keep computed
denominators; presets reduce to the two subcommands' defaults.

**D-SPEND-BY-INCREMENT — spend cannot leave the window.** DEFERRED:
no cost-per-increment join; the row, with its design note, is in
`DECISION_LOG_HISTORY_2.md`.

**D-USAGE-DOCSTRINGS — `sa/usage.py` docstrings are the measured facts.**
RULED. Each docstring is the measured fact with its population and date
and nothing else. The function bodies are the ported ones unchanged,
pinned by digest in `tests/test_usage.py`; `usage_cache_tier` (never
called) is deleted and its measured fact (exactly one tier per call; tier
totals equal `cache_creation_input_tokens` on 47,419 of 47,419 calls, 0
mixed) lives in `usage_spend`'s docstring.

**D-AMBIGUOUS-TOOL — an ambiguous increment carries the tool its candidates
share.** RULED 2026-10-01, second-opinion conditions applied. A `several`
increment keeps `cause=ambiguous`, its reason, its mass and its candidate
evidence, so the footer's ambiguous total and `--where cause=ambiguous`
are unaffected; it also sets `tool` when EVERY candidate is a tool_result
of one tool (a user_text candidate or an unresolved tool_use leaves it
unset) and `command` when, given that, every candidate's command is the
same and not None (`other` is a value). Measured basis (live local corpus,
33 files, 2026-10-01): 79 of 127 such intervals (404k of 634k ambiguous
tokens) share one tool, 36 of them (206k) the command as well. A user
record batching several tool_result blocks yields one contributor per
block (0 of 808 observed locally).

**D-AGENT-DIM — a main window carries no `subagent`.** RULED 2026-10-01.
Only a subagent's window carries `subagent` (its `agentId`); main windows
lack the dimension and land in the residual row, so `--by subagent` never
sums every session's main window into one row named like an agent
(measured: 9 main windows, 985,920 of 3,285,308 context tokens, would
have formed one). Main windows are selected by session, project or
window. A `--where` value of a closed-vocabulary dimension (`cause`,
`reason`, `started_by`) is validated at parse time.

**D-MESSAGE-ID-DEDUP — a call's identity is its `message.id`, deduplicated
across files.** RULED 2026-10-01; opus agreed with four conditions, all
applied. A fork re-mints its parent's last call under a new uuid in
another file. `corpus` marks an assistant record whose `message.id` was
already seen in an EARLIER-OWNED file as a duplicate exactly like a
repeated uuid: the owner is the first file in owner order (first
timestamp, longest run, path), never bare path order; the record is
marked, not dropped, so the tool_use join index still sees it; and the
population line counts both kinds together. Within one file, records
sharing a `message.id` are the split constituents of one call, max-merged;
an id-less record is never a key; constituents spread across files are
max-merged over all of them before the call is credited to the owning
file (`SourceFile.usages`). Measured basis (live local corpus,
2026-10-01): 1 of ~888 live calls, 15,240 input-side base-token
equivalents; it scales with fork fan-out. Pinned by a fixture of a main
file and a fork sharing one `message.id` under different uuids.

## Rulings — 2026-11-15

Owner-approved, amended after review. Each row cites [W], its
measurement (`WINDOW PROBE 2026-11-15`; `python3 -m sa.sweep` measures
the same figures), and [O], its second opinions (an independent opus
review, 2026-11-15, and `PROPOSAL_UX_MODEL.md` §Second opinion). The rows
as proposed: that proposal, mapped in `_HISTORY`.

**D-CONTEXT-WINDOW — a window is one context window.** RULED. It starts
at a session start, a subagent, a fork, a replay or a compaction marker
and fills until its file ends or the next compaction; a marker that ends
its file starts none (4 of 9). A file holds one or more windows and stays
internal: dedup and `file:line:uuid` locators are per file. Windows are
cut AFTER forest dedup, never by marking records duplicate; the duplicate
count must not change. Identity is (file, start line: the file's first or
the marker's), independent of dedup and `--since`; `reconcile` and
`window_count` key on it. The `window` value is 8 hex of sha1 over the
start record's root-relative `file:line`, for display and `--where` only,
never a default table: a collision cannot merge windows. The summarising
call is absent (0 of 23,662 api-request records): the population line
counts the unpriced compactions. Measured: 0 windows span files (605
files); 596 windows from 591 files; exact 84.75%; spend unaffected; peaks
per window, never summed. [W][O]

**D-START-CAUSE — `started_by` names what began a window.** RULED. A
window dimension on both kinds, constant per window: `session_start`,
`subagent`, `fork`, `replayed`, `compaction`; fork beats subagent (forks
live under `subagents/`). `replayed` names the record, not a guessed
intent. Measured 68 / 513 / 10 / 0 / 5; `replayed` declared, 0 observed.
[W][O]

**D-FORK-INHERITED — a fork copies the parent's occupancy at the branch
call.** RULED: fork head / parent occupancy is 1.006 to 1.034. The copied
part, `inherited`, equals the parent window's occupancy at the branch
call and carries the parent's exact breakdown to that call, signed rows
included, found by reference, never re-minted as facts; the remainder is
the fork's own start. `replayed` windows likewise. [W][O]

**D-INHERITED-ONCE — inherited mass counts once.** RULED. An increment,
cause `inherited`, carrying `context_delta` (one carrier kind); evidence
names the parent window key and the branch call. A window's own
reconciliation includes it; corpus totals exclude it only when the
parent window is in the selected population (query selection decides),
else count it in full. (Amended 2026-11-16: the one fork with a
`fork-context-ref` carries one copied call, its parent's last,
re-minted, not none; `PROPOSAL_MEAN_CONTEXT.md` §3.4.) Footer "inherited (counted in parent)", like shrink. The
window keeps the tokens and one total prints. [W][O]

**D-NO-START-SPLIT — starting context is never split by content.**
RULED. A session start is system prompt, tools, CLAUDE.md and first
message; a subagent's, system prompt and prompt; a compaction's, summary
and re-sent system prompt. No part has its own token count: any split
is an estimate, which is forbidden. [W][O]

**D-HEADLINE-TWO-LINES — starting context, then growth.** RULED. One
stated total; line 1: `starting_context` by `started_by`; line 2: growth
walked down `render.View.levers` whatever `--by` shows, never a cause or
window row; a `--where` pin omits every table and lever it fixes; signed
rows out of shares. Starting context is labelled mass that entered,
never a window size: compaction starts re-count the system prompt.
(Amended by D-PER-CALL: the stated total is the average context per
call, every line in its unit. [O] second opinion 2026-11-16 on the
amendment: AGREE.) [W][O]

**D-OUTPUT-CAP — default `context` output never exceeds its baseline.**
RULED. A test caps it at 46 lines, 3,228 chars: the fixture baseline at
ux-pass HEAD, on the resync corpus with root and projects as `~`. No
headroom. Doc caps count BYTES, as the pre-commit gates do
(`tests/test_doc_caps.py`). [W][O]

**D-PLAIN-TERMS, D-UNASSIGNED — display terms.** RULED (owner
directives, 2026-11-15 and -16); the rows, verbatim, are in
`DECISION_LOG_HISTORY_2.md`. Causes, dimensions and reasons print in
plain words (`replies`, `starting_context`, `started_by`, `command`,
`subagent`, `several`, ...); the residual row prints `unassigned*`, and
`*` marks a glossary term at its first appearance, the key listing
exactly the marked terms. Display only: no figure changes.

## Rulings — 2026-11-16

Owner-approved. [M]: `PROPOSAL_MEAN_CONTEXT.md`, measured by
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
`sweep_mean.since_bands`). Declared, ASCII, shell-safe: `0-50K`, `50-100K`,
`100-200K`, `200K+` (K = 1,000; each band includes its lower edge). A
label, never a summed peak. `--by peak` and `--where peak=200K+` use the
existing grammar; `spend --where peak=` too. Basis: a window filter by
peak moves the cause table 17.7 points where the call-weighted
breakdown moves it 2.3: 49 windows peaking above 200,000 hold 5,794
calls, tool_result first (37.0%), starting_context 34.1% -> 16.4% [O]. Rows print in
the dimension's declared order, fullest first, in every view
(`schema.ORDERED`). [O] second opinion 2026-11-16: AGREE-WITH-CHANGE, applied.

**D-PEAK-DEFAULT — the default output leads with the band.** RULED.
`context`'s default tables gain `by peak` (context tokens, windows,
calls, share; under a drill, whole windows with a matching change),
before `session` (the path's order). A default table, lever or hint
opens only when the windows in view carry more than one value, pinned
or not: one band prints no `by peak`. The hint follows the headline's
own walk (tool, then command, then `by change`): amended iter2, display
only, since a band the default screen no longer prints did not motivate
it (audit F4); `by peak` stays a table away. Tables that repeat one
table row for row share its one relabel line (`by session, project:`),
which keeps the fixture output at 46 lines / 2,872 chars, D-OUTPUT-CAP
unchanged. The "calls holding over 200K" figure (1,860 of 24,563 [O])
is not printed: it counts calls, not windows, so it has no pin to act
on (the call filter is deferred, D-OCCUPANCY-FILTER), the 200K+ row's
calls column already sizes the exposure, and the cap has no room; it
stays a sweep line. [O] second opinion 2026-11-16: AGREE-WITH-CHANGE, applied.

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

## Rulings — 2026-11-16, per call

**D-PER-CALL — every context figure is per call.** RULED by the owner;
amends D-HEADLINE-TWO-LINES and D-MEAN-CONTEXT, builds D-HELD-WEIGHT.
Why: the purpose is rot, and a report whose one per-call figure sat
above tables in summed tokens was judged incomprehensible by two cold
readers and the owner. Each increment books `context_held`, its delta
times `walk.held` (its window's calls from the one it is booked at
through the last); a set of changes is Σ held over the calls of the
whole windows in view (window pins narrow them, a drill keeps them). The
headline opens `average context per call* N tokens, over C calls in W
windows` (a drill adds `, from N changes where … in M of them`);
starting context, growth, the lever walk, every context table's `part of
avg` column (its rows add up to the average; the cause table alone, and
only with no drill, closes `= average N ✓ = mean call size`) and `--by
fact` (its part, then its raw delta) are in that unit. Shares are of the
average before shrink: the signed row stays out of them, so the base is
the average itself only without shrink. Every window-dimension table
adds windows, calls and each row's own `avg call` (`query.mean` over its
calls: what its pin's headline prints; never summed; under a drill, of
the whole windows with a matching change). `PER_CALL` is an aggregation
class: `query.per` refuses a sum or a table without one population's
calls, and any other metric given calls; a per-call figure is never
summed or merged across populations. A fork's calls hold its `inherited`
copy: a row whenever such a fork is in view (the summed selection keeps
D-INHERITED-ONCE). The summed total moves to the checks, against the
final window sizes, beside Σ delta×held = Σ call occupancy, checked per
window (`reconciliation`, MISMATCH exit 1). Spend unchanged. [M] LOCAL
SWEEP 2026-11-16T08:30Z: holds in 619 of 619 windows, 2,787,153,745 both
sides, 25,066 calls, average 111,193; `sa context --since all` holds,
exit 0. [O] second opinion 2026-11-16: AGREE-WITH-CHANGE, applied: the
part column reads `part of avg`, own `avg call`, the drill note, the
checks in two lines with `tokens × calls`, the -h path = the hint chain.

**D-NO-VERDICT — no numeric "is this hurting you" verdict.** RULED by
the owner. No rot threshold has been measured, so any cut-off would be
an estimate: no figure is labelled good or bad. `sa explain peak` says
in plain words, with no number, that larger windows are where models
are most likely to lose track, so start with the fullest band. [O]
second opinion 2026-11-16: AGREE.

**D-UX-PRINCIPLES — three principles bind every screen.** RULED by the
owner 2026-11-16: learnable, legible, trustworthy
(`references/UX_PRINCIPLES.md`). Rules are instances; one met by breaking
a principle fails. Per-screen budgets are hard, ratcheting gates.
