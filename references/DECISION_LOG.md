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

**R2 — window model.** RULED: a window is a file in build v1. The opus second
opinion had proposed a parentUuid-chain window model pending a probe; the
probe falsified it, so the fallback (file = window) is adopted as this log
originally recommended. Measured basis (local corpus probe, 21 files,
2026-09-30): 0 of 1,523 parentUuid links cross files and 0 uuids repeat
across files, so a parentUuid chain cannot stitch continuations. Forked agent
files instead start with a null-parent assistant root and carry a uuid-less
`fork-context-ref` record (fields `agentId`, `parentSessionId`,
`parentLastUuid`, `contextLength`) whose first-call occupancy is ~1.01x the
parent's occupancy at that point. Consequence: the `window_head` bucket (the
first usage-carrying call's occupancy) is inherited context for a fork and
boot context for a fresh session; either way it is always its own labelled
row and never spread. Design-for-later: the parser records
`fork-context-ref`'s `parentSessionId` and `parentLastUuid` as evidence on
the window_head fact so cross-file stitching can be added without a schema
change; no stitching ships in v1.

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
basename.** RULED 2026-10-01, on a fourth judge's rejection of 859225b;
opus agreed. R5's "first token" is read as the first command word:
`for f in …; do cmd; done` had yielded `Bash:for` (the #2 Bash head on the
live corpus, 164k tokens: a keyword, not a command). Now `for`, `while`,
`until`, `if`, `elif` drop everything through the `do` or `then` that opens
their body; the bare wrappers `{`, `(`, `!`, `time`, `sudo`, `env`,
`nohup`, `xargs` drop, and `timeout` with its duration, as a leading
assignment does; each list is one declared tuple in `heads.py`. Amendment:
a path-shaped first command word is its basename (`./check.sh` ->
`Bash:check.sh`, `/usr/bin/python3` -> `Bash:python3`), still subject to
`HEAD_SHAPE` and never a directory (`scripts/` -> `other`); it is one
expression in `heads.bash_head`. Known gaps, logged
and not widened now: an interpreter followed by a script (`python3
scripts/x.py`, `bash x.sh`) still yields the interpreter; and a loop whose
body opens with a label (`for f in …; do echo "== $f"; cat "$f"; done`)
yields `Bash:echo`, so on the live corpus (31 windows, 2026-10-01)
`Bash:echo` rose from under 44k to 167k tokens as `Bash:for`'s mass
dispersed. Same pass: a `--where` value that no fact carries (`tool=bash`)
exits 2 naming the values present by descending mass, narrowed pair by
pair, instead of printing a confident zero; each table's count column is
named for its carrier kind (`increments`, `calls`), since one ambiguous
increment counts several results; `cli` computes the reconciliation once
on the `Selection` (now in `query`, with `VIEWS` in `cli`) and `render`
only formats; `schema` reads the cache tiers through
`usage.cache_creation_tiers`, the ported helper made public with its body
unchanged; `walk.Contributor.dims` names its dimensions explicitly.

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
AMENDED again, eighth judge: `--by` had made its table the lever, so
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
2026-10-01, on a sixth judge's rejection of 8746202. A main window could
not be isolated: it carries no `agent` (D-AGENT-DIM) and `--where
session=` keeps every subagent window of that session, so the window the
user sat in was only ever answered mixed with its forks. Now every fact of
both kinds carries `window`, the root-relative file name (a window IS a
file, R2), constant per window, so filtering on it keeps a whole window
and the reconciliation still telescopes (local corpus, 36 windows,
2026-10-01: one main window answered alone reconciles at 280,967 tokens
over 97 intervals, 84.5% exact). It is drillable via `--where` and `--by`
and sits in no default table: one row per file is a listing, not a
breakdown; `--by fact` leaves omit the `window=` tag because the locator
beside it already names the file. Same pass: a drill's headline counts
the windows its facts actually come from ("in 29 of 36 windows"; plain
"in 36 windows" when every window qualifies) instead of the whole-window
count; `ambiguous` joins `window_head` as a row the headline never names
as the lever, with its own note under `by cause`; the forest-wide usage
index moved from every `SourceFile` to `Corpus.usages` and is passed to
`walk`; `query.narrow` is the one `--where` check (undeclared dimension
or value, a dimension the carrier never has, a value no fact carries) and
`query.group` checks `--by` against the carrier, the CLI only surfacing
the library's error as exit 2; the fork evidence keys and `candidates`
are declared once in `schema`.
