# DESIGN_B — join-first / relational

**Stance:** The corpus normalizes at parse time into a small set of keyed relations, and attribution IS a join over declared foreign keys — never a positional computation bolted on at query time.

## 1. The data model

"Relational" is a modeling discipline, not a dependency: a relation is a list of plain dict rows plus one entry in a declared `RELATIONS` registry (name → key columns, and per-column role: `key` / `fk→target` / `dimension` / `metric` / `evidence`). No sqlite, no ORM; the ported engine's purity contract is untouched. One parse sweep per file (physical `line_no` recorded at read time; the Nth parsed record is not raw line N) emits six relations:

- **record** — the parse ledger. Key `(file_id, line_no)`. Columns: `uuid` (nullable — 18,115 bookkeeping records carry none and get no identity), `record_type` (21 in the wild; unknown types tolerated, never granted identity), `parent_uuid`, `timestamp` (stored for the deferred TIME build, unused now).
- **call** — one API generation. Key `(file_id, message_id)`. `usage` = `max_merge_usage` over constituent records (mandatory: 78.05% of 53,855 ids split across records). Locator = `span` `[start, end)` over the file's assistant-record subsequence (99.84% contiguous) **plus** `constituent_uuids` — the lossless pair; the list, not the span, is authoritative for the 84 interleaved ids and for metadata landing physically inside a run. `seq` = ordinal among the file's usage-carrying calls (the lane). Derived metric columns: `occupancy` (= `usage_context`), `spend` (= `usage_spend`), `context_delta` vs the previous lane call (signed, unclamped).
- **block** — content blocks. Key `(uuid, ordinal)`. `block_type`, `chars`; `tool_use` blocks carry their own `id` and `name`; `tool_result` blocks carry `tool_use_id` and `is_error`.
- **tool_invocation** — projection of `tool_use` blocks. Key `tool_use_id`. `fk→call` (the generation that issued it), `tool_name`, input preview (evidence).
- **interval** — key `(file_id, seq)`. `fk prev_call`, `fk next_call`, `delta` (= next call's `context_delta`), `attributable` = `delta − prev.output_tokens` (the feed-forward subtraction), `status ∈ {exact, ambiguous, quarantined, file_head}`.
- **contribution** — key `(interval_id, uuid)`. `kind ∈ {tool_result, user_text, metadata}`; tool_result rows carry `tool_use_id` (`fk→tool_invocation`, total: 59,740/59,740 resolve).

**The fact layer sits downstream; the ported engine is not rewritten.** A fact is a denormalized row generated from a declared join path over `RELATIONS`: dimensions are columns plus followed fks; the locator is `(file_id, line_no)` or `(file_id, span, constituent_uuids)` — never a bare index. tool_result facts thus carry `tool_use_id` and `tool_name` as first-class dimension columns, fixing v1's 0-of-5,911 loss at the source. `spend`/`context_delta` exist only on generation facts (§5). Injected facts keep `locator.source` as their only agent axis; the inverted tree (~95% of chars, zero mass) renders as an evidence panel keyed by locator, never as rows in a mass table.

**Dedup:** forest-level, uuid-keyed, never content-keyed, at the aggregation boundary (within-file dup 0.19%; cross-file replay 1.35% of distinct uuids). An attribution fact inherits its interval's `next_call` uuid as identity, so replayed intervals dedup by the same key for free.

**Presentation:** a view is a stored query — `(population predicate over relations, metric, optional preset drill path)` — no registration surface. Rendering is generated from metric declarations (class → legal reduction and ordering, unit noun) plus `RELATIONS` column metadata. The denominator line is **computed** by counting the population predicate's matches — replacing v1's five hand-written prose claims nothing checked. A metric is one declaration row; a dimension is one column entry; tests sweep both registries, vacuity-guarded (§8).

## 2. The walkthrough: raw records → "this tool result added N tokens"

One interval, every field named. Percentages: PHASE0_MEASUREMENT.md (1,845 files, 228,738 records, one machine, 2026-07-28).

1. **Read** file F line by line; store `line_no` at read time; skip-and-count the unparseable. Per line read `type`, `uuid`, `parentUuid`, `timestamp`, `message`.
2. **Build calls:** group assistant records by `message.id`; merge `message.usage` field-wise max over `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, recursing into `cache_creation.ephemeral_1h_input_tokens` / `cache_creation.ephemeral_5m_input_tokens`. Record each call's `span` + `constituent_uuids`. A call is usage-carrying iff any merged token field is nonzero; `seq` numbers those in file order.
3. **Occupancy:** `occupancy(seq) = input_tokens + cache_read_input_tokens + cache_creation_input_tokens` (`usage_context`). Never `cache_creation_input_tokens` as the increment — the identity fails on ~8% of pairs and double-counts nearly half of all cached tokens.
4. **Delta:** `delta = occupancy(N) − occupancy(N−1)`, signed, unclamped. If `delta < 0`: `status = quarantined`, no attribution row (no slot for removal). If N is the file's first call: `status = file_head` (see misfile 2 — inherited occupancy, not growth).
5. **Feed-forward:** `attributable = delta − output_tokens(N−1)` (the previous call's merged `output_tokens` feeds forward into the next prompt; `Δocc ≥ out_prev` on 97.79% of 45,555 pairs [MEASURED]).
6. **Contributors:** contribution rows are records positioned strictly between `max(position of prev_call.constituent_uuids)` and `min(position of next_call.constituent_uuids)`. Classify: user record whose `message.content` list holds a `tool_result` block → `kind = tool_result`, carrying that block's `tool_use_id`; string or text-only content → `user_text`; bookkeeping types → `metadata`. Every token-relevant contributor is identifiable (0/65,470 user records lack a uuid; every uuid-less type is tokenless bookkeeping). The 169 usage-less assistant records route their interval to `ambiguous`.
7. **The exact case** (exactly one contributor: 43,847/51,933 = 84.43% of intervals here; identifiability never subtracts from it): `status = exact`. Join `contribution.tool_use_id → tool_invocation.tool_use_id` — total, 59,740/59,740 resolve to an earlier `tool_use` in the same file — reaching `tool_name` and the issuing call. Emit `fact{kind: attribution, tool_use_id: "toolu_EXAMPLE", tool_name: "Read", metrics: {context_delta: attributable}, locator: (file_id, contributor line_no)}` — **"this Read result added N tokens to the window"**, N exact, evidence one `line_no` away. A sole `user_text` or token-bearing metadata contributor is named as that kind instead — attribution is to the contributor, never presumed to be a tool.
8. **Everything else:** `status = ambiguous` — ONE bucket, candidates listed by name with the measured total, never spread.
9. **Forest:** dedup attribution facts by `next_call` uuid before totals; the population line is printed from the interval `status` counts, computed, not hand-written.

The walk completes. Every join it needs is present at 100% on the measured populations.

## 3. Divergence from v1's [OPEN] choices

- **Kept unchanged** (no new measurement, and the relational stance agrees): score `= stat × cover`; `cover` as a fact count (relational reading: rows non-NULL on the join column); missing-key/null unified into one residual (this IS NULL semantics); the purity boundary (relations are built upstream; the engine consumes generated fact maps); `spend` input-side only; MAX reconciliation; `0` without advancing carry for usage-less calls; fail-closed raise on unclassified metrics; node-uniform η² fallback; basis-scoped fields absent, not defaulted; schema-derived tests with vacuity guards.
- **Diverge 1 — the locator (charter problem 1):** v1's single index becomes a keyed relationship: `(file_id, span, constituent_uuids)` plus fks. A single index cannot express the 78.05% of generations that are split; the constituent list is what makes interval boundaries well-defined.
- **Diverge 2 — presentation (charter problem 2):** the view registration surface becomes stored queries with computed denominators, rendered from schema metadata. Cross-slice pivots are cheap because every dimension is a column: the same attribution facts group by `tool_name`, `locator.source`, or any declared column, zero per-view wiring.
- **Diverge 3 (decision-log; needs an owner ruling — the files are ported verbatim):** `AGGREGATION` and `METRIC_UNITS` are two metric-keyed dicts, so "adding a metric touches exactly ONE declaration" fails on the ported schema itself. Proposal: one v2 `METRICS` table (name → class, unit) with a consistency test against both ported dicts — a wrapper, not an in-place edit, respecting the channel of change.

## 4. Deliberately not building

- TIME/scheduling — but `timestamp` is a stored column on `record` and `call`, so time later lands as new metric declarations, no schema rework.
- Any estimator for the ambiguous bucket; chars→tokens in any form; dollar figures.
- Cross-file window stitching. v2 names lanes (file-scoped, exact) and forests (sessionId-scoped — a filename is not a session id for 86% of files); it does not claim to name a window, and `file_head` status is where that honesty lives.
- A real query engine (sqlite/duckdb), the HTML/JS twin, the parity harness.

## Suspected misfiles

1. **§1 "…and NOT the per-node max", inside an [ARITHMETIC] tag.** The sum prohibition is arithmetic. But refusing to *display* a labeled max over member facts' own values (a well-defined statistic the engine's η² branch already consumes) is population-honesty policy, [RULING]-shaped. The tag forecloses a future per-window peak surface as a category error when the real blocker is that windows are unnameable today.
2. **§6 "the carry resets to an empty window at the start of EVERY file" as [ARITHMETIC].** For unrelated files, arithmetic. For continuation files — bg, /branch, --fork-session, the very shapes the non-negotiables say continue ONE window — the reset counts inherited occupancy as fresh growth, so forest-level Σ`context_delta` exceeds true window growth by the inherited prompt per continuation file. That is a design compromise pending window identity: [OPEN] (or [RULING]), not arithmetic. My model does not resolve it; the named `file_head` status quarantines it so the population line can say so.

## What I'd attack in the obvious design

The obvious v2 keeps v1's fact bag, enriches the locator (end index, constituent list, `tool_use_id` stuffed into it), and computes attribution in a post-pass. Attack: (a) "between-ness" then lives procedurally in a pass, and every future query touching contributors re-implements it — v1's 40-table drift surface, relocated into code; (b) `tool_use_id` stays evidence inside the locator, so the drill engine cannot slice by it without a special case, when Phase 0 shows it is a total key — exactly what a dimension column is; (c) a fact bag has no population predicate, so the denominator stays a hand-written sentence nothing checks. The opposite obvious design — dump everything into sqlite — buys a query language at the cost of the purity contract and schema-derived tests.

## Weakest point

The `contribution` relation's boundary rule — "strictly between by constituent position" — is the one derived relation the flagship join, the exact/ambiguous split, and the dedup key all hang from. Interleaved generations (84), usage-less assistant records (169), and metadata inside physical runs make its edges fiddly, and a boundary slip misfiles contributors *silently*: the statuses cannot catch a wrong-but-plausible membership. My mitigation is a sweep-derived partition test (every non-assistant record lands in exactly one interval; vacuity-guarded) — but that asserts partition-ness, not edge correctness, and critics should land exactly there.
