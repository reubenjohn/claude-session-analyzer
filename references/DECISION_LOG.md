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
RULED 2026-10-01, closing R5-BASENAME's logged gap: a loop body that opens
with a label (`for f in …; do echo "== $f"; cat "$f"; done`) had yielded
`Bash:echo`, although `echo` never produces the tokens the increment books.
Measured basis, live corpus (40 files, 32 windows, 2026-10-01, `--where
tool=Bash --by head`): before, `Bash:echo` carried 167,401 tokens over 23
increments (the #2 Bash head) and `Bash:cat` 238,494 over 37; after,
`Bash:echo` and `Bash:printf` (2,440) carry nothing and `Bash:cat` is
448,448 over 57 (48.0% of 935,044 with a head). One declared tuple in
`heads.py`, `BUILTINS = ("echo", "printf", "true", "false", "set",
"export", "unset", "shift")`: a builtin is skipped with its own arguments up
to the next separator, so the head is the next command word (`echo hi && pytest` ->
`Bash:pytest`, `printf '%s' x | sort` -> `Bash:sort`) and a command that is
only builtins yields `Bash:other`. The interpreter-plus-script gap
(`python3 scripts/x.py` -> `Bash:python3`) stays logged, not widened. Same
pass: a table's mass column is headed by the metric name
(`context_delta`, `spend`) rather than its unit, which the headline already
states once; spend's 33-character unit had overflowed the column and
misaligned `by agent`. Extended 2026-10-01 (fourteenth judge): the
principle is negligible output, not the builtin list, so a second declared
tuple `SILENT = ("mkdir", "touch", "mv", "cp", "rm", "chmod", "sleep",
"ln")` is skipped the same way (`mkdir -p x && cat > f <<EOF` ->
`Bash:cat`); measured basis, live corpus 2026-10-01: `Bash:mkdir` carried
59,586 context tokens over 13 increments, one increment of 23,390 tokens
that mkdir did not print. Amended 2026-10-01 (fifteenth judge): the
tokenizer is the standard library's `shlex` (posix; a run of `();|&` is
one word), so quoting is modelled (`echo "a; b"; make` -> `Bash:make`), a
nested `$(...)` collapses from the inside, and a builtin's arguments run to
the next separator, never a reserved word (`echo if x; make` ->
`Bash:make`); heredocs and function definitions are still not.

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
table's top row as a share of the total.** RULED 2026-10-01, same judge.
`sa context` had led with "top cause=tool_result 33%", the "mostly tools"
category PURPOSE calls true and useless. Now the lead is the top regular
row of the most specific dimension shown that `--where` did not pin, in the
order head, tool, cause, agent, session, project — declared once as
`schema.DIMENSIONS` reversed, general to specific — so `sa context` leads
with "top head=Bash:cat 554,879 (13.2% of the 4,188,015 total)" and `sa
spend` with the top agent; `--by` still overrides. The share is of the
headline TOTAL, named "of the N total"; the table's own `share of <base>`
column stays over its base, so the two differ whenever a residual or
signed row exists and each names what it is over. Same pass, three fixes
the judge measured: `--where cause=shrink` had been refused ("no facts
carry cause=shrink") because the present values were read from a table's
regular rows, which file shrink as signed — they now come from the carrier
facts themselves, by descending |mass|, and the closed-vocabulary guard is
parametrized over EVERY declared value; `--by fact` sorted by signed mass,
so a shrink leaf fell last under `--limit` — now by |mass|; and
`heads.bash_head` treats a newline and either parenthesis as separators,
drops a bare separator, skips `timeout`'s options (`VALUED` take a
word) before its duration, skips a `[`…`]` / `[[`…`]]` test, and skips
`exit` as a builtin (`cd x || exit 1; make` is `Bash:make`, re-pinned).
AMENDED 2026-10-01, seventh judge: picking the lead by position had led
a subagent window (72% of its mass ambiguous, sharing a tool but no head)
with `head=Edit:py 19,214` while `tool=Bash` carried 99,422 below it.
Levers are declared per view (`render.View.levers`): context `tool` and
`head`, spend `agent`; never `cause` (categories) nor a window dimension
(local corpus, 46 files, 2026-10-01: the top project row is 81.0% of the
context total; on a window drill each window table's one row is 100%).
AMENDED (judge 8): `--by` had made its table the lever, so
`spend --by session` and `context --by window` led with a population row
and `--by cause` with a category. Now the headline is grouped from the
levers alone, whatever `--by` shows (`fact` too), and since a head row
can never exceed its tool row it walks down: the top tool with its share
of the total, then `within it` the top head when it lies under that tool
(a top head under another tool ends the walk); a pinned lever drops out.
AMENDED 2026-10-01, ninth judge: `within it head=Bash:cat 839,141
(15.4%)` was a share of the total that read as a share of Bash, and a
top head under another tool was silent. Now the refining clause is the
largest head of the top tool's facts, grouped once, with both bases
(`47.0% of Bash, 15.4% of the total`), and when the largest head overall
lies elsewhere it follows: `top head=Read:py N (x% of the total) under
tool=Read`. A `--where` pin omits every default table and lever whose
facts all share one value (a pinned head implies its tool, a pinned
window its agent, session and project; `--by` still prints on request).
Same pass: `cd` joined `BUILTINS` in place of its own branch (`cd -P /x
&& make` -> `Bash:make`; a lone `cd /x` -> `Bash:other`, like `echo
done`); `query.Selection` dropped the CLI's root, since and corpus,
which `cli` now hands to `render.population`.

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
