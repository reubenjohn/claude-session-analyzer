# session-analyzer v2 — design brief (Phase 3 synthesis)

**Status: awaiting owner rulings.** Nothing builds until the NEEDS-RULING rows
in `DECISION_LOG.md` are answered; every "proposed" row there may be vetoed.
Base = `designs/DESIGN_C2.md` (Design C revised after the critic panel and
Spike 1), with the panel's grafts and BOTH spikes folded in. Sources:
`designs/PANEL_REPORT.md` (the panel's recommendation and spike results),
`designs/DESIGN_A.md` / `DESIGN_B.md` (graft donors), probes under
`scripts/probes/`.

**Population convention.** Every figure names its population inline. Corpus
figures are one machine's full live corpus, measured 2026-07-28 by the named
probe. The corpus is live and grows while probes run; totals drift a few
records between sweeps — re-run the probe rather than quoting these numbers
for a future corpus.

**Stance (one line).** Mint facts at the grain of the answer: attribution is a
parse-time join materialized as *increment facts*, so the ported engine — zero
bytes changed, proven by Spike 2 — already answers both shipped questions, and
the exact case is measured at 94.98%, not the ~77–84% every earlier document
budgeted.

## 0. What came from where — the graft map

| Element | Origin |
|---|---|
| Increment-fact model, fact grain = answer grain, parse-time attribution, presets-as-data | Design C (base) |
| METRICS single declaration (one name → class, unit; swept test against both ported dicts) | Design B graft |
| Computed denominators — every population line counted from a membership predicate, never prose | Design B graft |
| Machine-readable `cause.reason` codes on every non-exact interval; population lines printed from their counts | Design A graft |
| `interleaved` reason code kept though measured-extinct post-dedup, as the vacuity guard's witness | Design A graft |
| `cause.tool_input_head` dimension; agent attributes declared on generation facts; per-tier cache-write metrics | Panel question-tracer lens |
| Token-relevant contributor definition (MEASURED); dedup-then-locate precondition; chain-integrity restatement + mandatory reconciliation footer; ~5% ambiguous budget | Spike 1 |
| Seam proof (zero engine bytes); double-carrier 2.000000x hazard; `cause.candidates` → evidence; depth-2 nesting rule; one-lane-home rule; residual-aware renderer rule; shrink basis-mixing finding; `sa_schema` import friction | Spike 2 |

## 1. The data model

A **fact** keeps the ported engine's native shape: `{leaf_id: {attributes…,
metrics: {…}, locator, preview, provenance}}` — dotted attributes,
declared-class metrics, evidence excluded from slicing. Two fact kinds:

**Generation fact (kind `generation`)** — one per max-merged `message.id`
group. Locator: `[start, end)` span over the file's assistant-record
subsequence (99.84% contiguous; population 53,855 message.ids, Phase 0 §2)
PLUS the constituent-uuid list PLUS physical line numbers recorded at read
time (unparseable lines are skipped-and-counted, so parsed index ≠ raw line).
Declared attributes: `subagent_info.*` and `locator.source` on every
generation fact, so "which of 42 agents was expensive" is one drill over
`spend`. Metrics: `spend`, `output_tokens`, `context_tokens` (peak), and the
ported schema's input-class metrics by exact name — `input_tokens`,
`cache_creation_input_tokens` (additive), `cache_read_input_tokens` (peak,
never summed; its cost lives inside `spend` only). NEW declarations via
METRICS (below): `cache_write_1h_tokens`, `cache_write_5m_tokens` (additive;
1h + 5m + untiered = `cache_creation_input_tokens` on 47,419/47,419 calls,
ported docstring) — so "which subagent's spend concentrates in cache writes"
is a drill over declared additive metrics (tracer graft, closes Q3's gap).

**Increment fact (kind `increment`) — proposed carrier of `context_delta`**
(RULING PENDING — `DECISION_LOG.md` R1; the fallback model is §3 item 5). One
per attributed component of the interval between consecutive usage-carrying
calls in a lane. Attributes:

- `cause.kind`, vocabulary declared ONCE: `feed_forward | tool_result |
  user_text | ambiguous | shrink | lane_head`. A derivation test sweeps
  presets and renderers, asserts every `cause.kind` literal is in the
  vocabulary AND that the sweep found at least one (vacuity guard). An unknown
  `cause.kind` at parse or render time raises — fail closed, never a skip.
- `cause.reason` (A graft): machine-readable code on every non-exact
  increment — `multi_contributor`, `remainder_negative`, `shrink`,
  `lane_head`, `interleaved`. `interleaved` is measured-extinct post-dedup
  (Spike 1c: 0/53,987 calls) but the code stays: the boundary-partition
  test's vacuity guard asserts the PRE-dedup pathology count is nonzero
  (84 > 0 on this corpus).
- `cause.tool_input_head` (tracer graft — the pivot enabler), stamped at
  parse time: a normalized LOW-CARDINALITY head of the joined
  `tool_use.input` — for Bash the first command token of `input.command`;
  never a full command line, never a file path. Other tools: extension is one
  entry in a declared head-extractor mapping, swept and asserted nonempty.
  Normalization rule is privacy-relevant and NEEDS-RULING (R5).
- `cause.tool_use_id`, `cause.tool_name`, `cause.uuid`, plus inherited
  `subagent_info.*` / `locator.source`. Metric: `context_delta` (signed only
  on `shrink`). Per Spike 2, `cause.candidates` is EVIDENCE (locator/preview
  side), not an attribute — `flatten()` json-dumps a list into one opaque key
  and the dimension dies at 98.3% residual; the drillable scalar is
  `cause.candidate_count`.

**Identity discipline.** Forest-level uuid-keyed dedup at the aggregation
boundary — never per-file, never content-keyed (sibling forks re-bill
identical text). Grouping by embedded `sessionId` + `agentId`, never filename
(1,588 of 1,845 files have non-UUID stems carrying the parent's sessionId,
Phase 0 §5). Sharpened by Spike 1c: **DEDUP-THEN-LOCATE** — within-file uuid
dedup (keep first) is a *precondition* of the interval boundary. Phase 0's 84
interleaved `message.id`s were replayed assistant records; after dedup,
0/53,987 calls interleave, 0 empty / 0 inverted / 0 overlapping intervals
corpus-wide.

**Schema rules (Spike 2, both tested):** dimension attributes nest at most TWO
deep — the ported `flatten()` offers `cause.field` but silently cannot offer
`cause.a.b`, so depth-2 is a declared rule, not an accident. Lane identity
lives in ONE home, `locator.source`, never duplicated as an attribute — the
engine folds the copy into an alias row (wasted offer).

**One metric declaration (B graft; proposed, P1 — never an in-place edit).**
The ported `sa_schema` holds `AGGREGATION` and `METRIC_UNITS` as two
metric-keyed dicts; their key sets coincide 13/13 today and nothing pins that.
v2 adds ONE `METRICS` declaration (name → class, unit); a swept,
vacuity-guarded test asserts both ported accessors agree with it and that the
sweep found ≥ 13 metrics. A new metric touches the v2 declaration only; the
ported file stays verbatim. This also closes the latent metric_units fail-open
defect the misfile lens found (nothing pins the two key sets equal).

## 2. The attribution question that justifies the rewrite

v1 cannot attribute because its generation locator is a single index with no
end and no constituent list, and 0 of its 5,911 tool_result facts carry a
`tool_use_id` though all 5,911 tool_calls do. Phase 0 proved the raw corpus
carries every join key at 100% (59,740/59,740 tool_results carry a
`tool_use_id` that resolves to an earlier `tool_use` in the same file); v1
lost the joins by dropping fields. This model keeps them.

**Population unless stated:** 1,854 files, 229,320 parsed records (2
unparseable lines, 395 within-file duplicate-uuid records dropped), 53,987
calls, 51,960 intervals, 1,821 lanes — full corpus 2026-07-28,
`scripts/probes/probe_interval_boundary.py` (Spike 1).

**The walk, one interval.** (1) Read file F line by line, recording physical
line numbers; skip-and-count unparseable; dedup by uuid within file (keep
first) — THEN locate boundaries. (2) Group assistant records by `message.id`;
merge usage with `max_merge_usage` (field-wise max, recursing into nested
`cache_creation`; 78.05% of 53,855 ids split across records, Phase 0). A call
is usage-carrying iff any merged token field is nonzero. (3) Occupancy
`occ = usage_context(merged)` = input + cache_read + cache_creation — never
`cache_creation` alone as the increment (fails on ~8% of pairs, [MEASURED]).
(4) Interval = records strictly between call N−1's last constituent and call
N's first; `Δocc = occ(N) − occ(N−1)`, signed, unclamped. (5) If `Δocc < 0`:
one `shrink` increment carrying the signed delta, quarantined out of the
attribution view. (6) Else subtract the feed-forward term: mint
`cause.kind = "feed_forward"` with `context_delta = out_prev` (the previous
call's merged `output_tokens`; `Δocc ≥ out_prev` on 97.79% of 45,555 pairs,
[MEASURED]). Remainder `R = Δocc − out_prev`. (7) Enumerate token-relevant
contributors (tool_result user records + user text). (8) Exactly one AND
`R ≥ 0`: mint the exact fact — `cause.kind = "tool_result"`,
`cause.tool_use_id = "toolu_EXAMPLE"`, `cause.tool_name = "Read"`,
`cause.uuid` = the contributor's uuid, `locator.line` = its physical line,
`metrics.context_delta = R`. That fact IS the sentence "this Read result
added R tokens to the window", exact, with evidence one line-open away.
(9) Otherwise: ONE `ambiguous` fact carrying the measured R, candidates as
evidence, `cause.reason` naming why. The walk completes.

**Contributor definition — MEASURED, not proposed.** Exactly-one rates over
the same 51,960 intervals: all non-assistant records 84.41% (reproduces Phase
0's 84.43%) → uuid-bearing 85.94% → **token-relevant 96.92%**. Zero intervals
lack a token-relevant contributor — no delta is ever stranded causeless.
[OPEN] caveat, stays labelled: excluding attachment/system records rests on a
presence-correlation (mean exact R is LOWER when they are present, 1,193 vs
1,741 tokens; population: exact intervals split by their presence) —
consistent with tokenless bookkeeping, not proof.

**The headline (supersedes ENGINE_CONTRACT's ~77%/~23% — blessing is R4):**
**49,352 / 51,960 = 94.98% of intervals attribute exactly** (exactly one
token-relevant contributor AND `R ≥ 0` AND `Δocc ≥ 0`). Disjoint failures:
`multi_contributor` 3.08%, `shrink` (Δocc<0) 1.59%, `remainder_negative`
(R<0) 0.35%, zero-token-relevant 0.00%. The ambiguous bucket is ~5% of
intervals, not the ~15–23% budgeted. Estimated attribution is NOT promised;
the ambiguous bucket stays, one bucket, never silently spread.

**The invariant, restated honestly (Spike 1d).** C's conservation test was a
tautology as written — it held 1,821/1,821 lanes by construction, since every
branch books exactly Δocc. The real claim is **CHAIN INTEGRITY**: rebuild each
lane's telescoping chain from its increment facts alone; the counterfactual
(dropping quarantined increments from the chain) breaks 187/1,821 = 10.27% of
lanes, 127 by >10k tokens — so the test CAN fail. It catches dropped,
reordered, or double-counted intervals. It cannot catch a wrong-but-plausible
attribution inside one interval (§5, honest gaps).

**Reconciliation footer — MANDATORY on every attribution view:** per lane and
corpus-wide, Σ exact + Σ feed_forward + Σ ambiguous + Σ lane_head +
Σ quarantined = final occupancy, with quarantined (−3.91M context tokens
corpus-wide, Spike 1) and lane_head masses included, never dropped, printed
from reason-code totals. Global buckets, same sweep: exact 82.8M,
feed-forward 47.6M, ambiguous 7.9M + 0.24M negative-remainder, quarantined
−3.9M.

**The seam is proven (Spike 2, `scripts/probes/probe_engine_seam.py`).**
Population: 1,856 files, 1,823 lanes, 158,987 facts (recorded as 53,946
generation + 105,040 increment — the components sum one short of the recorded
total; the corpus grew mid-sweep, which is why these numbers are re-run, not
quoted). The recommended fact shape fed the PORTED engine with **zero engine
bytes changed**: chain integrity passed integer-exact (root `resolve_path`
over increments = 188,975,626 = Σ lane final occupancy); every grafted axis
surfaces natively in `discover_dimensions` — `cause.kind` (score .4646),
`cause.tool_name` (.3261), `cause.tool_input_head` (.2732), `agent_id`
(.0998), `lane` (.0263). Mass shares of the chain: tool_result 42.72%,
lane_head 28.56%, feed_forward 25.28%, ambiguous 4.30%, user_text 1.21%,
shrink −2.07%. **PURPOSE's flagship pivot is real:** unprompted, the engine
ranked the input-head axis above the agent axis — the top input-head bucket
carries 10.77% of chain mass vs the hottest single agent's 0.24% (~44x;
populations: 105,040 increments / 1,590-fact agent card). Spend answers with
zero new code too (root 1.018B base-token-equivalents over 53,946 generation
facts), and the top spend agent ≠ the top context agent.

### 2a. Seam frictions — the build must handle these (gap closed here)

PANEL_REPORT §6 flagged these as "not yet folded into DESIGN_C2"; the C2
amendment landed after the report was written, and THIS brief carries the
authoritative list either way:

1. **Port friction:** ported `sa_schema.py` does `from lib import lib_cli,
   lib_dataset` — neither on the read allowlist, so the engine cannot import
   standalone. The spike stubbed them with zero engine bytes changed; the
   build's FIRST task is the owner's answer to R6 (allowlist-and-port vs
   sanctioned mechanical strip).
2. **Double-carrier hazard, measured:** `context_delta` on both fact kinds in
   one unpredicated map totals exactly 2.000000x the truth, AND the mixed
   root's shape-containment filter hides every `cause.*` axis — wrong and
   blind at once. Presets MUST lead with the `kind` membership predicate
   (restores the exact total). This is the owner-ruling evidence for R1.
3. **Shrink basis-mixing:** shrink's signed mass demotes `cause.kind` — the
   #1-ranked dimension — to a count-basis concentration while siblings rank
   on mass. Recommended: exclude `shrink` from the `context` preset's
   predicate; its mass stays footer-mandatory, so honesty survives (P2).
4. **Renderer rule:** `top_key` / `top_metric_share` can BE the residual
   bucket (observed: residual at 59.94% printed as "top"). Never render
   `top_key` as the top bucket without residual handling; a top-non-residual
   engine field would be an engine change only a ruling can authorize (P3).
5. **Depth-2 rule:** `flatten()` offers dotted attributes at most two deep;
   deeper nesting is silently un-offerable — declared and tested, not
   discovered again.
6. **List-valued attributes die:** json-dumped to one opaque key
   (`cause.candidates` rejected at 98.3% residual) — lists are evidence,
   scalars are dimensions (`cause.candidate_count`).
7. **One lane home:** duplicating lane identity on an attribute and
   `locator.source` costs a folded alias row.

## 3. Divergences from v1's [OPEN] choices — item by item

1. **Kept unchanged (P7):** score = stat × cover, cover as fact count,
   residual unification, purity boundary, fail-closed unclassified metric,
   absent-not-defaulted statistic fields, max-merge reconciliation. No new
   measurement, and these survived mutation testing — challenging them on
   argument alone is the recorded failure mode.
2. **§4 subtract-then-split:** adopted, materialized at parse time
   (`remainder_negative` 0.35% of 51,960 intervals gets no feed-forward
   fact; the whole Δocc routes to ambiguous — no honest split of a negative
   remainder).
3. **§4 one ambiguous bucket:** kept as ONE bucket in every total, annotated
   with `cause.reason` codes (A graft) so populations are computed, never
   prose.
4. **Contributor definition:** RESOLVED by Spike 1 measurement —
   token-relevant (§2); headline blessing is R4.
5. **§5 carrier move [R1 — NEEDS RULING].** `context_delta` moves from
   generation facts to increment facts; `spend` stays on generations. The
   misfile lens split makes this rulable: one-fact-per-token-per-metric is
   [ARITHMETIC]; WHICH kind carries the mass is [RULING]. Spike 2 measured
   what the discipline prevents (2.000000x + blind root). **Fallback if the
   owner keeps §5's letter:** fat generation facts — `cause.*` become
   attributes of the generation they explain; the feed-forward split becomes
   two declared additive metrics (`context_delta_feedforward` +
   `context_delta_attributed` = `context_delta`, a swept identity);
   `ambiguous` becomes an attribute value, not a fact. Survives: chain
   integrity, reason codes, METRICS sweep, fail-closed `cause.kind`,
   input-head drills. Lost: an interval's mass cannot split across rows; the
   footer sums attribute-partitioned generations. (Design A's third option —
   a NEW metric `context_added` on contributor facts — is on R1's table too.)
6. **METRICS single declaration (P1).** Fallback: keep the two ported dicts
   plus a pinned key-set-equality test.
7. **Presentation:** a view is a preset — data, not code: `{membership
   predicate, default metric, starting path}`; denominators computed from the
   predicate (B graft); a preset naming an unknown metric dies in
   `statistic_for`; unknown `cause.kind` fails closed. Two presets:
   `context`, `spend`. Renderer rule per §2a item 4.
8. **NEW [OPEN] — shrink's home (P2):** recommended exclusion from the
   `context` preset's predicate, mass footer-mandatory.

## 4. Deliberately not building

No estimator for multi-contributor intervals — estimated attribution is not
promised in build v1; the ambiguous bucket stays. No chars→tokens anywhere
(1.8x measured spread; a confident wrong number). No dollars. No TIME view —
locators keep timestamps and spans so TIME lands later without reparsing. No
cross-file window naming: the file=lane reset stands until the
continuation-head probe (R2) settles it; `lane_head` holds that honesty
meanwhile (28.56% of chain mass — the single biggest honesty bucket). No full
tool inputs as a dimension — normalized head only (R5). No per-record
attachment token measurement in v1 (the [OPEN] caveat stays labelled). No
HTML layer, live monitoring, parity harness, or view registration tables.

## 5. Honest gaps — labelled, not hidden

1. **Chain integrity cannot catch a wrong-but-plausible attribution WITHIN an
   interval** — a misclassified contributor yields an exact-labeled fact for
   the wrong cause. 94.98% is structural exactness, not verified causal truth.
2. **Attachment caveat:** if some attachment type does inject prompt tokens,
   that mass lands on the sole token-relevant contributor — labeled exact.
   The exclusion rests on a correlation, not a proof.
3. **The carrier ruling is pending (R1);** the fallback loses
   ambiguous-as-a-fact.
4. **`tool_input_head` extraction is hand-curated:** the sweep proves the
   mapping is declared and used, not that `env FOO=1 cmd`-shaped heads come
   out right.
5. **The engine cannot import standalone until R6 is answered** — the spike's
   stub is not a build.
6. **Corpus figures drift:** every number above is one machine, 2026-07-28;
   the seam-spike component counts already show single-record drift within a
   session.

**Every open or disputed choice is a numbered row in `DECISION_LOG.md`:
6 NEEDS-RULING rows block the build; 9 proposed rows may be vetoed.**
