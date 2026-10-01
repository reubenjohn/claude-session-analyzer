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
(RULED / DEFERRED / MOOT / RECORD-ONLY); the per-row headers below keep their
original status as history. Populations for every figure: see the brief;
corpus figures are 2026-07-28 sweeps and drift.

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

---

## R1 — Carrier of attributed mass (ENGINE_CONTRACT §5) — NEEDS-RULING

**The choice.** Where does `context_delta`'s attributed mass live? The
contract tags "spend and context_delta exist ONLY on generation facts"
[ARITHMETIC]. The misfile lens split it: *each token counted by exactly one
fact per metric* is the [ARITHMETIC] partition law; WHICH fact kind carries
the mass is a [RULING]. That split is what makes this cleanly rulable.

**Options considered.**
1. **C2's move (panel's evidence-based lean):** `context_delta` moves to
   increment facts; `spend` stays on generations. Clean buckets, the
   chain-integrity test and reconciliation footer hang naturally off
   increment facts, and Spike 2 shows the ported engine consumes them
   unmodified. Touches a pinned test and the [ARITHMETIC] tag's letter.
2. **Design A's variant:** keep §5's letter; mint a NEW additive metric
   `context_added` on contributor facts. No pinned test touched, but two
   token-mass metrics coexist and a consumer summing both double-counts —
   needs a declared reconciliation between them.
3. **Design B's silent both-carriers variant: REJECTED** by the panel (the
   one hard silent §5 violation; double-counts mass, inflates every share
   denominator).

**Measured stakes (Spike 2):** both kinds carrying `context_delta` in one
unpredicated map = exactly 2.000000x the true total, AND the mixed root's
shape-containment filter hides every `cause.*` axis — wrong and blind.
Whichever carrier wins, presets must lead with a kind predicate.

**Recommendation:** option 1, with C2's spelled-out fallback (fat generation
facts; see brief §3 item 5) if the owner keeps §5's letter.

## R2 — §6 file=lane re-tag + continuation-head probe — NEEDS-RULING

**The choice.** ENGINE_CONTRACT §6 tags "the carry resets to an empty window
at the start of EVERY file" [ARITHMETIC]. All three designers independently
flagged it: *never difference two unrelated windows* is [ARITHMETIC];
*file = lane* is a modeling choice — bg, /branch, --fork-session continue ONE
window in a new file, so the per-file reset books a boot-sized `lane_head`
delta at every continuation head (lane_head = 28.56% of chain mass, Spike 2).

**Options considered.** (a) Approve the named settling measurement — the
**continuation-head probe**: do continuation files' first calls report
occupancy ≈ the parent lane's last observed occupancy? Re-tag [OPEN] pending
its result. (b) Rule the [ARITHMETIC] tag stands as written; `lane_head`
remains the permanent honesty bucket.

**Recommendation:** approve the probe; keep file=lane and the `lane_head`
bucket in build v1 either way (no cross-file stitching ships in v1).

## R3 — Misfile-lens re-tag batch — NEEDS-RULING (one batch ruling)

**The choice.** The misfile lens adjudicated 9 contract-tag cases; none are
applied until ruled. The shared pattern (rule it once, not nine times): the
contract fuses a true statement about a QUANTITY with a DISPOSITION toward it
(carrier, reset point, display refusal, quarantine, clamp) and tags the pair
by the stronger half. The ported code already treats several dispositions as
policy. The batch:

1. §6 carry resets every file — SPLIT: never-difference-two-windows
   [ARITHMETIC]; file=lane [OPEN] + continuation-head probe (substance = R2).
2. §5 only-generation carriers — SPLIT: one-fact-per-token-per-metric
   [ARITHMETIC]; carrier choice [RULING] (substance = R1).
3. §1 peak→None, never max — SPLIT: no-sum / no-max-as-peak [ARITHMETIC];
   refusing a labeled member-max display [RULING].
4. metric_units fail-open — CORRECTLY TAGGED, but latent code defect: nothing
   pins set(METRIC_UNITS) == set(AGGREGATION); add the swept test (P1 closes
   this).
5. §7 duplicate-partition suppression — SPLIT: signature =
   partition(+residual) [ARITHMETIC]; suppression + alphabetical survivor
   [OPEN].
6. §4 shrink-quarantine lead (A's #2) — MISFILED: no-slot/no-sum core
   [ARITHMETIC]; quarantine disposition [OPEN].
7. §1 derived-absent — SPLIT: never-0 / never-misnamed-mean [ARITHMETIC];
   absent-vs-labeled-mean-vs-pooled-recompute [OPEN].
8. §1 sanctioned door (peak stays measurable via η²) — SPLIT: measurability
   [ARITHMETIC]; must-stay-open mandate [RULING].
9. §2 no-clamp — SPLIT: shrinks-are-real [MEASURED]; unclamped disposition
   [RULING].

**Options.** Accept the batch re-tags as listed; or accept with exceptions
named per row; or reject (tags stand as written).

**Recommendation:** accept the batch. No behavior changes in build v1 —
these change what KIND of claim each invariant is, i.e. which future
challenges are category errors and which are rulable.

## R4 — Bless the measured attribution headline — NEEDS-RULING

**The choice.** The build-brief non-negotiable says "~77% of intervals
attribute exactly … the other ~23%" (ENGINE_CONTRACT §4 [MEASURED], older
corpus, all-non-assistant contributor definition). Spike 1 measured, on
51,960 intervals (full corpus 2026-07-28, token-relevant contributor
definition): **94.98% exact / ~5% ambiguous** (multi_contributor 3.08%,
shrink 1.59%, remainder_negative 0.35%, zero-token-relevant 0.00%).

**Options.** (a) Bless the new headline: MEASURED supersedes MEASURED by a
new measurement — the sanctioned channel — so the non-negotiable's wording
does not outlive its measurement. (b) Keep quoting ~77% (now known-stale).

**Recommendation:** bless (a), with the population and the token-relevant
definition's [OPEN] attachment caveat printed wherever the figure appears.
Note: this does NOT relax "no estimated attribution" — the ambiguous bucket
stays, it is just smaller.

## R5 — `tool_input_head` normalization rule — NEEDS-RULING (privacy)

**The choice.** The flagship pivot needs a low-cardinality command-head
dimension stamped at parse time. Proposed rule: for Bash, the FIRST token of
`input.command`; for file tools, extension only; never a full command line,
never a file path; one declared head-extractor mapping, swept and asserted
nonempty.

**Why the owner must see it before it ships:** this is the one new surface
that derives an ATTRIBUTE from transcript CONTENT. Heads land in datasets,
reports, and drill output — unlike evidence fields they are meant to be
displayed and grouped. A wrong rule leaks (first "token" of `env
SECRET=… cmd`, or a path-shaped first token); even a right rule turns command
vocabulary into a queryable dimension. The privacy gate (no transcript text
in tracked files) makes the extraction rule itself privacy policy, so it is
[OPEN] with a mandatory owner review, not a build detail.

**Options.** (a) Ship the proposed rule as scoped above; (b) restrict v1 to
`tool_name` only, defer heads; (c) owner amends the rule (e.g. an allowlist
of known command heads, everything else → `other`).

**Recommendation:** (a), with (c)'s allowlist noted as the hardening path if
review finds leak-shaped heads. Measured value: top head bucket = 10.77% of
chain mass vs top agent 0.24% (~44x, Spike 2) — this axis is why the rewrite
answers PURPOSE's flagship question.

## R6 — `sa_schema.py` import surface — NEEDS-RULING (build precondition)

**The choice.** Ported `sa_schema.py` line 23 does `from lib import lib_cli,
lib_dataset`. Neither file is on the v1 read allowlist, neither was ported —
so the engine CANNOT import standalone (Spike 2 finding 0; the probe stubbed
the modules, zero engine bytes changed, but a stub is not a build).

**Where the imports are used (measured on the ported file):** only in the CLI
entry path — `lib_cli.prog(__file__)` (argparse prog name, line 344),
`lib_dataset.add_stale_arg(ap)` (line 348), `lib_dataset.version_error(ds,
path, tool="sa schema")` (line 361), all inside `main()`. The library surface
the engine actually needs (`AGGREGATION`, `METRIC_UNITS`, `metric_units`,
`flatten`, `census`, …) never touches them.

**Options.**
1. **Owner allowlists** v1's `lib_cli.py` + `lib_dataset.py` for verbatim
   porting (widens the clean-room window; imports v1's CLI/dataset-versioning
   machinery the build may not want).
2. **Owner sanctions a minimal mechanical strip.** Exactly what it touches:
   the two-name import on line 23 plus the three call sites above — either
   delete `main()`/`__main__` entirely (the build queries the library
   surface, not v1's CLI) or make the import lazy inside `main()`. No
   docstring, declaration, or census-logic byte changes; the diff is
   committed and named as the sanctioned exception to "port verbatim".
3. Something else the owner prefers (e.g. port stubs that raise on use).

**Recommendation:** option 2, delete-the-CLI variant — smallest surface,
keeps the clean-room boundary intact, and the removed code is v1 CLI plumbing
the v2 presets replace anyway. Build blocks until answered: this is the
first task of any build session.

---

## P1 — METRICS single declaration (Design B graft) — proposed

**Choice:** one v2 `METRICS` declaration (name → class, unit); swept,
vacuity-guarded test asserts both ported dicts agree and the sweep found
≥ 13 metrics. New metrics touch one declaration; ported files stay verbatim.
Also closes misfile-batch row 4's latent defect. **Options:** wrapper (as
proposed) / fallback: keep two ported dicts + a pinned key-set-equality test.
**Recommendation:** wrapper.

## P2 — Shrink's home — proposed

**Choice:** shrink's signed mass demotes `cause.kind` (#1-ranked dimension)
to a count-basis concentration while siblings rank on mass — silent basis
mixing (Spike 2; ENGINE_CONTRACT §2 live). **Options:** sign attribute /
quarantine kind outside the default preset / accept-and-render
`dist_basis_reason`. **Recommendation:** exclude `shrink` from the `context`
preset's membership predicate; its mass stays reconciliation-footer-mandatory
(−3.91M tokens corpus-wide), so honesty survives and the default ranking
stays on one basis.

## P3 — Residual-aware `top_key` rendering — proposed

**Choice:** `top_key`/`top_metric_share` can BE the residual bucket (observed
59.94% residual printed as "top", Spike 2). **Options:** display layer owns
residual handling (recommended, no engine change) / engine grows a
top-non-residual field — an engine change only an owner ruling could
authorize; NOT requested in v1. **Recommendation:** renderer rule — never
print `top_key` as "top" without residual handling.

## P4 — `cause.candidates` to evidence — proposed

**Choice:** lists json-dump into one opaque flatten key; the dimension died at
98.3% residual (Spike 2). **Recommendation:** candidates move to the evidence
side (locator/preview); the drillable scalar is `cause.candidate_count`.
Diverges from Design C as originally briefed; measured, not argued.

## P5 — `lib_corpus.py` shared parser — proposed tangent

**Choice:** two spike probes (three, counting Phase 0's) duplicate
`read_file`/`build_calls`/`tool_index` verbatim. **Recommendation:** promote
to `scripts/lib/lib_corpus.py` before a third copy drifts; the build's parser
grows from it rather than from a fourth copy. Cost: one module + tests; the
panel reported it upward as the standing missing-tool signal.

## P6 — Usage-less call disposition — proposed (keep as ported)

**Choice:** ENGINE_CONTRACT §6: a call reporting no usage emits `0` without
advancing the carry; the trailing parenthetical marks `0`-over-no-fact
[OPEN]. Design A proposed absent-metrics-not-0. **Recommendation:** keep the
ported behavior in build v1 — no new measurement distinguishes the options'
totals (they are identical; the difference is `n_valued` honesty), and the
misfile batch (R3 row 7) already routes the display-side question. Revisit
only with a measurement.

## P7 — v1 [OPEN] choices kept unchanged — proposed (keep)

**Choice:** score = stat × cover; cover as fact count; missing-key/null
residual unification; purity boundary; fail-closed unclassified metric;
absent-not-defaulted statistic fields; max-merge reconciliation.
**Recommendation:** keep all, unchanged — no new measurement, and these
survived mutation testing; challenging them on argument alone is the recorded
failure mode. Listed so the keep is itself a logged decision.

## P8 — Schema shape rules — proposed

**Choice:** two rules Spike 2 measured against the ported engine: dimension
attributes nest at most two deep (`flatten()` offers depth-2 only; deeper is
silently un-offerable), and lane identity lives only in `locator.source`
(duplicate attribute folds into an alias row). **Recommendation:** declare
both as tested schema rules so they are design, not rediscovery.

## P9 — Presets-as-data + computed denominators — proposed

**Choice:** a view is `{membership predicate, default metric, starting
path}` — data, not code; two presets (`context`, `spend`); every population
line counted from the predicate (B graft), never hand-written prose; a preset
naming an unknown metric dies in `statistic_for`; unknown `cause.kind` fails
closed. **Recommendation:** build as stated; this is the replacement for
v1's ~40 hand-maintained tables (three fail-silent) the charter orders
killed.
