# session-analyzer v2 — decision log

Superseded rows: `DECISION_LOG_HISTORY.md` (`_HISTORY`). Moved, in force:
`DECISION_LOG_HISTORY_2.md` (D-MEAN-CONTEXT, D-PEAK-BAND, D-MISSING-PARENT). Open work: Filed.

## Sources — folded here, deleted 2026-11-16

Two design proposals, a competition and the owner's feedback, each
mapped to its rulings with its evidence: `git show
41ca90c:references/DECISION_LOG.md`; the files: `git show 048b3ff:references/<file>`.

## Rulings — 2026-09-30

Authority: the owner delegated all design rulings to the lead agent, each
with a claude-opus-5-5 second opinion; both concur on every row unless noted.
Owner directive: "strive for an elegant simple implementation from which
powerful capabilities emerge." Opus independently reviewed the brief and the
ported engine and concurred with the path below.

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
`DECISION_LOG_HISTORY.md`.

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

**D-AGENT-DIM — a main window carries no `subagent`.** RULED 2026-10-01;
the row, verbatim, is in `_HISTORY`.

**D-MESSAGE-ID-DEDUP — a call's identity is its `message.id`, deduplicated
across files.** RULED 2026-10-01 (owner order, marked not dropped,
max-merged across files); the row, verbatim, is in `_HISTORY`.

## Rulings — 2026-11-15

Owner-approved, amended after review. Each row cites [W], its
measurement (`WINDOW PROBE 2026-11-15`; `python3 -m sa.sweep` measures
the same figures), and [O], its second opinions (an independent opus
review, 2026-11-15, and the UX-model proposal's §Second opinion: Sources).

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
re-minted, not none; the mean-context proposal §3.4.) Footer "inherited (counted in parent)", like shrink. The
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
(`tests/test_docs.py`). [W][O]

**D-PLAIN-TERMS, D-UNASSIGNED — display terms.** RULED (owner
directives, 2026-11-15 and -16); the rows, verbatim, are in
`DECISION_LOG_HISTORY.md`. Causes, dimensions and reasons print in
plain words (`replies`, `starting_context`, `started_by`, `command`,
`subagent`, `several`, ...); the residual row prints `unassigned*`, and
`*` marks a glossary term at its first appearance, the key listing
exactly the marked terms. Display only: no figure changes.

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


## Rulings — 2026-11-16, screens (iteration 4)

**D-FOLDED-PARTS-POINTER — a catch-all row whose parts fold names its
pin.** DECIDED (orchestrator, by principle 2; owner to review). When a
composite row's parts fold into `+N more`, the line under it is the
command that pins the row (`python3 -m sa context 'command=no command'`),
whose screen lists every part with its share. Rejected: printing every
part in place (one line either way, but no shares and no way to drill).

**D-SPEND-ONE-ANSWER — the spend screen drops its average-context
line.** DECIDED (orchestrator, by principle 2; owner to review). One
answer a slide: `context` is one command away, and the spend `-v` note
and `-h` already say so. Rejected: a bridge label on the line.

**D-AMBIGUOUS-SAID-ONCE — the checks' ambiguous share prints only where
no cause table on screen prints it.** DECIDED (implementer, by principle
2, one share a figure; owner to review). On an unpinned screen the cause
table's `ambiguous` row is that share with its base; a drill, `by DIM`
or `by change` screen still prints the line; the `!` trigger is
unchanged. With the blank line between the ways deeper and the checks,
it pays for the two pointer lines above within the 46-line budget.
Rejected: raising the budget; cutting table rows.

## Rulings — 2026-11-16, the repo (phase 2)

Each DECIDED (orchestrator, by principle N; owner to review); N is
`UX_PRINCIPLES.md` "The project is a screen too".

| id | decided | by | rejected |
|---|---|---|---|
| D-REFS-LIVE | `references/` holds live docs only; the rest folded (Sources) | 2 | an `archive/` folder: git keeps them |
| D-ONE-HISTORY | one `_HISTORY`; R1-P9 as proposed left to git | 1 | concatenating both (31.6K, over the 20K cap) |
| D-BRIEF-WALK | `DESIGN_BRIEF.md` trimmed to the walk (§2), its gaps | 3 | keeping the retired engine's model |
| D-PLAN-CURRENT | `PUBLISHING_PLAN.md` rewritten to today, kept | 3 | folding into AGENTS.md (at its cap; the clean-room text cites step 1) |
| D-RESIDUAL-SCHEMA | `residual` into `schema` (a dimension's catch-all is vocabulary); dead `residual_note` deleted | 1 | `glossary` (words, not values; over 15K) |
| D-ONE-SWEEP | `sweep_mean` into `sweep`; the proposal's sum-vs-average comparisons and `expand` deleted (their rulings are built); the held identity read from `reconciliation` | 2 | two measuring modules |
| D-KEEP-MODULES | `grammar`, `notes`, `style`, `leaves` stay: one concern each, and any merge is over 15K | 2 | merging past the cap |
| D-TEST-FILES | `test_sweep_mean` into `test_sweep`; `test_docs` (caps, examples); `test_scripts` (screens, agent eval) | 1 | one file per module where that file would pass 15K |
| D-CI | `.github/workflows/ci.yml`: push/PR, Python 3.8, pytest; every corpus is a fixture, so nothing skips | 3 | a Python matrix (3.8 is the floor) |

## Rulings — 2026-11-16, release (phase 3): as phase 2

| id | decided | by | rejected |
|---|---|---|---|
| D-PIP | `pyproject.toml`; no console script: `sa` is acct's, and a 2nd name breaks printed = typed | 1 | an `sa` entry point |
| D-VERSION | `sa.__version__`; manifests match (test); `-h` prints it | 2 | `--version` (retires nothing) |
| D-CHANGELOG | `CHANGELOG.md`, 2.0.0 | 3 | GitHub notes only |
| D-README-RUNS | README leads with install; its commands run on the fixture (test) | 1 | untested |
| D-NEAREST-DECLARED | a closed-vocabulary typo names the nearest value | 1 | the list alone |

## Rulings — 2026-11-16, wrap-up: RULED by the owner 2026-11-16

**D-TWO-PARTS.** A catch-all row names its two largest parts, then
`+ N more X` (the pin under it lists them); never one, however short the
line: `= replies 46,930 + 4 more 43,401` hid starting_context (~36K).

**D-AMBIGUOUS-OF-GROWTH (E5).** Ambiguous is read as a share of growth
before shrink (whole windows), the only thing it can be: a cause pin's
headline adds `= 14.3% of growth (96,746): growth not traced to one
source`; the trigger reads `! 14.3% of growth not traced to one source:
<command>` in place of the checks' share line. Threshold (decided by the
lead): 10% of growth, the old floor's number on the ruled base, meaning
kept: a tenth of what the growth walk attributes is untraced. It fires
more often (the fixture: 31% of a 433-token growth): by design, small
growth is no more traceable.

**D-MAIN-IN-BASE (E6).** `main` is windows like any subagent's, a
population, not a remainder: the subagent table's `= 100%` includes it,
so a share is of all spend and the headline and table agree (an eval
agent had computed 6.7% itself from a 7.6% on screen). `main` prints
above `= 100%` with its share; the check reads `rows + main = spend`.
One rule per dimension (`schema.IN_BASE`), so context's subagent table
follows (lead's call: one `main` behaves one way).

**D-SHRINK-CHECKS (E1).** The checks print shrink in `-v` (the worked
equation) and on trigger (1%+), not on every screen; `AGENTS.md`'s
"always in the checks" amended to match the code.

**D-SPEND-TERMS (E3).** Two call metrics, `input_tokens` (uncached
input) and `cache_read_tokens`, join the cache writes in `METRICS`;
`schema.SPEND_TERMS` pairs each term with its weight from `usage`.
`spend -v` works the price equation under the ✓ (`uncached input ×1.0 +
cache reads ×0.1 + 5m ×1.25 + 1h ×2.0 = spend ✓ the headline's`), a ✓
only where it reconciles; the formula and "weighed in spend" lines go.

**D-PYPI-NAME (E10).** The PyPI distribution is
`claude-code-session-analyzer` (`claude-session-analyzer` is taken);
the module stays `sa`, run as `python3 -m sa`; the plugin keeps its name.

## Filed, not built (re-checked 2026-11-16)

- Project names print encoded (`~-work-proj3`), not as paths.
- No pin shows a parent's breakdown to a branch call (D-INHERITED-HELD).
- `subagent` is a dimension and `subagent_start` a `started_by` value.
- Fork / compaction / replay counts are small (10 / 9 / 0): re-measure
  before pinning; D-INHERITED-HELD's exact expansion is unmeasured since
  D-ONE-SWEEP (`expand`, git 048b3ff).
- Headroom: AGENTS.md, `sa/sweep.py` and this log sit at their caps.
