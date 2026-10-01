# session-analyzer v2 — decision log (Phase 3 synthesis)

Travels with `DESIGN_BRIEF.md`. Every open or disputed choice is a numbered
row. **STATUS meanings:** `NEEDS-RULING` — the build BLOCKS until the owner
answers; `proposed` — synthesis will build it as recommended unless the owner
vetoes. Populations for every figure: see the brief; corpus figures are
2026-07-28 sweeps and drift.

| id | choice | status |
|---|---|---|
| R1 | Carrier of attributed mass (ENGINE_CONTRACT §5) | NEEDS-RULING |
| R2 | §6 file=lane re-tag + continuation-head probe | NEEDS-RULING |
| R3 | Misfile-lens re-tag batch (9 verdicts) | NEEDS-RULING |
| R4 | Bless 94.98%/~5% headline over ~77%/~23% | NEEDS-RULING |
| R5 | `tool_input_head` normalization rule (privacy) | NEEDS-RULING |
| R6 | `sa_schema.py` import surface (allowlist vs strip) | NEEDS-RULING |
| P1 | METRICS single declaration (B graft) | proposed |
| P2 | Shrink's home: exclude from `context` preset | proposed |
| P3 | Residual-aware `top_key` rendering | proposed |
| P4 | `cause.candidates` → evidence + `candidate_count` | proposed |
| P5 | `lib_corpus.py` shared-parser tangent | proposed |
| P6 | Usage-less call: keep ported 0-without-advancing | proposed |
| P7 | Keep v1's untouched [OPEN] engine choices | proposed |
| P8 | Schema rules: depth-2 nesting, one lane home | proposed |
| P9 | Presets-as-data; computed denominators | proposed |

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
