# Design brief C2 — C revised after the panel and two spikes

**Stance (one line):** Mint facts at the grain of the answer — attribution is a
parse-time join materialized as *increment facts* — and the spikes measured it:
exact case ~95% (not C's ~77–84%), and the ported engine consumed the shape
unchanged.

## 1. The data model

A **fact** keeps the ported engine's shape: `{leaf_id: {attributes…, metrics…,
locator, preview, provenance}}` — dotted attributes, declared-class metrics,
evidence excluded from slicing. Fact kinds:

- **Generation fact (kind `generation`).** One per max-merged `message.id`
  group. Locator as in C: assistant-subsequence `[start, end)` span +
  constituent-uuid list + physical lines. **`subagent_info.*` and
  `locator.source` are declared on every generation fact** — "which of 42
  agents was expensive" is one drill over `spend`. Metrics:
  `spend`, `output_tokens`, `context_tokens` (peak), and by exact ported name
  `input_tokens`, `cache_creation_input_tokens` (additive);
  `cache_read_input_tokens` is `peak`, never summed — its cost lives inside
  `spend`. NEW, via METRICS below: `cache_write_1h_tokens`,
  `cache_write_5m_tokens` (additive; 1h + 5m + untiered =
  `cache_creation_input_tokens`, 47,419/47,419 calls), so cache-write
  concentration per subagent is a drill over additive metrics.
- **Increment fact (kind `increment`) — carrier of `context_delta`** (ruling
  pending, §3.4). One per attributed component of a lane's inter-call
  interval. Attributes:
  - `cause.kind`, vocabulary declared ONCE: `feed_forward | tool_result |
    user_text | ambiguous | shrink | lane_head`. Derivation test: every
    literal in presets/renderers is in the vocabulary and the sweep found ≥ 1
    (vacuity guard); unknown values raise — fail closed.
  - `cause.reason` (A graft): machine-readable code on every non-exact
    increment — `multi_contributor`, `remainder_negative`, `shrink`,
    `lane_head`, `interleaved`. Population lines print from reason-code
    counts, never prose. `interleaved` is extinct post-dedup (Spike 1c); the
    code stays for the partition test's vacuity guard (84 pre-dedup).
  - `cause.tool_input_head` (the panel's decisive gap), stamped at parse time:
    a normalized LOW-CARDINALITY head of the joined `tool_use.input` — for
    Bash the first command token of `input.command`; never a full command
    line or file path. Other tools: absent in v1; extension = one entry
    in a declared head-extractor mapping (swept, nonempty). PURPOSE's flagship
    pivot rides this axis — proven live in Spike 2 (§2).
  - plus C's `cause.tool_use_id`, `cause.tool_name`, `cause.uuid`, inherited
    `subagent_info.*` / `locator.source`. Metric: `context_delta` (signed only
    on `shrink`). Per Spike 2, `cause.candidates` moves to evidence — flatten
    json-dumps lists into one opaque key (98.3% residual); the drillable
    scalar is `cause.candidate_count`.
- **Identity discipline.** As in C (forest-level uuid-keyed dedup, never
  content-keyed; grouping by `sessionId` + `agentId`, never filename), plus
  Spike 1c's **DEDUP-THEN-LOCATE**: within-file uuid dedup (keep first) is a
  precondition of the boundary — the 84 interleaved ids were replays;
  0/53,987 post-dedup.
- **Schema rules (Spike 2):** dimensions nest at most TWO deep (`cause.a.b`
  is silently un-offerable — depth-2 is a declared, tested rule); lane
  identity lives ONLY in `locator.source` (a duplicate attribute folds into
  an alias).
- **One metric declaration (B graft; decision-log, never an in-place
  edit).** AGGREGATION and METRIC_UNITS are two metric-keyed dicts, key sets
  coinciding 13/13 unpinned — C's "touches AGGREGATION (+ unit)" was two
  declarations. v2 adds ONE `METRICS`
  declaration (name → class, unit); a swept, vacuity-guarded test asserts both
  ported accessors agree and found ≥ 13 metrics. A new metric touches the v2
  declaration only; the ported file stays verbatim. [needs OWNER RULING] —
  fallback: the two dicts plus a pinned key-set-equality test.

## 2. The attribution walkthrough — re-grounded in the spikes

Population unless stated: **1,854 files, 229,320 records, 51,960 intervals,
1,821 lanes** — full corpus, 2026-07-28,
`scripts/probes/probe_interval_boundary.py` (Spike 1). Steps as in C —
**dedup within file, then locate boundaries**; max-merge by `message.id`;
`occ = usage_context`; interval = records strictly between call N−1's last
constituent and call N's first. Revisions:

- **Contributor definition: MEASURED.** Exactly-one rates, same 51,960
  intervals: all non-assistant 84.41% → uuid-bearing 85.94% → **token-relevant
  (tool_result user records + user text) 96.92%**, and zero intervals lack
  one — build v1 ships on this definition.
- **The exact case:** one token-relevant contributor AND R = Δocc − out_prev
  ≥ 0 AND Δocc ≥ 0 → **49,352/51,960 = 94.98%** attribute exactly. Failures
  disjoint: `multi_contributor` 3.08%, `shrink` (Δocc < 0) 1.59%,
  `remainder_negative` 0.35%, zero-token-relevant 0.00%. The minted fact
  (`cause.kind = "tool_result"`, `cause.tool_use_id = "toolu_EXAMPLE"`,
  `cause.tool_name = "Read"`, `metrics.context_delta = R`) IS "this tool
  result added R tokens" — the walk completes.
- **[OPEN] caveat:** attachment/system exclusion rests on a
  presence-correlation: mean exact R is LOWER with them present (1,193 vs
  1,741; exact intervals by presence) — not proof.
- **The invariant, restated** (C's version was a tautology — 1,821/1,821 by
  construction). The real claim is **CHAIN INTEGRITY**:
  rebuild each lane's telescoping chain from its increment facts alone; the
  counterfactual — dropping quarantined increments — breaks 187/1,821 = 10.27%
  of lanes. It catches dropped/reordered/double-counted intervals only.
- **Reconciliation footer (mandatory):** Σ exact + Σ feed_forward + Σ ambiguous
  + Σ lane_head + Σ quarantined = final occupancy, per lane and corpus-wide —
  incl. quarantined (−3.91M, Spike 1) and lane_head, from reason-code totals.

**Seam spike (Spike 2)** — `scripts/probes/probe_engine_seam.py`, full corpus
2026-07-28; 158,987 facts (53,946 generation + 105,040 increment), 1,823
lanes. Zero engine bytes changed; chain integrity integer-exact (root
`resolve_path` over increments = 188,975,626 = Σ lane final occupancy); the
flagship pivot is REAL — it ranked `cause.tool_input_head` (score .2732)
above `agent_id` (.0998) unprompted: top head bucket 10.77% of chain
mass vs top agent 0.24%, ~44x. Shares by `cause.kind`: tool_result 42.72,
lane_head 28.56, feed_forward 25.28, ambiguous 4.30, user_text 1.21, shrink
−2.07 (% of chain mass).

## 3. Divergence from v1's [OPEN] choices — decision log

1. **Kept unchanged:** score = stat × cover, cover as fact count, residual
   unification, purity boundary, fail-closed unclassified metric, absent-not-
   defaulted fields, max-merge — no new measurement.
2. **§4 attribution rules:** subtract-then-split adopted, materialized at
   parse time (`remainder_negative` 0.35% of 51,960 intervals, Spike 1); ONE
   ambiguous bucket kept in every total, annotated with `cause.reason` codes.
3. **Contributor definition:** RESOLVED by Spike 1; token-relevant, per §2.
4. **§5 carrier move [needs OWNER RULING].** `context_delta` on increments;
   `spend` on generations. Spike 2: double-carrier in one unpredicated map =
   exactly 2.000000x, AND the mixed root's shape-containment filter
   hides every `cause.*` axis — presets MUST lead with the kind predicate; an
   unpredicated root is wrong and blind. **Fallback if the ruling keeps
   `context_delta` on generations:** fat generation facts — `cause.*` become
   attributes; the feed-forward split becomes two declared additive metrics
   (`context_delta_feedforward` + `context_delta_attributed` =
   `context_delta`, a swept identity); `ambiguous` becomes an attribute
   (candidates only as evidence). Survives: chain integrity, reason-code
   lines, METRICS sweep, `tool_input_head` drills. Lost: an interval's mass
   cannot split across rows; the footer sums attribute-partitioned
   generations.
5. **Presentation:** a view is a preset — data, not code: `{membership
   predicate, default metric, starting path}`; denominators computed from the
   predicate; a preset naming an unknown metric dies in `statistic_for`. Two
   presets: `context`, `spend`. Renderer rule (Spike 2): `top_key` can BE the
   residual bucket (observed at 59.94% printed as "top") — never render it as
   the top bucket without residual handling; a top-non-residual engine field
   is an [OPEN] change needing a ruling.
6. **NEW [OPEN] — shrink's home (Spike 2).** Shrink's signed mass demotes
   `cause.kind` — the #1-ranked dimension — to a count-basis concentration
   while siblings rank on mass: silent basis mixing at one node. Options: a
   sign attribute; a quarantine kind outside the default preset;
   accept-and-render `dist_basis_reason`. Recommended: exclude `shrink` from
   the `context` preset's membership — its mass is footer-mandatory anyway,
   keeping the default ranking on one basis without losing the mass.

## 4. Deliberately not building

No estimator for multi-contributor intervals; no chars→tokens; no dollars. No
TIME view (locators keep timestamps/spans). No cross-file window naming —
file=lane stands until the continuation-head probe (first call of a
continuation ≈ parent lane's last occupancy?) settles it; `lane_head` holds
that honesty. No full tool inputs as a
dimension — head only. No per-record attachment token measurement in v1. No
HTML layer, live monitoring, parity harness, or view registration tables.
Build precondition (Spike 2): ported `sa_schema.py` imports unported
`lib_cli`/`lib_dataset` — it cannot import standalone; port or strip that
import (the spike stubbed it).

## Suspected misfiles — the panel's verdicts, awaiting ruling

Referenced, not applied: **§5** = "each token counted by exactly one fact per
metric" [ARITHMETIC] + carrier choice [RULING] (§3.4 waits on it); **§6** =
"never difference two windows" [ARITHMETIC] + file=lane [OPEN] (the
continuation-head probe settles it); **§4** quarantine's [ARITHMETIC] head
covers only post-shrink summation — disposition [OPEN] per its own
parenthetical.

## Weakest point

Boundary and seam are measured; what remains: (1) chain integrity
cannot catch a wrong-but-plausible attribution *within* an interval — a
misclassified contributor yields an exact-labeled fact for the wrong cause;
94.98% is structural exactness, not verified causal truth. (2) If an
attachment type does inject prompt tokens, that mass lands on the sole
token-relevant contributor — labeled exact. (3) The carrier ruling is
pending; the fallback loses ambiguous-as-a-fact. (4) `tool_input_head` heads
are hand-curated; Spike 2 proves the axis ranks, not that every head is right.

## Changes from DESIGN_C

1. Contributors → token-relevant: exact 84.43%→94.98%, ambiguous ~15–23%→~5%
   (51,960 intervals) — Spike 1a/1b.
2. Dedup-then-locate precondition; `interleaved` only a vacuity-guarded reason
   code (0/53,987 post-dedup, 84 pre) — Spike 1c.
3. Chain integrity + quarantine-drop counterfactual (187/1,821 lanes) +
   mandatory footer — Spike 1d.
4. One v2 METRICS declaration + `cause.kind` derivation test, fail-closed —
   complexity auditor (B graft).
5. `tool_input_head`, agent attrs on generations, per-tier cache-write
   metrics — question-tracer.
6. Reason codes + computed population lines — A graft; misfiles cite panel
   adjudications.
7. Carrier fallback spelled out — contract skeptic.
8. Spike 2: seam validated (zero engine bytes; chain integer-exact; pivot
   ~44x); candidates → evidence + `candidate_count`; shrink [OPEN], preset
   exclusion; depth-2 + one lane home; residual-aware `top_key`;
   double-carrier 2.000000x; port precondition.
