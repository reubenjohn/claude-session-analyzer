# session-analyzer v2 — decision log history: rows moved verbatim out of
`DECISION_LOG.md`, and what each superseded proposal was. The proposals
themselves are in git (`git show 048b3ff:references/<file>`).

## Phase 3 synthesis — the rows as proposed (history)

The Phase 3 synthesis's numbered rows and their 2026-09-30 ruling; the
discussions as proposed: `git show 048b3ff:references/DECISION_LOG_HISTORY.md`.

| id | choice | status |
|---|---|---|
| D-ENGINE | Retire the ported ranking engine | RULED |
| R1 | Carrier of attributed mass (ENGINE_CONTRACT §5) | RULED |
| R2 | §6 file=lane re-tag + continuation-head probe | SUPERSEDED (D-CONTEXT-WINDOW) |
| R3 | Misfile-lens re-tag batch (9 verdicts) | RECORD-ONLY |
| R4 | Bless 94.98%/~5% headline over ~77%/~23% | RULED (neither) |
| R5 | `tool_input_head` normalization rule (privacy) | RULED |
| R6 | `sa_schema.py` import surface (allowlist vs strip) | MOOT |
| P1 | METRICS single declaration (B graft) | RULED |
| P2 | Shrink's home: exclude from `context` preset | MOOT |
| P3 | Residual-aware `top_key` rendering | MOOT |
| P4 | `cause.candidates` → evidence + `candidate_count` | RULED |
| P5 | `lib_corpus.py` shared-parser tangent | RULED |
| P6 | Usage-less call: keep ported 0-without-advancing | RULED |
| P7 | Keep v1's untouched [OPEN] engine choices | MOOT |
| P8 | Schema rules: depth-2 nesting, one lane home | MOOT |
| P9 | Presets-as-data; computed denominators | RULED |

## Rows moved from `DECISION_LOG.md`, 2026-11-15 (verbatim)

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

## Rows moved from `DECISION_LOG.md` (verbatim; formerly `DECISION_LOG_HISTORY_2.md`)

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

## Rows moved from `DECISION_LOG.md`, 2026-11-16 (verbatim)

**R5 — `tool_input_head` normalization.** RULED: option (a) with a mechanical
guard. Bash head = first token after stripping leading `VAR=value`
assignments and `cd <dir>` prefixes ended by `&&`, `;` or `||`; kept only if it matches
`^[A-Za-z0-9_.+-]{1,32}$` and contains no slash, else `other`. File tools ->
extension only. One declared extractor mapping. Rationale: output goes to the
user's own terminal from their own transcripts; the privacy gate governs
tracked files.

**D-START-CAUSE — `start` names what began a window.** RULED. A window
dimension on both kinds, constant per window: `session_start`,
`subagent`, `fork`, `replayed`, `compaction`; fork beats subagent (forks
live under `subagents/`). `start`, not `trigger`: it names the line it
heads; `replayed`, not `resume`: the record, not a guessed intent.
Measured 68 / 513 / 10 / 0 / 5; `replayed` declared, 0 observed. [W][O]

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

## Rows moved from `DECISION_LOG.md`, 2026-11-16, per call (verbatim)

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

## Rows moved from `DECISION_LOG.md`, 2026-11-16, phase 2 (verbatim)

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
