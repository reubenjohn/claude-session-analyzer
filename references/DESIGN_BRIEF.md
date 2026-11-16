# session-analyzer v2 — the attribution walk (the spec)

The walk every context figure rests on, as specified and measured before the
build (Phase 3 synthesis, 2026-07-28). `sa/walk.py` implements it; its
docstring is the current spec and `DECISION_LOG.md` the rulings since. The
rest of the brief (graft map, the ported engine's data model and presets,
v1 divergences, seam frictions) is superseded by D-ENGINE and the rulings
after it: `git show 048b3ff:references/DESIGN_BRIEF.md`, with the design
competition it synthesised (`DESIGN_COMPETITION.md`, `designs/`).

**Terms as of 2026-07-28.** `feed_forward` is now `replies`; a lane is a
window (D-CONTEXT-WINDOW: one context window, not a file); `lane_head` is
`starting_context`; `cause.kind` is the `cause` dimension; quarantined
shrink is the signed `shrink` row; the tool_input head is `command` (R5).
Figures are one machine's corpus on that date: re-run, never quote.

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
`probe_interval_boundary.py` (Spike 1, a design-competition probe never in this repo).

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

The ported engine this section was measured against is retired
(D-ENGINE); its one lasting finding, a metric carried by both fact kinds
totals exactly 2.000000x the truth, is why every metric names one carrier
(R1, `sa/schema.py`).

## 4. Deliberately not building

No estimator for multi-contributor intervals: the ambiguous bucket stays.
No chars to tokens anywhere (1.8x measured spread; a confident wrong
number). No dollars. No TIME view: locators keep timestamps and spans, so
it lands later without reparsing. No full tool inputs as a dimension (R5).

## 5. Honest gaps — labelled, not hidden

1. **Chain integrity cannot catch a wrong-but-plausible attribution WITHIN an
   interval** — a misclassified contributor yields an exact-labeled fact for
   the wrong cause. 94.98% is structural exactness, not verified causal truth.
2. **Attachment caveat:** if some attachment type does inject prompt tokens,
   that mass lands on the sole token-relevant contributor — labeled exact.
   The exclusion rests on a correlation, not a proof.
3. **`command` extraction is hand-curated:** the sweep proves the
   mapping is declared and used, not that `env FOO=1 cmd`-shaped heads come
   out right.
4. **Corpus figures drift:** every number above is one machine, 2026-07-28;
   `python3 -m sa.sweep` re-measures the live ones.
