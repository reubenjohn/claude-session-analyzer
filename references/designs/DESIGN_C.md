# Design brief C — unconstrained stance

**Stance (one line):** Mint facts at the grain of the answer — attribution is a
parse-time join materialized as *increment facts*, so the ported engine, unmodified,
already knows how to ask every question the rewrite exists to answer.

**What I'd attack in the obvious design** (independence marker): the obvious move
is "keep v1's fact kinds, add `tool_use_id` to tool_result facts, and do the
attribution join at query time." I'd attack it on three points: (a) a query-time
join re-derives interval structure inside the presentation layer, per question —
which is exactly v1's 40-hand-tables disease wearing a new hat; (b) the ambiguous
remainder then lives in no fact, so no schema-derived test can assert the
reconciliation Σ(shown) + Σ(ambiguous) + Σ(quarantined) = final occupancy — the
honesty surface becomes prose; (c) when the join fails at query time the tempting
patch is the chars→tokens estimator, the single most-falsified move in this domain
(1.8x spread, [MEASURED]). The other obvious shape — a general event-log/SQL
warehouse — buys generality nobody asked for and puts the purity boundary at risk.

## 1. The data model

A **fact** keeps the ported engine's shape: `{leaf_id: {attributes…, metrics: {…},
locator, preview, provenance}}` — dotted attribute namespace, declared-class metrics,
evidence fields excluded from slicing (Filter A). The engine is the fixed point; the
design freedom is *which facts get minted* and *what the locator carries*. Three
commitments, each forced by a Phase 0 number:

- **Call fact (kind `generation`).** One per max-merged `message.id` group.
  Locator: `[start, end)` span over the file's **assistant-record subsequence**
  (99.84% contiguous) **plus the constituent record-`uuid` list** (the lossless form
  — covers the 84 interleaved ids) **plus physical line numbers** recorded at read
  time (unparseable lines skipped-and-counted, so parsed index ≠ raw line). Metrics:
  `spend`, `output_tokens`, `context_tokens` (peak), input-class tokens. v1's
  single-index-no-end locator cannot express 78.05% of generations; this one
  expresses all of them.
- **Increment fact (kind `increment`) — the new carrier of `context_delta`.** One
  per attributed *component* of the interval between consecutive usage-carrying
  calls in a lane. Attributes: `cause.kind` (`feed_forward` | `tool_result` |
  `user_text` | `ambiguous` | `shrink`), `cause.tool_use_id`, `cause.tool_name`,
  `cause.uuid`, `cause.candidates` (ambiguous only), plus `locator.source` /
  `subagent_info` inherited from the lane. Metric: `context_delta` (signed only on
  `shrink`). Invariant, schema-derivable and testable: **the increment facts of a
  lane partition its deltas — Σ`context_delta` over all of them telescopes to the
  lane's final observed occupancy.**
- **Identity discipline at the aggregation boundary.** Forest-level uuid-keyed
  dedup (within-file dups 0.19%, cross-file replays 1.35%, never content-keyed —
  sibling forks re-bill identical text). A file is not a session: 1,588 of 1,845
  files have non-UUID stems carrying the *parent's* `sessionId`; grouping is by
  embedded `sessionId` + `agentId`, never filename. Unknown record types (21 in the
  wild) are tolerated, counted, and granted no identity.

Why this shape: the two shipped questions are drills over additive masses, and the
engine's native operation is "rank dimensions over a member set, then resolve a
path." Making the attributable component a *fact* means "where is my context going"
is literally `discover_dimensions(facts, increments, "context_delta")` — no new
engine code, no view registration, and the ambiguous bucket is a bucket, not a
footnote. The injected subtree (~95% of observed chars, zero mass) still exists as
`injected` facts for the chars view, permanently labeled in chars; the inverted
tree is handled by *which facts carry which metrics*, not by renderer heroics.

## 2. The attribution walkthrough (raw records → "this tool result added N tokens")

Grounded in PHASE0_MEASUREMENT.md; every field named. Take one interval in one file.

1. **Read** file `F` under the corpus root. Per line: record the **physical line
   number**, parse JSON; unparseable → skip and count. Dedup records by top-level
   `uuid` within the file, then forest-wide at the aggregation boundary.
2. **Assemble call N−1 and call N.** Group assistant records (`type ==
   "assistant"`) by `message.id` over the assistant-record subsequence. Merge each
   group's `message.usage` with `max_merge_usage` — field-wise max over
   `input_tokens`, `output_tokens`, `cache_read_input_tokens`,
   `cache_creation_input_tokens`, recursing into
   `usage.cache_creation.ephemeral_1h_input_tokens` / `ephemeral_5m_input_tokens`
   (80.5% of ids are split; 73.0% of those disagree on `output_tokens`). A call is
   usage-carrying iff any merged field is nonzero.
3. **Occupancy.** `occ(N) = usage_context(merged_N)` = `input_tokens +
   cache_read_input_tokens + cache_creation_input_tokens`. The carry is per-lane,
   reset at file start. NOT `cache_creation_input_tokens` — that identity fails on
   ~8% of pairs and double-counts nearly half of cached tokens [MEASURED].
4. **The interval.** `Δocc = occ(N) − occ(N−1)` (= `context_delta(prev, cur)`,
   signed, unclamped). The interval's records are those strictly between call
   N−1's last constituent `uuid` and call N's first, in file order.
5. **Branch on sign.** If `Δocc < 0`: mint one increment fact, `cause.kind =
   "shrink"`, `metrics.context_delta = Δocc`, quarantined out of the attribution
   view (a growth question has no slot for removal); stop.
6. **Subtract the feed-forward term.** `out_prev = merged_{N−1}.output_tokens`
   (the previous turn's output feeds forward into the next prompt; `Δocc ≥
   out_prev` on 97.79% of 45,555 pairs). Mint increment fact #1: `cause.kind =
   "feed_forward"`, `cause.message_id = message.id(N−1)`, `metrics.context_delta =
   out_prev`. Edge rule [OPEN]: if `Δocc < out_prev` (the 2.21%), mint NO
   feed-forward fact and send the whole `Δocc` to `ambiguous` — there is no honest
   split of a remainder that would go negative.
7. **Enumerate contributors.** Non-assistant records in the interval (zero
   intervals are empty — every delta has a candidate cause). For each user record,
   walk `message.content` (string or block list — both routine): a block with
   `type == "tool_result"` carries `tool_use_id` (present 59,740/59,740 =
   100.00%); resolve it to the earlier `tool_use` block **in the same file**
   (resolvable 100.00%), which yields `name` (→ `cause.tool_name`), the tool
   `input` (evidence: e.g. the `file_path` a Read dumped), and the producing call's
   `message.id`. Metadata records (uuid-less bookkeeping) carry no tokens — every
   identifiability failure in Phase 0 §4 is one of them; every conversational
   contributor is identifiable.
8. **Exactly-one case (84.43% of 51,933 intervals, and identifiability never
   subtracts from it).** Remainder `R = Δocc − out_prev` attributes EXACTLY. Mint
   increment fact #2: `cause.kind = "tool_result"` (or `"user_text"`),
   `cause.tool_use_id = "toolu_EXAMPLE"`, `cause.tool_name = "Read"`, `cause.uuid`
   = the contributor record's `uuid`, `locator.line` = its physical line,
   `metrics.context_delta = R`. **That fact IS the sentence "this tool result
   added R tokens to the window"** — population: single-contributor intervals of
   lane L; label: exact, not estimated.
9. **Otherwise (~15–23% depending on contributor definition).** Mint one fact,
   `cause.kind = "ambiguous"`, `cause.candidates` = the contributors' uuids,
   `metrics.context_delta = R`. One bucket, candidates named, never spread.
10. **Query.** `resolve_path(facts, [("cause.tool_name", "Read")],
    "context_delta")` → `{members, total: N, total_statistic: "sum", n_valued}`;
    `discover_dimensions` at the same node offers the next slice (`cause.kind`,
    `subagent_info.agent_id`, `locator.source`, …). Drill to evidence:
    `locator.line` opens the transcript at the proving record.

The walk completes. Verdict: exact attribution is buildable from what the raw
corpus measurably carries; v1 lost the joins by dropping fields, not because the
data lacks them.

## 3. Divergence from v1's [OPEN] choices, item by item

- **Score = stat × cover, cover as fact count, residual unification, purity
  boundary, fail-closed unclassified metric, absent-not-defaulted statistic
  fields:** kept, unchanged. I have no new measurement, and these survived
  mutation testing; challenging them on argument alone is the recorded failure mode.
- **§4 subtract-then-split:** adopted, but *materialized at parse time* as
  feed-forward increment facts instead of computed at query time. Divergence: the
  rule becomes data, so a schema-swept test can assert the telescoping identity.
- **§4 one ambiguous bucket:** adopted as `cause.kind = "ambiguous"` — a fact,
  so it appears in every drill with its measured total, not as renderer prose.
- **§5 carrier of `context_delta` moves from generation facts to increment facts**
  (needs an owner ruling; see misfile #1). `spend` stays on generation facts only.
- **New [OPEN] proposal — contributor definition:** Phase 0 counted ALL
  non-assistant records as contributors (84.43% exactly-one). Metadata records
  carry no tokens, so counting only token-relevant records (tool_result user
  records, user text) should RAISE the exact share — but whether attachments and
  system records add prompt tokens is unverified. Proposal: a Phase-0b probe
  measuring the exactly-one rate over token-relevant contributors; ship v1 of the
  build on the conservative measured definition, upgrade only on the number.
- **Presentation:** a "view" is a *preset* — data, not code: `{membership
  predicate, default metric, starting path}`. Denominators are computed from the
  membership predicate (v1's were hand-written prose claims nothing checked).
  Tables render engine output plus `metric_units`; adding a metric touches
  `AGGREGATION` (+ unit); adding a dimension is stamping an attribute at parse
  time; a preset naming an unknown metric dies in `statistic_for`. Zero
  fail-silent surfaces, two presets: `context` (increments), `spend` (generations).

## 4. Deliberately not building

No estimator for multi-contributor intervals (no honest one exists). No
chars→tokens anywhere. No dollars. No TIME view — but every fact's locator keeps
timestamps and spans so TIME can be added without reparsing. No cross-file window
naming (peaks still reduce to `None` at nodes; grouping a peak stays unsolved and
says so). No HTML report layer in v1 of the build. No live monitoring. No parity
harness, no view registration tables.

## Suspected misfiles

1. **§5 "`spend` and `context_delta` exist ONLY on generation facts" [ARITHMETIC].**
   The arithmetic core is *each token counted by exactly one fact* (no inflated
   denominator, no double count). WHICH fact kind carries the mass is a design
   choice — my model moves `context_delta` to increment facts while preserving the
   telescoping sum. Proposed re-tag: partition/no-double-count law [ARITHMETIC] +
   carrier choice [RULING].
2. **§6 "the carry resets to an empty window at the start of EVERY file"
   [ARITHMETIC].** "A delta between unrelated windows is meaningless" is
   arithmetic; "a file boundary starts a new lane" is a modeling choice that the
   contract itself elsewhere denies ("a window is not a file" — bg/fork continue
   one window in a new file). A continuation file's first call currently books its
   entire re-established occupancy as one giant unattributable delta. Proposed:
   re-tag the reset [OPEN] with a measurement task — do fork-continuation files'
   first calls report occupancy ≈ the parent lane's last?

## Weakest point

The carrier move (misfile #1) touches a pinned test and an [ARITHMETIC]-tagged
invariant — if the owner rules against it, my model degrades to fat generation
facts with `cause.*` attributes and loses the clean ambiguous-as-bucket property.
And the whole exactness claim rests on the interval components *partitioning*
`Δocc`: the 2.21% `Δocc < out_prev` edge, the shrink quarantine, and the 0.16%
interleaved generations all shunt mass into buckets the default view must surface
via one reconciliation footer (Σ shown + Σ ambiguous + Σ quarantined = final
occupancy). If a critic finds a record shape that breaks the partition — e.g. a
usage-less assistant record that genuinely consumed window — the "exact" label on
step 8 is the first thing that has to be withdrawn.
