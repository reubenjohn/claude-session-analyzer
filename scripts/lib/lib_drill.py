#!/usr/bin/env python3
"""lib_drill — the generic drill engine.

This module IS the specification. BUILD_SPEC.md §0 (the arithmetic) and §1 (the
discovery pipeline) were deleted when this file and its tests replaced them,
under that document's governing rule: a section is deleted when it becomes code,
because the test is then the record. Where those sections used to point, read
``tests/test_score_rule.py`` (the rule and its counterexamples),
``tests/test_score_rule_mutations.py`` (proof the guards bite), and
``tests/test_engine_acceptance.py`` (the acceptance bar).

A node is an ordered path of ``dimension=value`` pairs; its member set is the
facts matching that path. This module answers two questions about a node and
nothing else: *which dimensions are worth offering next* (``discover_dimensions``)
and *which facts does a path select* (``resolve_path``).

It measures a dimension with one of TWO statistics, and the metric's aggregation
class picks which — entropy concentration over bucket shares for an additive
mass, explained variance (η²) over the facts' own values for a ``peak`` or a
``derived`` ratio. Both land in 0..1 and multiply by the same ``cover``, so there
is one score rule, one tie-break, and one entry point; what there is not is a
category of metric this engine refuses. See ``STATISTIC_FOR_CLASS`` for why the
free axis is the statistic rather than the aggregator, and
``tests/test_variance_explained.py`` for the record.

Purity is a contract, not an aspiration. No file I/O, no dataset reads, no
clock, no randomness, no global mutable state, no mutation of inputs — the same
inputs produce byte-identical output, which is what makes the acceptance tests
in ``tests/test_engine_acceptance.py`` reproducible. Bucket sums are taken in a
fixed canonical order so even float results are stable.

The engine also knows nothing of rendering, the CLI, or argparse: it returns
numbers and identifiers, never composed prose.

Scope for Filter B comes from ``sa_schema.scopes()`` — the same one-pass rule
the census prints — so the gate cannot drift from what the data carries.
"""

import json
import math
import sys
from pathlib import Path

# sa_schema.py is the parent directory's module: the single source for
# shape_of / flatten / EVIDENCE_FIELDS / scopes.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sa_schema  # noqa: E402

# The one reserved bucket. A missing key and an explicit null are the SAME case
# everywhere in this module — `cover` is defined against this single bucket
# precisely so no second predicate can drift from it.
RESIDUAL = "∅undefined"

# Reject a dimension whose single largest bucket holds more than this share of
# the member facts (strict >; exactly 0.95 survives).
# First-fit on datasets A and B — the first thresholds tried that behaved. NOT a
# swept optimum; no sensitivity analysis stands behind them.
TOP_MEMBER_SHARE_MAX = 0.95

# Fewer distinct keys than this and there is nothing to partition.
# First-fit on datasets A and B — the first thresholds tried that behaved. NOT a
# swept optimum; no sensitivity analysis stands behind them.
MIN_CARDINALITY = 2

# The two statistics this engine can put in the 0..1 slot of `score = stat × cover`,
# and the aggregation class that selects each.
#
# AGGREGATION DISPATCHES; IT DOES NOT GATE. An earlier version of this module let
# only `additive` in and raised on everything else, on the reasoning that summing
# a peak is a correctness bug. The premise is right and the conclusion was wrong:
# summing is not the only question that can be asked of a bucket.
#
# - CONCENTRATION is 1 − normalised entropy over `p_k = mass_k / Σmass`. It asks
#   "how concentrated is the SHARE?", which needs an additive, non-negative
#   quantity — right for `observed_chars` and `duration_s`, meaningless otherwise.
# - VARIANCE_EXPLAINED (η²) is between-bucket variance over total variance of the
#   facts' OWN values. It asks "does knowing the bucket tell you the value?",
#   which is the only well-posed question for a `peak` (`context_tokens`) or a
#   `derived` ratio (`rate`) — quantities stored one per fact, with no total to
#   take a share of. Both land in 0..1 and multiply by `cover` unchanged, so the
#   score rule and the `(-score, dimension)` tie-break are untouched.
#
# A different AGGREGATOR does not rescue the gated design and was not the missing
# piece: `min`/`max`/`mean` all produce a per-bucket vector that can be
# normalised, but the entropy of a normalised min-vector states nothing — the
# buckets are no longer shares of a whole. The free axis is the STATISTIC.
CONCENTRATION = "concentration"
VARIANCE_EXPLAINED = "variance_explained"

STATISTIC_FOR_CLASS = {
    "additive": CONCENTRATION,
    "peak": VARIANCE_EXPLAINED,
    "derived": VARIANCE_EXPLAINED,
}

# Filter A exemptions: evidence paths kept as slice axes anyway.
#
# UNMEASURED DESIGN DECISION. Root-segment matching puts `locator.source` inside
# sa_schema.EVIDENCE_FIELDS, so the retired prototype that produced BUILD_SPEC's
# ranked figures rejected it — none of those figures includes this exemption.
# It is kept because `locator.source` covers 100% of facts and is the *only*
# agent-identifying axis on injected facts (subagent_info.agent_id is absent from
# every one of them), i.e. excluding it blinds the engine on the data it exists
# to explain. It demonstrably moves rankings: see the recorded deviation in
# tests/test_score_rule.py::test_entailed_dimensions_are_filtered_at_a_drilled_node.
EVIDENCE_EXEMPTIONS = ("locator.source",)


def dimension_value(fact, dimension):
    """The bucket key one fact contributes to ``dimension`` (a dotted path).

    Absent segment, non-dict on the way down, or a resolved ``None`` all collapse
    to ``RESIDUAL`` — missing and explicit-null are one case. Scalars are used
    as-is; lists and dicts are canonicalised with ``json.dumps(sort_keys=True)``
    so they are hashable and order-independent.
    """
    node = fact
    for part in dimension.split("."):
        if not isinstance(node, dict) or part not in node:
            return RESIDUAL
        node = node[part]
    if node is None:
        return RESIDUAL
    if isinstance(node, (dict, list)):
        return json.dumps(node, sort_keys=True)
    return node


def statistic_for(metric):
    """Which statistic this engine measures ``metric`` with. Raises for an unknown one.

    The class comes from ``sa_schema.AGGREGATION``, the same declaration the
    census prints, so the choice cannot drift from what the schema claims — the
    reason Filter B takes its scope from ``sa_schema.scopes()`` rather than
    recomputing one. Summing a ``peak`` or a ``derived`` ratio is still the
    correctness bug it always was; nothing here sums one. The class now selects
    the arithmetic instead of admitting or refusing it, which is why there is no
    longer a category of metric this engine turns away for its meaning.

    FAIL CLOSED ON AN UNCLASSIFIED METRIC, and the argument is unchanged by the
    dispatch. What a metric means is not recoverable from the data: an unnamed
    metric could be a mass (where a share is the question) or a per-fact value
    (where explained variance is), and picking either would be a guess rendered
    as a measurement. It is also the typo path — ``sa rank --metric`` is free
    text, and a mistyped name reaches every fact as "absent", which η² would
    report as a serene 0 rather than as the mistake it is.
    """
    statistic = STATISTIC_FOR_CLASS.get(sa_schema.AGGREGATION.get(metric))
    if statistic is not None:
        return statistic
    raise ValueError(
        "metric %r is unclassified; the drill engine picks its statistic from a "
        "metric's aggregation class and cannot infer one from the data (see "
        "sa_schema.AGGREGATION). Known metrics: %s."
        % (metric, ", ".join(sorted(sa_schema.AGGREGATION))))


def discover_dimensions(facts, members, metric, scope=None, collapse=True):
    """Rank the dimensions worth offering at the node whose member set is ``members``.

    ``facts`` is the whole ``{leaf_id: fact}`` map, ``members`` an iterable of
    leaf ids, ``metric`` a key into ``fact["metrics"]``, and ``scope`` the
    ``{dimension: set(shape)}`` table from ``sa_schema.scopes()`` (derived from
    ``facts`` when omitted).

    Returns every survivor, ranked — truncation is a UI concern. Each record is
    a dict with the keys documented in ``_statistics``, plus ``dimension`` and
    the ``aliases`` / ``folded_into`` pair that ``_collapse_identical`` sets.

    ``collapse=False`` keeps the rows Filter D would have suppressed, each marked
    with the representative that absorbed it. It exists so a MEASUREMENT tool can
    still see what the filter removed: a filter that hides its own input cannot
    be checked, and a miscomputed signature would suppress genuinely different
    dimensions with no way to notice. Ranking, statistics and order are identical
    either way — the flag only decides whether suppressed rows are dropped.
    """
    statistic = statistic_for(metric)
    members = list(members)
    n = len(members)
    if n == 0:
        # BOUNDARY: nothing to partition, and `cover` / `top_member_share` are
        # undefined here rather than 0. Return before bucketing so no caller can
        # read a defaulted statistic that was never measured.
        return []
    if scope is None:
        scope, _present = sa_schema.scopes(facts)

    node_shapes = set(sa_schema.shape_of(facts[leaf_id]) for leaf_id in members)

    ranked = []
    for dimension in _candidates(facts, members):
        if not _is_slice_axis(dimension):
            continue
        if not _in_scope(dimension, node_shapes, scope):
            continue
        record = _statistics(facts, members, dimension, metric, statistic)
        if record is None:
            continue
        record["dimension"] = dimension
        ranked.append(record)

    # Ties broken by dimension name ASCENDING: candidate-list order is not stable
    # across datasets, and a reproduction test needs a total order.
    ranked.sort(key=lambda record: (-record["score"], record["dimension"]))
    # Filter D runs AFTER the sort, so the representative it keeps is whichever
    # member of a collinear group the engine's own total order already ranked
    # first. No second ordering rule is introduced.
    return _collapse_identical(facts, members, ranked, collapse)


def resolve_path(facts, path, metric):
    """Resolve an ordered dimension-path to that node's members and metric aggregate.

    Returns ``{"members", "total", "total_statistic", "n_valued"}``. Node identity
    is the ordered path; the member set is derived by filtering, and set
    intersection is commutative — so ``[A, B]`` and ``[B, A]`` return the same
    members in the same order and the same aggregate. Both are accumulated in
    ``facts`` iteration order, which the path order cannot perturb.

    ``total_statistic`` NAMES what ``total`` is, and reading one without the other
    is a bug of exactly the class this pair exists to prevent. A ``peak`` or a
    ``derived`` ratio has no meaningful sum — summing ``context_tokens`` across a
    node printed a plausible six-figure number that was nothing at all — so those
    aggregate as the ``"mean"`` of the facts that carry a value, matching the
    per-bucket means the ranked statistic compares. ``"sum"`` is the additive
    case. ``total`` is ``None`` when no member carries the metric, because the
    mean of nothing is not 0.

    ``n_valued`` counts members carrying a usable value, on both branches: under
    ``"sum"`` an absent contribution really is 0 and belongs in the total, but a
    caller still has to be able to tell a node of zeroes from a node of absences.

    Values compare against ``dimension_value``'s bucket keys: to select the
    residual bucket, pass ``RESIDUAL``.
    """
    summed = statistic_for(metric) == CONCENTRATION
    pairs = list(path)
    members, total, valued = [], 0, 0
    for leaf_id, fact in facts.items():
        if all(dimension_value(fact, dimension) == value for dimension, value in pairs):
            members.append(leaf_id)
            value = _value(fact, metric)
            if value is not None:
                valued += 1
                total += value
    if summed:
        return {"members": members, "total": total, "total_statistic": "sum",
                "n_valued": valued}
    return {"members": members, "total": total / valued if valued else None,
            "total_statistic": "mean", "n_valued": valued}


def _candidates(facts, members):
    """The flat dotted namespace carried by the node's members, in a fixed order.

    Attributes and evidence share this namespace — which is why Filter A exists
    and is not dead code. A dimension carried by no member would bucket to a lone
    residual and die at Filter C, so restricting the sweep to the members' own
    keys changes no outcome and keeps the query path cheap.
    """
    seen = set()
    for leaf_id in members:
        seen.update(sa_schema.flatten(facts[leaf_id]))
    return sorted(seen)


def _is_slice_axis(dimension):
    """FILTER A — type curation. No statistics computed here; a hard skip.

    Reject any path whose ROOT SEGMENT (first dotted component) is in
    sa_schema.EVIDENCE_FIELDS, except the paths in EVIDENCE_EXEMPTIONS.
    """
    if dimension in EVIDENCE_EXEMPTIONS:
        return True
    return dimension.split(".")[0] not in sa_schema.EVIDENCE_FIELDS


def _in_scope(dimension, node_shapes, scope):
    """FILTER B — applicability gate. No statistics computed here; a hard skip.

    Offer D at node N iff ``shapes(N) ⊆ scope(D)``: CONTAINMENT, not
    intersection. A dimension absent from ``scope`` is skipped outright.
    Soft coverage-multipliers were tried instead of this gate and junk kept
    resurfacing at a different rank position rather than disappearing.
    """
    allowed = scope.get(dimension)
    if allowed is None:
        return False
    return node_shapes.issubset(allowed)


def _statistics(facts, members, dimension, metric, statistic):
    """FILTER C — the only stage that computes. ``None`` means rejected.

    Survivors carry: dimension (added by the caller), score, stat, statistic,
    cover, card, top_member_share, n, top_key, dist_basis, dist_basis_reason,
    n_measured — plus the field that only the statistic actually used defines:
    ``conc`` and ``top_metric_share`` under concentration, ``eta_squared`` and
    ``top_bucket_mean`` under variance explained.

    THE BASIS-SCOPED FIELDS ARE ABSENT, NOT DEFAULTED, when they do not apply.
    A reader that wants the 0..1 number without caring which one it is reads
    ``stat`` and is told which by ``statistic``; a reader that names ``conc``
    gets an entropy or a ``KeyError``, never an η² wearing the wrong name. The
    same discipline is why ``top_bucket_mean`` is not called ``top_metric_share``
    — the mean of a bucket is not a share of anything, and reusing the name would
    put a number in tokens-per-fact where consumers read a fraction.

    Filters and score are statistic-independent: ``card``, ``top_member_share``
    and ``cover`` are all FACT COUNTS, so both branches are gated identically and
    ``score = stat × cover`` needs no cases.
    """
    n = len(members)
    count = _bucket_counts(facts, members, dimension)
    keys = _canonical(count)

    card = len(keys)                                   # INCLUDES the residual
    if card < MIN_CARDINALITY:
        # card == 1 where the sole key IS the residual has cover == 0 and is
        # rejected here. That is a different case from "one real value plus
        # residual", which is card == 2 and must NOT be rejected.
        return None

    top_member_share = max(count[k] for k in keys) / float(n)   # INCLUDES residual
    if top_member_share > TOP_MEMBER_SHARE_MAX:
        return None

    cover = (n - count.get(RESIDUAL, 0)) / float(n)    # EXCLUDES residual; FACT COUNT, not mass

    if statistic == VARIANCE_EXPLAINED:
        measured = _variance_explained(facts, members, dimension, metric)
    else:
        # `_bucket_mass` is reached ONLY on this branch, which is what makes a
        # summed peak structurally absent from the module rather than computed
        # and discarded.
        measured = _concentration(_bucket_mass(facts, members, dimension, metric),
                                  count, keys, card)
    if isinstance(measured, str):
        # The values could not carry a statistic. Fall back to the SAME
        # count basis the mass branch already falls back to, carrying its own
        # reason — a renderer that marks and footnotes one marks and footnotes
        # the other for free. Note the fallback is decided by node-level
        # properties (does any member carry a value; do they all carry the same
        # one), so every dimension at the node falls back together and the
        # ranking stays a comparison of like with like.
        measured = _concentration(None, count, keys, card, forced_reason=measured)

    # SCORE. Do NOT add a cardinality penalty: `conc` is ALREADY entropy-normalised
    # by ln(card), so conc/log2(card) and conc/sqrt(card) apply a *second*
    # cardinality penalty. Both were measured and both break the acceptance bar
    # (they bury cluster_id beneath spawn_depth and unseat tool_name from #1,
    # i.e. tools-tree reproduction fails). The defect is the penalty, not its
    # strength — a gentler one does not rescue the idea. Node explosion belongs
    # in bounded display, not in ranking. η² is a variance ratio rather than an
    # entropy and is not normalised by ln(card) at all, but the conclusion is the
    # same one and for the same reason: ranking is not where explosion is solved.
    record = {
        "score": measured["stat"] * cover,
        "cover": cover,
        "card": card,
        "top_member_share": top_member_share,
        "n": n,
    }
    record.update(measured)
    record["top_key"] = _as_text(record["top_key"])
    return record


def _concentration(mass, count, keys, card, forced_reason=None):
    """1 − normalised entropy over bucket SHARES. The additive statistic.

    Mass is usable iff it forms a DISTRIBUTION: total > 0 *and* every bucket
    non-negative. Both halves are load-bearing and the second is not
    theoretical — `duration_s` is additive but SIGNED (`clock_adjustment` facts
    carry a duration that is ≤ 0 by construction, see lib_turns.py's
    `signed_adjustment`), and a `time` node mixes them with `wall` facts in one
    member set. With a negative bucket and a positive total nothing raises:
    `top_metric_share` can exceed 1.0 and the entropy is computed over a vector
    that does not sum to 1, so the node reports an ordinary-looking wrong number.

    A bucket that NETS positive stays on mass and is correct — that is exactly
    what a signed correction fact is for. Only a bucket whose own sum goes
    negative breaks the arithmetic, which is why the predicate is the per-bucket
    minimum rather than the aggregation class: `duration_s` is declared additive
    and dispatches here, rightly. Signedness is a second axis, checked here.

    ``forced_reason`` is the variance-explained branch handing its own failed
    node over: ``mass`` is then ``None`` and MUST NOT be read, because the mass
    of a peak is the sum this engine is not allowed to take.
    """
    if forced_reason is not None:
        dist_basis, dist_basis_reason = "count", forced_reason
    else:
        total_mass = sum(mass[k] for k in keys)
        least_mass = min(mass[k] for k in keys)
        if total_mass > 0 and least_mass >= 0:
            dist_basis, dist_basis_reason = "mass", None
        # Why the fallback happened, so a renderer does not have to guess. The one
        # footnote that existed said "this node's total is 0", which is a lie in
        # the signed case — the total can be large and positive there.
        elif least_mass < 0:
            dist_basis, dist_basis_reason = "count", "signed_mass"
        else:
            dist_basis, dist_basis_reason = "count", "zero_mass"
    dist = mass if dist_basis == "mass" else count

    total = sum(dist[k] for k in keys)
    # Σdist == 0 with n > 0 is unreachable: the fallback is `count`, and
    # Σcount == n. Asserted rather than guarded — hitting this means `dist`'s
    # fallback got miswired, and a guard would hide that.
    assert total > 0, "sum(dist) == 0 with n > 0: dist's count fallback is miswired"

    top_key = keys[0]
    for key in keys:
        if dist[key] > dist[top_key]:
            top_key = key

    entropy = 0.0
    for key in keys:
        p = dist[key] / float(total)
        if p > 0:                                      # 0·ln0 := 0
            entropy -= p * math.log(p)
    conc = 1.0 - entropy / math.log(card) if card > 1 else 1.0

    return {
        "stat": conc,
        "statistic": CONCENTRATION,
        "conc": conc,
        "top_key": top_key,
        "top_metric_share": dist[top_key] / float(total),   # INCLUDES residual
        "dist_basis": dist_basis,
        "dist_basis_reason": dist_basis_reason,
        # Every member contributes on this basis — a count always, and a mass of
        # 0 where the metric is absent, which is the truth about a sum.
        "n_measured": sum(count.values()),
    }


def _variance_explained(facts, members, dimension, metric):
    """η² — the share of the metric's variance across facts that the split explains.

    The per-fact statistic. ``SS_between / SS_total`` over the members' own
    values: 1.0 when every bucket is internally constant (the bucket tells you
    the value exactly), 0.0 when every bucket has the grand mean (it tells you
    nothing). Returns a record, or a STRING naming why the values were unusable —
    the caller turns that into the count-basis fallback.

    ABSENT IS NOT ZERO, and this is the whole reason ``_value`` exists next to
    ``_metric``. `sa_aggregate` writes ``rate`` as null whenever tokens or
    duration are missing, and `context_tokens` is absent from every fact that is
    not a generation; folding those in as 0 would invent stalled calls and empty
    context windows, and η² would then dutifully report how well a dimension
    predicts *absence* under a column labelled with the metric. Facts carrying no
    value are excluded, and ``n_measured`` publishes how many were left so a
    renderer can say so. (``resolve_path`` calls its own count ``n_valued``, and
    the two names are deliberately different: that one is always "members
    carrying a value", while this one is "members the statistic ran over" — the
    same number here, but every member on the concentration branch.)

    Which members carry a value does not depend on the dimension, so ``SS_total``
    and both failure modes are node-level: every dimension at a node either gets
    an η² or falls back together.
    """
    sums, counts, valued, grand = {}, {}, 0, 0.0
    for leaf_id in members:
        fact = facts[leaf_id]
        value = _value(fact, metric)
        if value is None:
            continue
        key = dimension_value(fact, dimension)
        sums[key] = sums.get(key, 0.0) + value
        counts[key] = counts.get(key, 0) + 1
        valued += 1
        grand += value
    if valued == 0:
        return "absent_value"

    mean = grand / valued
    ss_total = 0.0
    for leaf_id in members:
        value = _value(facts[leaf_id], metric)
        if value is not None:
            ss_total += (value - mean) ** 2
    if ss_total <= 0:
        # Every member carries the same value. No split can explain variation
        # there is none of, and 0.0 would rank every dimension identically at 0
        # while claiming to have measured something.
        return "constant_value"

    keys = _canonical(counts)                # fixed summation order, as everywhere
    ss_between = 0.0
    for key in keys:
        ss_between += counts[key] * (sums[key] / counts[key] - mean) ** 2
    eta_squared = ss_between / ss_total
    # SS_between ≤ SS_total is algebra, not a hope, so anything past float noise
    # means the decomposition got miswired. Asserted loosely, then clamped, so a
    # real defect surfaces and a last-bit rounding artefact does not escape as a
    # statistic above 1.
    assert eta_squared <= 1.0 + 1e-9, "eta-squared above 1: SS_between exceeded SS_total"
    eta_squared = min(1.0, eta_squared)

    # The headline bucket is the one with the HIGHEST MEAN — the bucket driving
    # the variance, which is the readable answer to "who runs hottest / fastest".
    # Under concentration it is the largest bucket instead; both are "the bucket
    # this row is about", and the rule follows the statistic because nothing else
    # would be meaningful. Buckets holding no valued fact have no mean and cannot
    # win. Ties keep the canonical key order, matching the mass branch.
    top_key = keys[0]
    for key in keys:
        if sums[key] / counts[key] > sums[top_key] / counts[top_key]:
            top_key = key

    return {
        "stat": eta_squared,
        "statistic": VARIANCE_EXPLAINED,
        "eta_squared": eta_squared,
        "top_key": top_key,
        "top_bucket_mean": sums[top_key] / counts[top_key],
        "dist_basis": "value",
        "dist_basis_reason": None,
        # Fewer than `n` whenever the metric has holes, which is the caveat a
        # renderer has to be able to print — `rate` is null on any call missing
        # tokens or duration, so this gap is the normal case, not an edge one.
        "n_measured": valued,
    }


def _collapse_identical(facts, members, ranked, collapse=True):
    """FILTER D — identity collapse. Same partition, same question, one row.

    This is the SAME notion of entailment the engine already had, applied one
    step further out. Filter C already drops a dimension the drill path has made
    constant (card 1) — see
    ``tests/test_score_rule.py::test_entailed_dimensions_are_filtered_at_a_drilled_node``.
    That is the degenerate case of mutual determination: a dimension fixed by
    the path determines, and is determined by, nothing. Here the determinant is
    another *offered* dimension rather than the path, and the same conclusion
    follows — a dimension that partitions the node exactly as an already-offered
    one does asks a question that dimension has already answered.

    The predicate is PARTITION equality, not statistic equality. Every statistic
    is a function of the partition, so equal partitions provably produce an
    identical row (``card``, ``cover``, ``stat``, ``top_member_share``, ``score``,
    ``dist_basis`` and the basis-scoped fields all coincide); the converse
    is false — two genuinely different splits can share a bucket-size multiset
    and so every number computed from it. Collapsing on the numbers would
    therefore delete real axes that merely tie. See
    ``tests/test_identity_collapse.py`` for that counterexample, which no
    committed fixture happens to contain.

    Nothing is hidden: the folded names are published on the survivor's
    ``aliases`` and each suppressed row carries ``folded_into``, naming the
    representative that absorbed it. The decision is therefore ANNOTATED
    unconditionally and only its *effect* is optional — ``collapse=False``
    returns the same rows in the same order with nothing dropped, which is what
    lets ``sa rank --no-collapse`` audit the filter instead of inheriting it.
    """
    kept, seen = [], {}
    for record in ranked:
        signature = _partition_signature(facts, members, record["dimension"])
        representative = seen.get(signature)
        record["aliases"] = []
        record["folded_into"] = None
        if representative is None:
            seen[signature] = record
            kept.append(record)
        else:
            representative["aliases"].append(record["dimension"])
            record["folded_into"] = representative["dimension"]
            if not collapse:
                kept.append(record)
    return kept


def _partition_signature(facts, members, dimension):
    """The node's partition under ``dimension``, independent of its bucket KEYS.

    Members are numbered by the block they fall in, in first-appearance order
    over the fixed ``members`` sequence, so two dimensions that split the node
    identically share a signature however differently they label the blocks —
    which is the whole point, since a label vocabulary is what distinguishes
    ``subagent_info.agent_id`` from ``subagent_info.label``.

    The residual block is tagged rather than numbered like any other, because
    ``cover`` is the one statistic defined against it: two dimensions can carve
    the same blocks while only one of them calls a block *undefined*, and those
    are NOT the same question — they score differently and both are offered.
    """
    blocks, ids, residual = {}, [], None
    for leaf_id in members:
        key = dimension_value(facts[leaf_id], dimension)
        if key not in blocks:
            blocks[key] = len(blocks)
            if key == RESIDUAL:
                residual = blocks[key]
        ids.append(blocks[key])
    return (tuple(ids), residual)


def _bucket_counts(facts, members, dimension):
    """Fact count per bucket key. Needed by every filter and both statistics."""
    count = {}
    for leaf_id in members:
        key = dimension_value(facts[leaf_id], dimension)
        count[key] = count.get(key, 0) + 1
    return count


def _bucket_mass(facts, members, dimension, metric):
    """Summed metric mass per bucket key. ADDITIVE METRICS ONLY.

    Split out from the count pass so that the one operation this engine may not
    perform on a peak or a ratio has exactly one call site, on the branch the
    aggregation class already selected. A summed peak is then not something the
    module computes and declines to use — it is something the module never
    computes.
    """
    mass = {}
    for leaf_id in members:
        fact = facts[leaf_id]
        key = dimension_value(fact, dimension)
        mass[key] = mass.get(key, 0) + _metric(fact, metric)
    return mass


def _metric(fact, metric):
    """m(f) — the fact's contribution to a summed mass; absent or null is 0.

    Correct for a sum and WRONG for an average, which is why ``_value`` exists.
    """
    value = (fact.get("metrics") or {}).get(metric, 0)
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return value


def _value(fact, metric):
    """v(f) — the fact's OWN value for ``metric``, or ``None`` where it has none.

    The distinction ``_metric`` cannot make. Adding nothing to a sum is the truth
    about an absent quantity; averaging it in as 0 is a fabrication. `rate` is
    written null whenever a call recorded no tokens or no duration, and
    `context_tokens` is carried only by generation facts, so on the metrics this
    matters for the holes are routine. A non-numeric value is absent too, rather
    than the silent 0 a sum has to tolerate.
    """
    value = (fact.get("metrics") or {}).get(metric)
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _canonical(keys):
    """A total order over bucket keys, so every sum is taken the same way twice.

    Keys are heterogeneous (strings, numbers, booleans), which Python 3 refuses to
    compare, so the type name leads the sort key.
    """
    return sorted(keys, key=lambda key: (type(key).__name__, str(key)))


def _as_text(key):
    """The bucket key as a string, for the ``top_key`` identifier field."""
    return key if isinstance(key, str) else json.dumps(key, sort_keys=True)
