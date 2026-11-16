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

**D-SPEND-BY-INCREMENT — spend cannot leave the window.** DEFERRED. Call
facts carry only window dimensions, so `sa spend` cannot say what put the
tokens there; it prints a one-line pointer to `sa context` and says that
context shares are not cost shares. No cost-per-increment join. Design
note: an exact decomposition exists — spread each call's
spend uniformly over the tokens occupying its window at that call, so an
increment's cost is `delta x sum over later calls N of spend(N)/occupancy(N)`,
which telescopes to `sum spend` exactly — but uniform per-token spreading
inside a call is a convention, so it is attribution by model and waits for an
owner ruling. Alternative: price each call's `cache_creation` at its own
tier rate against the increment booked into the interval that call closes;
this rests on the identity `cache_read(N) == cache_read(N-1) +
cache_creation(N-1)`, measured at 92.21% of pairs, so it must be measured
before anyone calls it exact.

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
else count it in full: the fallback for the 1 fork inheriting by
reference only. Footer "inherited (counted in parent)", like shrink. The
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
never a window size: compaction starts re-count the system prompt. [W][O]

**D-OUTPUT-CAP — default `context` output never exceeds its baseline.**
RULED. A test caps it at 46 lines, 3,228 chars: the fixture baseline at
ux-pass HEAD, on the resync corpus with root and projects as `~`. No
headroom. Doc caps count BYTES, as the pre-commit gates do
(`tests/test_doc_caps.py`). [W][O]
