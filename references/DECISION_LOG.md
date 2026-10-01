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
`Read:py`), and `&&`/`||` are padded like `;`.

---

## Phase 3 synthesis — the rows as proposed (history)

Travels with `DESIGN_BRIEF.md`. Every open or disputed choice is a numbered
row. **Original STATUS meanings:** `NEEDS-RULING` — the build BLOCKS until
the owner answers; `proposed` — synthesis will build it as recommended unless
the owner vetoes. The status column now shows the 2026-09-30 ruling
(RULED / DEFERRED / MOOT / RECORD-ONLY). The per-row discussions as
originally proposed are in `DECISION_LOG_HISTORY.md`. Populations for every
figure: see the brief; corpus figures are 2026-07-28 sweeps and drift.

| id | choice | status |
|---|---|---|
| D-ENGINE | Retire the ported ranking engine | RULED |
| R1 | Carrier of attributed mass (ENGINE_CONTRACT §5) | RULED |
| R2 | §6 file=lane re-tag + continuation-head probe | RULED |
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

