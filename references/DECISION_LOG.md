# session-analyzer v2 — decision log

## Rulings — 2026-09-30

Authority: the owner delegated all design rulings to the lead agent, each
with a claude-opus-5-5 second opinion; both concur on every row unless noted.
Owner directive: "strive for an elegant simple implementation from which
powerful capabilities emerge." Opus independently reviewed the brief and the
ported engine and concurred with the path below.

**D-ENGINE — the ported ranking engine is RETIRED from the build.** RULED.
`scripts/lib/lib_drill.py` and `scripts/sa_schema.py` are deleted from the
tree (they remain in git history and on the `v1-legacy` branch).
Measured basis: the engine is ~85–90% dimension-ranking machinery (four
filters, entropy and eta-squared statistics, partition-signature collapse)
built for v1's many-shape taxonomy; v2 has two fact kinds and about six
dimensions, which are shown side by side rather than ranked. `sa_schema.py`
also cannot import standalone (it depends on two unported v1 modules, R6).
What survives, re-pinned by v2's own tests: never sum a peak; a peak reports
no value at a node; signed mass handled explicitly; fail closed on an unknown
metric; the one residual bucket. What the owner loses: the mutation-tested
score rule and the eta-squared door for drilling a peak. Mitigation: v2's
fact shape stays `{attributes, metrics, locator}` so `lib_drill.py` can be
re-attached if dimensions multiply. `scripts/lib/lib_usage.py` stays
VERBATIM; it carries the measured corrections.

**R1 — carrier of attributed mass.** RULED: option 1, made structural. Every
metric declares its single carrier kind in one `METRICS` table (`spend` ->
call fact, `context_delta` -> increment fact); the query layer reads a metric
only from its carrier kind, so the measured 2.000000x double-count is
impossible by construction.

**R2 — window model.** RULED 2026-09-30: a window is a file.
SUPERSEDED by D-CONTEXT-WINDOW. Full row: `_HISTORY`.

**R3 — misfile-lens re-tag batch.** RECORD-ONLY. Accepted as a record of
what kind of claim each invariant is; no build work follows. Rows 3, 5, 7
and 8 target the retired engine.

**R4 — attribution headline.** RULED: neither option. No attribution rate is
hard-coded anywhere; the tool computes and prints its own exact / ambiguous
/ shrink / window-head rates with their population on every run. The 94.98%
figure stays as a dated note in `DESIGN_BRIEF.md`. The non-negotiable is
reworded to "measured per run".

**R5 — `tool_input_head` normalization.** RULED: option (a) with a mechanical
guard. Bash head = first token after stripping leading `VAR=value`
assignments and `cd <dir>` prefixes ended by `&&`, `;` or `||`; kept only if it matches
`^[A-Za-z0-9_.+-]{1,32}$` and contains no slash, else `other`. File tools ->
extension only. One declared extractor mapping. Rationale: output goes to the
user's own terminal from their own transcripts; the privacy gate governs
tracked files.

**R6 — `sa_schema.py` import surface.** MOOT under D-ENGINE.

**P1 — METRICS single declaration.** RULED, agreed as the ONLY table:
`METRICS` name -> (class, carrier, unit). No ported dicts to reconcile.

**P2 — shrink's home.** MOOT. Shrink is a signed row excluded from share
percentages and always present in the reconciliation footer.

**P3 — residual-aware `top_key`.** MOOT as engine work. Renderer rule: the
headline names the top non-residual row; `ambiguous` is always its own
labelled row.

**P4 — `cause.candidates` to evidence.** RULED, agreed. Candidates are
evidence; `candidate_count` is the drillable scalar.

**P5 — shared parser.** RULED, agreed and strengthened: the parser module IS
the product; probes import it.

**P6 — usage-less calls.** RULED, agreed: a usage-less call emits no fact and
does not advance the carry.

**P7 — keep v1's [OPEN] engine choices.** MOOT (D-ENGINE).

**P8 — schema shape rules.** MOOT (`flatten()` quirks of the retired engine).

**P9 — presets-as-data; computed denominators.** RULED: keep computed
denominators; presets reduce to the two subcommands' defaults.

**D-SPEND-BY-INCREMENT — spend cannot leave the window.** DEFERRED. Call
facts carry only project/session/agent, so `sa spend` cannot say what put the
tokens there; v1 prints a one-line pointer to `sa context` and says that
context shares are not cost shares. No cost-per-increment join in v1. Design
note for the next build: an exact decomposition exists — spread each call's
spend uniformly over the tokens occupying its window at that call, so an
increment's cost is `delta x sum over later calls N of spend(N)/occupancy(N)`,
which telescopes to `sum spend` exactly — but uniform per-token spreading
inside a call is a convention, so it is attribution by model and waits for an
owner ruling. Alternative: price each call's `cache_creation` at its own
tier rate against the increment booked into the interval that call closes;
this rests on the identity `cache_read(N) == cache_read(N-1) +
cache_creation(N-1)`, measured at 92.21% of pairs, so it must be measured
before anyone calls it exact.

**D-USAGE-DOCSTRINGS — `sa/usage.py` docstrings trimmed.** RULED. Each
docstring is now the measured fact with its population and date and nothing
else: no engine cross-references, no history of earlier wordings. The
function bodies are the ported ones unchanged, pinned by digest in
`tests/test_usage.py`; `usage_cache_tier` (never called) is deleted and its
measured fact (exactly one tier per call; tier totals equal
`cache_creation_input_tokens` on 47,419 of 47,419 calls, 0 mixed) moved into
`usage_spend`'s docstring. CLAUDE.md no longer calls the module verbatim.
Same pass, R5 amended: a head value carries its tool (`Bash:pytest`,
`Read:py`), and `&&`/`||` separate like `;`.

**D-AMBIGUOUS-TOOL — an ambiguous increment carries the tool its candidates
share.** RULED 2026-10-01, second-opinion conditions applied. A
`multi_contributor` increment keeps `cause=ambiguous`, its reason, its mass
and its candidate evidence, so the footer's ambiguous total and `--where
cause=ambiguous` are unchanged; it additionally sets `tool` when EVERY
candidate is a tool_result of one tool (a user_text candidate or an
unresolved tool_use leaves it unset) and `head` when, given that, every
candidate's head is the same and not None (`other` is a value). Measured
basis at proposal: 78 of 122 multi_contributor intervals, ~382k of 606k
ambiguous tokens, shared one tool (the judge's run, live corpus, earlier on
2026-10-01); at landing: 79 of 127 (404k of 634k), 36 of them (206k)
sharing the head as well (live local corpus, 33 files, 2026-10-01). What changes: `by tool` and
`by head` answer "which tool" for mass that was pure residual, with the
ambiguity still named on the row. Same pass: a user record batching several
tool_result blocks yields one contributor per block (0 of 808 observed
locally; the one-per-record reading was a silent exact booking to the first
block's tool), and `walk.py`'s local measurements name one population.

**D-AGENT-DIM — a main window carries no `agent`.** RULED 2026-10-01, on a
third judge's rejection of e861c48. The walk had set `agent=main` on every
main window, so `--by agent` summed every session's main window into one
row named like an agent (local corpus, 28 windows: 9 main windows, 985,920
of 3,285,308 context tokens, under one `main`). Now only a subagent's window
carries `agent` (its `agentId`); main windows lack the dimension and land
in the residual row, whose note under `by agent` reads "∅: main windows
(no subagent)". `--where agent=main` therefore selects nothing; main windows
are selected by session or project. Same ruling pass: the headline names
the top SPLITTABLE row (`window_head`, declared unsplittable, keeps its
table row and note but never leads), prints that row's mass, and names the
share's base whenever a residual or signed row makes it less than the total
("top tool=Bash 926,819 (58.6% of 1,587,809 with a tool)"; "(34.9%)" when
the base is the total); and a `--where` value of a closed-vocabulary
dimension (`cause`, `reason`) is validated at parse time, since
`--where cause=bogus` had printed a confident zero.

**R5-BASENAME — the Bash head is the first COMMAND word; a path's
basename.** RULED 2026-10-01. Full row: `_HISTORY`.

**R5-BUILTINS — output-less shell builtins are skipped like keywords.**
RULED 2026-10-01: `heads.BUILTINS` and `heads.SILENT` are skipped with their
arguments up to the next separator; `shlex` tokenizes. Full row: `_HISTORY_2`.

**D-MESSAGE-ID-DEDUP — a call's identity is its `message.id`, deduplicated
across files.** RULED 2026-10-01, on a fifth judge's rejection of ab20da2;
opus agreed with four conditions, all applied. Call identity had been
`message.id` grouped per file, so a message.id already minted in an
earlier-owned file was minted again under a new uuid in another file: a
fork re-mints its parent's last call. Measured basis (live local corpus,
2026-10-01): 1 of ~888 live calls, 15,240 input-side base-token-equivalents, one phantom
call and one phantom interval; it scales with fork fan-out. Now `corpus`
marks an assistant record whose `message.id` was already seen in an
EARLIER-OWNED file as a duplicate exactly like a repeated uuid: the owner
is the first file in the existing owner order (first timestamp, longest
run, path), never bare path order; the record is marked, not dropped, so
the tool_use join index still sees it; and the population line counts both
kinds together ("N duplicate records excluded"). Conditions: within one
file, records sharing a `message.id` are the split constituents of one
call and are still max-merged, and an id-less record is never a key; when
the split constituents are spread across files, the usage is max-merged
over all of them before the call is credited to the owning file
(`SourceFile.usages`, the forest's usage dicts by id). Pinned by a fixture
of a main file and a fork sharing one `message.id` under different uuids:
one call, its metrics equal to the same split within one file, spend
counted once, the population line counting the duplicate; the vacuity
guard gives the fork its own id and gets two calls and double spend.

**D-HEADLINE-SPECIFIC — the headline names the most specific unpinned
table's top row as a share of the total.** RULED 2026-10-01, amended by
judges 7-9: levers per view (`render.View.levers`), walked down whatever
`--by` shows; a pin omits every table and lever it fixes. Spellings
superseded by D-PLAIN-TERMS. Full row: `_HISTORY_2`.

**D-WINDOW-DIM — a window is selectable by its file name.** RULED
2026-10-01. SUPERSEDED in part by D-CONTEXT-WINDOW: the value is the
window key, not the file name. Full row: `_HISTORY`.

## Rulings — 2026-11-15

Owner-approved, amended after review. Each row cites [W], its
measurement (`sa/probe_window_model.py`, `WINDOW PROBE 2026-11-15`), and
[O], its second opinions (an independent opus review, 2026-11-15, and
`PROPOSAL_UX_MODEL.md` §Second opinion). The rows as proposed: that
proposal, mapped in `_HISTORY`.

**D-CONTEXT-WINDOW — a window is one context window.** RULED,
superseding R2. It starts at a session start, a subagent, a fork or a
compaction marker and fills until its file ends or the next compaction;
a marker that ends its file starts none (4 of 9). A file holds one or
more windows and stays internal: dedup and `file:line:uuid` locators are
unchanged. Windows are cut AFTER forest dedup, never by marking records
duplicate; the duplicate count must not change. Identity is (file, start
line: the file's first or the marker's), independent of dedup and
`--since`; `reconcile` and `window_count` key on it. The `window` value
is 8 hex of sha1 over the start record's root-relative `file:line`, for
display and `--where` only: a collision cannot merge windows. The
summarising call is absent (0 of 23,662 api-request records): the
population line counts the unpriced compactions. Measured: 0 windows
span files (605 files); 591 file-windows become 596; shrinks 8 -> 3, 5
becoming starts; exact 84.73% -> 84.75%; spend unchanged; peaks per
window, never summed. [W][O]

**D-START-CAUSE — `start` names what began a window.** RULED. A window
dimension on both kinds, constant per window: `session_start`,
`subagent`, `fork`, `replayed`, `compaction`; fork beats subagent (forks
live under `subagents/`). `start`, not `trigger`: it names the line it
heads; `replayed`, not `resume`: the record, not a guessed intent.
Measured 68 / 513 / 10 / 0 / 5; `replayed` declared, 0 observed. [W][O]

**D-FORK-INHERITED — a fork copies the parent's occupancy at the branch
call.** RULED, changed from the owner's "parent's starting context":
fork head / parent occupancy is 1.006 to 1.034. The copied part,
`inherited`, equals the parent window's occupancy at the branch call and
carries the parent's exact breakdown to that call, signed rows included,
found by reference, never re-minted as facts; the remainder is the
fork's own start. `replayed` windows likewise. [W][O]

**D-INHERITED-ONCE — inherited mass counts once.** RULED. An increment,
cause `inherited`, carrying `context_delta` (one carrier kind); evidence
names the parent window key and the branch call. A window's own
reconciliation includes it; corpus totals exclude it only when the
parent window is in the selected population (query selection decides),
else count it in full: the fallback for the 1 fork inheriting by
reference only. Footer "inherited (counted in parent)", like shrink.
Revives the proposal's rejected 3C, whose objections (the window carried
the tokens; a second total costs reading) fail here: the window keeps
them and one total prints. [W][O]

**D-NO-START-SPLIT — starting context is never split by content.**
RULED. A session start is system prompt, tools, CLAUDE.md and first
message; a subagent's, system prompt and prompt; a compaction's, summary
and re-sent system prompt. No part has its own token count: any split
is an estimate, which is forbidden. [W][O]

**D-HEADLINE-TWO-LINES — starting context, then growth.** RULED. Line 1:
starting context by `start`; line 2: growth by tool -> head; one stated
total; signed rows out of shares. Starting context is labelled mass that
entered, never a window size: compaction starts re-count the system
prompt. [W][O]

**D-OUTPUT-CAP — default `context` output never exceeds its baseline.**
RULED. A test caps it at 46 lines, 3,228 chars: the pre-A1 fixture
baseline at ux-pass HEAD (live: about 71, 5,450), the root string pinned
so the temp path cannot flake it. CORRECTED from 3,214 (ux-pass's own
corpus, 8-char root): the resync corpus, root and projects as `~`. No headroom: "no higher than the
baseline". Doc caps count BYTES, as the pre-commit gates do, stricter
given ∅ ✓ ° (`tests/test_doc_caps.py`). [W][O]

**D-PLAIN-TERMS — user-facing terms explain themselves.** RULED, owner
directive (UX_FEEDBACK 6, 7, 10); [O] an independent opus review,
2026-11-15, agreed with the changes as folded in. Supersedes
D-START-CAUSE's spellings and every older row's. Key and CLI spelling
renamed together: cause `feed_forward` -> `replies`, `window_head` ->
`starting_context`; dimension `start` -> `started_by` (values unchanged),
`head` -> `command` (table "by command / file type"), `agent` ->
`subagent` (spend's lever too); reasons `multi_contributor` ->
`several`, `negative_remainder` -> `less_than_reply`, `no_contributor` ->
`unexplained`. Display only: `context_delta` prints as "context
tokens", increments as `changes`, calls as `calls`, spend's unit as
price-weighted input tokens; `-h` says subcommand and pin. Markers only
on `ambiguous`, `∅`, `window`, `starting_context`. Never more verbose
than pre-A1: default `--limit` 10 -> 5, the cause table always whole,
`∅` and signed rows never hidden; key entries one clause, the full text
in `sa explain`. Unchanged: ambiguous, ∅, window, inherited, replayed,
shrink, exact, tool_result, user_text, spend, drill.

**D-UNASSIGNED — the residual row prints `unassigned*`; `*` footnotes.**
RULED, owner directive, 2026-11-16. A display rename only: the residual
row (was `∅`) means what it meant, never in a share, never hidden. `*`
replaces `°` and marks a glossary term at its first appearance (every
residual row carries it); the key lists exactly the marked terms, one
clause each. The per-table `∅ by X` lines go; `sa explain unassigned`
gives each table's cases. `--where` never took `∅` as a value, nor
takes `unassigned`. Amends D-PLAIN-TERMS' markers; no second opinion yet.
