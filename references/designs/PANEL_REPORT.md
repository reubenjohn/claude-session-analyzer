# Panel report — design competition, Phase 2

Process artifact, disposable with the branch. Inputs: three design briefs
(DESIGN_A/B/C.md), four critic lenses, two grounding spikes run against the
full live corpus, one revision round (DESIGN_C2.md). Every figure below names
its population; corpus figures are from 2026-07-28 sweeps and will drift.

## Recommendation

**Base: Design C (increment facts), revised as DESIGN_C2.md**, with grafts
from A and B listed in §5. C is the only brief whose every deviation traveled
the sanctioned channel (decision-log + fallback + measurement), its fact grain
equals the answer grain so the ported engine answers the two shipped questions
with zero new engine code, and the spikes strengthened rather than weakened
it: its contributor-definition proposal was confirmed (exact attribution lands
at 94.98%, not the budgeted ~77–84%), and its conservation test — restated
honestly as a chain-integrity invariant — is the strongest single drift guard
any brief offered.

## 1. Spike results

### Spike 1 — interval boundary (`scripts/probes/probe_interval_boundary.py`)

All three designers independently named the interval boundary their weakest
point. Measured on the full corpus (1,854 files, 229,320 parsed records, 2
unparseable lines, 395 within-file duplicate-uuid records dropped, 53,987
calls, 53,781 usage-carrying, 1,821 lanes, **51,960 intervals**; sanity vs
Phase 0: 84.41% reproduces its 84.43%, 84 interleaved ids reproduce exactly):

- **(a) Exact attribution — 49,352 / 51,960 = 94.98%** (exactly one
  token-relevant contributor AND remainder R = Δocc − out_prev ≥ 0 AND
  Δocc ≥ 0). Disjoint failures: multi-contributor 3.08%, Δocc<0 1.59%,
  R<0 0.35%, zero-token-relevant **0.00%**. The ambiguous bucket is ~5%,
  not the ~15–23% every brief budgeted. The non-negotiable's "~77% exact"
  understates what the measured boundary now delivers.
- **(b) Candidate definition** (same 51,960 intervals): exactly-one rate is
  84.41% counting all non-assistant records (Phase 0's definition), 85.94%
  excluding uuid-less bookkeeping, **96.92% counting only token-relevant
  contributors** (tool_result / user_text). Zero intervals lack a
  token-relevant contributor, so no delta is ever stranded causeless.
  Safety signal: mean exact R is LOWER (1,193 vs 1,741) when attachment/
  system records are also present — no evidence the excluded kinds carry
  tokens (a signal, not a proof; stays an [OPEN] caveat).
- **(c) Interleaved message.ids: dedup-then-locate dissolves them.**
  Phase 0's 84 interleaved ids reproduce on raw records — and all 84
  produce inverted+empty boundaries there — but after within-file uuid
  dedup (keep first) they drop to **0 / 53,987 calls; 0 empty, 0 inverted,
  0 overlapping intervals corpus-wide**. They were replayed assistant
  records, not concurrent generations. Consequence: within-file dedup is
  the boundary's PRECONDITION, and any boundary-partition test needs a
  vacuity guard asserting the pre-dedup pathology count is nonzero.
- **(d) Design C's conservation test: tautological AS WRITTEN, valuable
  restated.** It holds 1,821/1,821 lanes by construction (every branch
  books exactly Δocc, so buckets telescope to final − head). What it
  really tests is CHAIN INTEGRITY: drop the quarantined intervals from
  the chain — the natural reading of "quarantined out of the attribution
  view" — and it fails on 187/1,821 = 10.27% of lanes, 127 of them by
  >10k tokens. Verdict on the orchestrator's question: keep the invariant,
  state its real claim (catches dropped/reordered/double-counted
  intervals), and REQUIRE the reconciliation footer to carry quarantined
  (−3.91M tokens corpus-wide) and lane_head mass. Global buckets: exact
  82.8M, feed-forward 47.6M, ambiguous 7.9M + 0.24M negative-remainder,
  quarantined −3.9M context tokens.

### Spike 2 — engine seam (`scripts/probes/probe_engine_seam.py`)

Recommended fact shape (C + grafts) built over the full corpus and fed to the
ported engine as shipped. Population: 1,856 files, 1,823 lanes, **158,987
facts = 53,946 generation + 105,040 increment** (the corpus is live; totals
move a little between runs).

- **Port friction (finding 0):** the engine did NOT import standalone —
  ported `sa_schema.py:23` does `from lib import lib_cli, lib_dataset`,
  neither ported. The probe stubbed the modules; **zero engine bytes
  changed**. The build must port or strip that import.
- **Seam PASSES:** every grafted axis surfaces natively in
  `discover_dimensions` — `cause.kind` (score .4646), `cause.tool_name`
  (.3261), `cause.tool_input_head` (.2732), `agent_id` (.0998), `lane`
  (.0263) — with no engine change.
- **Chain integrity PASSES integer-exact:** root `resolve_path` over
  increments = 188,975,626 = Σ lane final occupancy. Mass shares of the
  chain: lane_head 28.56%, feed_forward 25.28%, tool_result **42.72%**,
  user_text 1.21%, ambiguous **4.30%**, shrink −2.07%.
- **Double-carrier hazard MEASURED (owner-ruling evidence for §5):**
  `context_delta` on both generation and increment facts in one
  unpredicated map = **exactly 2.000000x** the true total; and the mixed
  root's shape-containment filter hides every `cause.*` axis, so the
  unpredicated root is both wrong AND blind. A `kind=="increment"`
  membership predicate restores the exact total.
- **The flagship pivot is REAL:** the engine, unprompted, ranks the
  input-head axis above the agent axis; the top input-head bucket carries
  **10.77%** of chain mass vs the hottest single agent's **0.24%** (~44x)
  — populations: 105,040 increments; agent card 1,590. PURPOSE's "the
  biggest lever lives on a different slicing" reproduces in the engine's
  own ranking on this corpus. Spend also answers with zero new code
  (root 1.018B base-token-equivalents over 53,946 generation facts), and
  the top spend agent ≠ the top context agent.
- **Seam frictions for the build** (NOT yet folded into DESIGN_C2.md — the
  seam spike finished after the revision; THIS list is authoritative and a
  C2 amendment or the build brief must carry it): shrink's signed mass
  demotes `cause.kind` to a count-basis concentration while siblings rank
  on mass (silent basis mixing, ENGINE_CONTRACT §2 live); `top_key` /
  `top_metric_share` can BE the residual (observed 59.94% printed as
  "top"); `flatten()` offers depth-2 only (deeper nesting silently
  un-offerable); list-valued attributes json-dump to one opaque key
  (`cause.candidates` rejected at 98.3% residual — dead weight as a
  dimension); duplicating lane identity on an attribute and
  `locator.source` costs a folded alias row.

## 2. Per-design verdicts by lens

### Design A — flat event log
- **Contract:** arithmetically clean walkthrough (every number checked);
  two dings — quotes Phase 0's MEASURED exactly-one figure over a
  contributor population the design changed without a new measurement
  (spike 1(b) has now supplied that measurement), and the new
  `context_added` metric on tool_result facts is only half-routed (a
  misfile aside, not a decision-log item).
- **Complexity:** best of the three. Fewest stored artifacts, dimensions
  cost zero declarations (`flatten()`), swept two-dict consistency test.
  Worst smell: reason-code vocabulary + `feeds_gen` derived positionally
  from the same field its invariants check — self-consistent misrouting
  passes its own tests.
- **Question-tracer:** Q1 PASS, Q3 PASS-WITH-GAP (cache-write metric never
  declared stored), Q2 FAIL — no tool-input field stored anywhere, and the
  "zero-declaration dimensions" claim hides the cost of adding one.
- **Misfiles:** 3 flagged, all upheld (two as SPLIT, one as MISFILED).

### Design B — join-first / relational
- **Contract:** the panel's one hard silent violation — §1 asserts §5
  compliance, then §2.7 emits `context_delta` on attribution facts with a
  different value than the generation's own, double-counting mass and
  inflating every share denominator. Also: no routing for interleaved
  intervals (the one design that could print exact-and-wrong — though
  spike 1(c) shows dedup-first empties that hazard), and a §3 claim
  ("kept: 0 without advancing") contradicted by its own build.
- **Complexity:** heaviest. Largest hand-maintained surface (per-column
  role registry + a denormalized fact layer with no stated reconciliation
  test) beside a self-admitted silent-misfile seam. Best property: only
  brief to name the ported two-dict metric wrinkle as a defect and propose
  the single-declaration METRICS wrapper with a consistency test.
- **Question-tracer:** Q1 PASS-WITH-GAP (ambiguous mass is an interval
  status, not a fact — invisible inside the drill table), Q2 FAIL twice
  (tool input roled `evidence` = declared unsliceable; NO agent axis on
  any relation), Q3 FAIL (same missing agent axis on the spend carrier).
- **Misfiles:** 2 flagged, both upheld as SPLIT.

### Design C — increment facts
- **Contract:** zero silent violations; every deviation routed with
  measurement or fallback attached ("the model exemplar of the sanctioned
  channel"). Exposure: the brief is architected around the carrier move
  landing, and prices the fallback at one sentence.
- **Complexity:** leanest pipeline (fact grain = answer grain; the
  question IS one engine call) but openly fails the one-declaration
  metric gate (touches AGGREGATION + unit, unswept) and leaves
  `cause.kind` — its central vocabulary — without a derivation test.
- **Question-tracer:** Q1 PASS (cleanest trace), Q3 PASS-WITH-GAP (agent
  attr on call facts implied, not declared), Q2 FAIL — but the cheapest
  fix of the three: one parse-time attribute stamp, C's own declared
  mechanism for adding a dimension.
- **Misfiles:** 2 flagged, both upheld as SPLIT; its §5 re-tag proposal
  adopted verbatim by the misfile lens.

**Cross-design finding (question-tracer, decisive):** NO brief as written
can answer PURPOSE's flagship pivot ("one bash pattern across 42 agents
beats the top agent") — all three carry tool input as evidence-or-nothing,
never as a dimension. DESIGN_C2 adds `cause.tool_input_head` (normalized,
low-cardinality) as a parse-time attribute for exactly this reason.

## 3. Scored comparison against the charter gates

| Charter gate | A | B | C (as briefed) |
|---|---|---|---|
| Derivation over enumeration | best (swept dict pair; flatten) | worst (role registry + unswept enums) | mid (cause.kind unswept) |
| Metric = one declaration | 2 dicts, 1 module, swept | wrapper proposed, needs ruling | FAILS openly (2 touches, no sweep) |
| Dimension = one declaration | zero (stored fields only — hides ingest cost) | one column entry | one parse-time stamp |
| Zero fail-silent surfaces | 2 seams, both drift-tested | 3, incl. one self-admitted silent misfile | 2, best drift guard (telescoping) |
| Engine purity / no rewrite | clean, native input | clean, wrapper routed | clean; carrier move ruling-gated |
| Contract discipline | 1 minor violation, 1 half-routed | 1 hard silent violation | clean, fully routed |
| Reaches evidence (Q1/Q3) | PASS / GAP | GAP / FAIL | PASS / GAP |
| Cross-slice pivot (Q2) | FAIL | FAIL twice | FAIL, cheapest fix |

Complexity-lens ranking A > C > B; contract and tracer lenses rank C > A > B.
B is not salvageable as a base: its two structural absences (agent axis,
ambiguous-as-fact) plus the silent §5 violation are load-bearing, while its
genuinely good ideas (computed denominators from population predicates, the
METRICS wrapper) graft cleanly onto C.

## 4. Misfile verdicts (routed to the owner; none applied)

Adjudicated by a dedicated lens against the ported code; the ported engine
itself is the best witness (labeled means at lib_drill.py:224-250, the
`collapse=False` opt-out at :558-572).

| Case | Verdict | Proposed re-tag |
|---|---|---|
| §6 carry resets every file | SPLIT | never-difference-two-windows [ARITHMETIC]; file=lane [OPEN] + continuation-head probe |
| §5 only-generation carriers | SPLIT | one-fact-per-token-per-metric [ARITHMETIC]; carrier choice [RULING] |
| §1 peak→None, never max | SPLIT | no-sum / no-max-as-peak [ARITHMETIC]; refusing a labeled member-max display [RULING] |
| metric_units fail-open | CORRECTLY TAGGED | latent code defect: nothing pins set(METRIC_UNITS)==set(AGGREGATION) (sa_schema.py:115 vs lib_drill.py:151) — add swept test |
| §7 duplicate-partition suppression | SPLIT | signature=partition(+residual) [ARITHMETIC]; suppression + alphabetical survivor [OPEN] |
| §4 shrink quarantine lead (A#2) | MISFILED | no-slot/no-sum core [ARITHMETIC]; quarantine disposition [OPEN] |
| NEW §1 derived-absent | SPLIT | never-0 / never-misnamed-mean [ARITHMETIC]; absent-vs-labeled-mean-vs-pooled-recompute [OPEN] |
| NEW §1 sanctioned door | SPLIT | measurability [ARITHMETIC]; must-stay-open mandate [RULING] |
| NEW §2 no-clamp | SPLIT | shrinks-are-real [MEASURED]; unclamped disposition [RULING] |

Pattern the owner should see once, not nine times: the contract fuses a true
statement about a QUANTITY with a DISPOSITION toward it (carrier, reset
point, display refusal, quarantine, clamp) and tags the pair by the stronger
half. The ported code already treats several of those dispositions as policy.

## 5. Recommended grafts onto the C base (in DESIGN_C2.md)

1. **From B:** the METRICS wrapper — one v2 declaration (name → class,
   unit) with a swept consistency test against both ported dicts; fixes
   C's failed metric gate and the latent metric_units drift defect in one
   move. Routed as a decision-log item, never an in-place edit.
2. **From B:** computed denominators — every population line counted from
   a membership predicate, never prose.
3. **From A:** machine-readable reason codes on every non-exact interval,
   population lines printed from their counts; the `interleaved` code kept
   although measured-extinct post-dedup, as the vacuity guard's witness.
4. **From the tracer:** `cause.tool_input_head` stamped at parse time (the
   pivot enabler), the agent attribute declared on generation facts, and
   per-tier cache-write token metrics on generation facts (Q3's gap).
5. **From spike 1:** dedup-then-locate as a stated precondition;
   token-relevant contributor definition adopted as MEASURED (96.92% /
   94.98%, populations above); conservation restated as chain integrity
   with a mandatory reconciliation footer carrying quarantined and
   lane_head mass; the ~5% ambiguous budget replacing ~23%.

## 6. Iteration run

One revision round, C only (DESIGN_C2.md). Judged real, not ceremony: C's
brief contained claims the spikes superseded (its ambiguous budget, its
Phase-0b proposal now executed, its conservation claim as written), plus
three critic-found gaps (metric gate, cause.kind sweep, pivot dimension).
A and B were not revised — the verdict spread was decisive, and their
salvageable ideas travel as grafts. No second round: nothing left in
dispute is settleable by another design document; what remains is owner
rulings and measurements.

**DESIGN_C2.md's changes from C** (11,975 chars, charter format): contributor
definition upgraded to token-relevant on the measurement (84.43% → 94.98%
exact); dedup-then-locate as boundary precondition; conservation restated as
chain integrity + counterfactual + mandatory footer; B's METRICS single
declaration grafted (13/13 coincidence pinned by a swept test); `cause.kind`
derivation test failing closed; `cause.tool_input_head` + generation-fact
agent attributes + per-tier cache-write metrics; A's reason codes with
computed population lines; the §5 carrier-move fallback spelled out as a full
degraded model (what survives, what is lost).

**Known gap:** DESIGN_C2.md predates the seam spike and does not yet carry
its findings (double-carrier 2.000000x, shrink basis-mixing, candidates-list
rejection, depth-2 rule, top_key-residual renderer rule, the sa_schema
import friction). §1's Spike 2 section above is authoritative for those; a
C2 amendment was requested but had not landed at report time.

## 7. Disputes only the owner can settle

1. **Where attributed mass lives** (the ENGINE_CONTRACT §5 carrier
   question). Three positions on the table: C2 — `context_delta` moves to
   increment facts (clean buckets, telescoping test, but touches a pinned
   test and an [ARITHMETIC] tag); A — keep §5's letter, mint a NEW metric
   `context_added` on contributor facts (no pinned test touched, but two
   token-mass metrics coexist and a consumer summing both double-counts —
   needs a declared reconciliation); B's silent both-carriers variant is
   rejected. The misfile lens's split (partition law [ARITHMETIC], carrier
   [RULING]) makes this cleanly rulable. **Panel's evidence-based lean:
   C2's move**, because the reconciliation footer and chain-integrity test
   hang naturally off increment facts, and spike 2 shows the engine
   consumes them unmodified.
2. **The §6 file=lane re-tag** — all three designers converged on it; the
   settling measurement is named (do continuation files' first calls
   report occupancy ≈ parent lane's last observed?). Approve the probe or
   rule the tag stands.
3. **The remaining misfile re-tags** (§4 lead inversion, §7 suppression,
   §1 derived/door, §2 no-clamp) — batch ruling on the quantity-vs-
   disposition pattern in §4 above.
4. **The exact-rate headline** — the build brief's "~77% exact / ~23%
   ambiguous" non-negotiable is superseded by 94.98% / ~5% under the
   measured token-relevant definition (population: 51,960 intervals,
   2026-07-28). The owner should bless the new headline so the
   non-negotiable's wording doesn't outlive its measurement.
5. **`cause.tool_input_head` normalization** — the pivot needs a
   low-cardinality command-head dimension; the normalization rule (first
   token for Bash, extension-only for file tools) is a privacy-relevant
   [OPEN] choice the owner should see before it ships.
6. **Two engine-adjacent [OPEN] choices the seam spike surfaced** —
   (a) shrink's home: leaving the signed shrink bucket inside `cause.kind`
   demotes the top-ranked dimension to a count basis (C2 recommends
   excluding shrink from the default context preset's predicate, footer
   keeps the mass); (b) `top_key`/`top_metric_share` include the residual
   bucket — either the display layer owns residual handling or the engine
   grows a top-non-residual field, which is an engine change only a
   ruling can authorize.

## 8. Friction reported upward

- **The port is incomplete:** ported `sa_schema.py` cannot import without
  `lib_cli`/`lib_dataset` (v1 files NOT on the allowlist). The build's
  first task must be an owner-sanctioned strip or port of that import.
- **Proposed tangent (not done):** two probes now duplicate
  `read_file`/`build_calls`/`tool_index` verbatim; promote to a shared
  `scripts/lib/lib_corpus.py` before a third probe copies it.
- The corpus is live and grows while probes run (this session writes to
  it); figures drift a few records between runs. Pin a snapshot or re-run
  rather than quoting across days.
