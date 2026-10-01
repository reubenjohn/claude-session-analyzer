"""Usage-dict helpers ported verbatim from v1 lib_parse.py.

Each docstring carries a measured correction and IS the specification.
Self-contained: no imports required.
"""

_CTX = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
_ALL = ("input_tokens", "output_tokens",
        "cache_creation_input_tokens", "cache_read_input_tokens")


def usage_context(u):
    """Call prompt size = input + cache_read + cache_creation (context-window
    occupancy, NOT a cumulative total). See CUMULATIVE_CACHE_TRAP."""
    if not isinstance(u, dict):
        return 0
    return sum(int(u.get(k, 0) or 0) for k in _CTX)


# Cost weights in BASE-TOKEN-EQUIVALENTS per token, for the three input classes.
# Quoted verbatim from the `claude-api` skill's `shared/prompt-caching.md:141`:
#
#   > **Economics:** Cache reads cost ~0.1x base input price. Cache writes cost
#   > **1.25x for 5-minute TTL, 2x for 1-hour TTL**.
#
# The quote is inlined (here and in `references/token-accounting.md`) because the
# citation is NOT reachable: that file lives under a version- and hash-scoped
# bundled-skills temp root, so it does not survive a Claude Code upgrade and never
# existed on another machine. Verified present at 2.1.220; re-verify before
# treating the numbers as fresh.
#
# Equivalents, never dollars. A rate is ambiguous per model anyway — Opus 5 is
# $5/$25 per MTok but fast mode on the same model is $10/$50, which `usage.speed`
# distinguishes and `max_merge_usage` drops.
CACHE_READ_WEIGHT = 0.1
CACHE_WRITE_WEIGHT = {"1h": 2.0, "5m": 1.25}


def usage_cache_tier(u):
    """Which TTL tier this call's cache writes were billed at, from nested usage.

    ``"1h"``, ``"5m"``, ``"mixed"`` (both subfields non-zero), or ``"none"`` (no
    cache write, or a record carrying no nested ``cache_creation`` to read).

    Read PER CALL, never at session level. Measured over 47,419 usage-bearing
    calls in 1,719 files (a sweep that did not collapse symlinks; the canonical
    ``scripts/corpus_shape.py`` reads 1,727 realpaths / 47,703 calls) spanning
    2.1.177-2.1.220 — every version that carries a call, which is 16 of the 17
    ``version`` values present over RECORDS (2.1.212 has 5 records and 0 calls, so
    "all 17 versions" is a record population quoted for a call one): nested
    ``cache_creation`` is present on 100% of them with no version gate;
    ``cache_creation_input_tokens == ephemeral_1h + ephemeral_5m`` on 47,419 of
    47,419 with zero mismatches; and ``mixed`` is 0 calls. So exactly one tier
    applies to any real call and the weighting needs no approximation — but a
    session mixes tiers freely, which is why taking the tier once per session
    (an earlier draft did) is inference dressed as measurement.
    """
    hour, five = _cache_creation_tiers(u)
    if hour and five:
        return "mixed"
    if hour:
        return "1h"
    if five:
        return "5m"
    return "none"


def _cache_creation_tiers(u):
    """(1h tokens, 5m tokens) from ``usage.cache_creation``; (0, 0) if absent."""
    if not isinstance(u, dict):
        return 0, 0
    cc = u.get("cache_creation")
    if not isinstance(cc, dict):
        return 0, 0
    return (int(cc.get("ephemeral_1h_input_tokens", 0) or 0),
            int(cc.get("ephemeral_5m_input_tokens", 0) or 0))


def usage_spend(u):
    """What one call COST, in base-token-equivalents. Additive across calls.

    ``1.0*input_tokens + 0.1*cache_read_input_tokens + W*cache_creation``, with
    ``W`` from the token's own TTL tier. This is the reading under which
    ``cache_read`` genuinely does accumulate — a cache read is money spent every
    time it happens — and it exists because reclassifying ``cache_read`` from
    ``additive`` to ``peak`` in ``sa_schema.AGGREGATION`` would otherwise have left
    no way to express cost at all.

    Each tier is weighted at its own rate rather than the call being assigned one
    tier, so a ``mixed`` call (0 observed in 47,419) is priced correctly instead of
    silently taking one side's rate. A cache write the nested subfields do not
    attribute to any tier is priced at 5m: that is the default TTL the source ties
    to a bare ``{"type":"ephemeral"}``, and 0 such tokens were measured.

    Output tokens are NOT here. They bill on a different axis at a different rate,
    and the quoted economics covers the input classes only — folding them in would
    produce a number in no stated unit.
    """
    if not isinstance(u, dict):
        return 0.0
    hour, five = _cache_creation_tiers(u)
    declared = int(u.get("cache_creation_input_tokens", 0) or 0)
    untiered = max(0, declared - hour - five)
    return (float(int(u.get("input_tokens", 0) or 0))
            + CACHE_READ_WEIGHT * int(u.get("cache_read_input_tokens", 0) or 0)
            + CACHE_WRITE_WEIGHT["1h"] * hour
            + CACHE_WRITE_WEIGHT["5m"] * (five + untiered))


def context_delta(previous, current):
    """Per-call occupancy increment: ``usage_context(N) - usage_context(N-1)``.

    SIGNED, and deliberately unclamped. A window that shrinks is a real event —
    830 of them over the 45,555-pair sweep, 827 of those dropping more than 100
    tokens, with zero compaction markers anywhere — so clamping
    would delete the evidence rather than the anomaly. ``NEGATIVE_DELTA_CLAMP`` is
    a caveat about concurrent split records producing tiny negative DURATIONS and
    must not be reused here; the two negatives mean different things.

    Pass ``None`` for ``previous`` at the head of a sequence: occupancy before the
    first call is 0, so the deltas of a sequence telescope to its final occupancy,
    which is what makes the metric ``additive`` while ``context_tokens`` is a
    ``peak``.

    ``cache_creation_input_tokens`` is NOT this increment, however much it looks
    like one. The identity ``cache_read(N) == cache_read(N-1) + cache_creation(N-1)``
    holds on only 92.21% of 45,818 measured pairs, and using it as the increment
    double-counts NEARLY HALF of all cached tokens: ``sum|negative residual|`` is
    49.0% of ``sum cache_creation(N)`` over those pairs, 44.7% of
    ``sum cache_creation(N-1)`` (the identity's own term), 42.9% of
    ``sum cache_creation`` over all calls. Name the denominator — "nearly half"
    survives all three, the digits do not.
    """
    return usage_context(current) - usage_context(previous)


def max_merge_usage(usages):
    """Field-wise max over usage dicts, recursing into nested cache_creation.

    LOAD-BEARING, not a belt-and-braces safety net. Measured over 46,955
    message.ids forest-wide: 37,807 of them (80.5%) are split over more than one
    record, and 27,591 of THOSE (73.0% of split ids, 58.8% of all ids) disagree on
    `output_tokens` — so take-first misreports output on the majority of split
    calls. Context occupancy is the field that almost never disagrees: 1 split id
    of 37,807 (0.0026%).

    Why this docstring changed: it used to quote "~0.07% of split calls disagree"
    on output_tokens, which was a correct output_tokens rate measured on a
    169-SESSION corpus, carried forward onto this ~1,700-file forest where the same
    field disagrees at 73.0% — a right measurement, quoted for a population it was
    not measured over, understating the case for max-merging by three orders of
    magnitude. Its other half, "0 context-field disagreements corpus-wide", is
    simply wrong here: there is 1. Both are the defect
    `references/token-accounting.md` exists to name.

    See USAGE_SPLIT_DEDUP + dedup-experiment.md."""
    usages = [u for u in usages if isinstance(u, dict)]
    if not usages:
        return {}
    out = {k: max(int(u.get(k, 0) or 0) for u in usages) for k in _ALL}
    keys = set()
    for u in usages:
        cc = u.get("cache_creation")
        if isinstance(cc, dict):
            keys |= set(cc.keys())
    if keys:
        out["cache_creation"] = {
            k: max(int((u.get("cache_creation") or {}).get(k, 0) or 0)
                   for u in usages)
            for k in keys
        }
    return out
