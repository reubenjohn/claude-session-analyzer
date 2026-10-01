"""Usage-dict helpers ported from v1's lib_parse.py.

The function bodies are the ported ones, unchanged (tests pin them). The
docstrings hold only the measured corrections; a change to either is a new
measurement plus a logged ruling (DECISION_LOG D-USAGE-DOCSTRINGS).
Population, unless a docstring says otherwise: the 2026-07-28 sweep of one
machine's full corpus.
"""

_CTX = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
_ALL = ("input_tokens", "output_tokens",
        "cache_creation_input_tokens", "cache_read_input_tokens")


def usage_context(u):
    """Call prompt size = input + cache_read + cache_creation: context-window
    occupancy at this call, NOT a cumulative total. Summing it over calls
    once printed 4,950,327 against a true high-water mark of 131,612."""
    if not isinstance(u, dict):
        return 0
    return sum(int(u.get(k, 0) or 0) for k in _CTX)


# Cost weights in BASE-TOKEN-EQUIVALENTS per token for the three input classes,
# from the published prompt-caching economics (cache reads ~0.1x base input
# price; cache writes 1.25x for the 5-minute TTL, 2x for the 1-hour TTL),
# verified against Claude Code 2.1.220. Equivalents, never dollars: the dollar
# rate varies per model and per speed mode, which max_merge_usage drops.
CACHE_READ_WEIGHT = 0.1
CACHE_WRITE_WEIGHT = {"1h": 2.0, "5m": 1.25}


def cache_creation_tiers(u):
    """(1h tokens, 5m tokens) from ``usage.cache_creation``; (0, 0) if absent."""
    if not isinstance(u, dict):
        return 0, 0
    cc = u.get("cache_creation")
    if not isinstance(cc, dict):
        return 0, 0
    return (int(cc.get("ephemeral_1h_input_tokens", 0) or 0),
            int(cc.get("ephemeral_5m_input_tokens", 0) or 0))


def usage_spend(u):
    """What one call COST, in base-token-equivalents; additive across calls.

    ``1.0*input_tokens + 0.1*cache_read_input_tokens + W*cache_creation``, W
    from each token's own TTL tier, read PER CALL from the nested
    ``cache_creation``. Measured over 47,419 usage-bearing calls in 1,719
    files (versions 2.1.177-2.1.220): nested ``cache_creation`` is present on
    all of them; ``ephemeral_1h + ephemeral_5m == cache_creation_input_tokens``
    on 47,419 of 47,419; and exactly one tier applies to any one call (0
    mixed), while a session mixes tiers freely, so a per-session tier would be
    inference. A cache write the subfields attribute to no tier (0 tokens
    measured) is priced at 5m, the default TTL of a bare ``{"type":"ephemeral"}``.

    Output tokens are NOT here: they bill on a different axis at a different
    rate, and the economics quoted above covers the input classes only.
    """
    if not isinstance(u, dict):
        return 0.0
    hour, five = cache_creation_tiers(u)
    declared = int(u.get("cache_creation_input_tokens", 0) or 0)
    untiered = max(0, declared - hour - five)
    return (float(int(u.get("input_tokens", 0) or 0))
            + CACHE_READ_WEIGHT * int(u.get("cache_read_input_tokens", 0) or 0)
            + CACHE_WRITE_WEIGHT["1h"] * hour
            + CACHE_WRITE_WEIGHT["5m"] * (five + untiered))


def context_delta(previous, current):
    """Per-call occupancy increment: ``usage_context(N) - usage_context(N-1)``.

    SIGNED and unclamped: a window that shrinks is a real event, 830 of
    45,555 consecutive-call pairs (827 of them by more than 100 tokens, with
    no compaction marker anywhere). ``None`` for ``previous`` means occupancy
    0 before the first call, so a sequence's deltas telescope to its final
    occupancy.

    ``cache_creation_input_tokens`` is NOT this increment. The identity
    ``cache_read(N) == cache_read(N-1) + cache_creation(N-1)`` holds on only
    92.21% of 45,818 pairs, and taking cache_creation as the increment
    double-counts nearly half of all cached tokens: ``sum|negative residual|``
    is 49.0% of ``sum cache_creation(N)`` over those pairs, 44.7% of
    ``sum cache_creation(N-1)``, 42.9% of ``sum cache_creation`` over all calls.
    """
    return usage_context(current) - usage_context(previous)


def max_merge_usage(usages):
    """Field-wise max over the usage dicts of one ``message.id``, recursing
    into the nested ``cache_creation``.

    Load-bearing: over 46,955 message.ids forest-wide (a sweep of the same
    corpus earlier than Phase 0's), 37,807 (80.5%) are split over more than
    one record and 27,591 of those (73.0%) disagree on ``output_tokens``, so
    take-first misreports output on most split calls. Occupancy almost never
    disagrees: 1 split id of 37,807.
    """
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
