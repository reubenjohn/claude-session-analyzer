"""The average-context measurements (``sa.sweep_mean``): the held identity
holds by construction, fails loudly when broken, and the expansion of an
inherited increment by reference is exact."""
import json
import os

import fixtures as fx
from sa import query, reconciliation, schema, sweep_mean as m

DELTA, PEAK_METRIC = fx.DELTA, fx.metric_named(aggregation=schema.PEAK)


def _calls(facts, window):
    return [f for f in facts if f.kind == schema.CALL and f.window == window]


def test_held_counts_the_calls_from_the_booking_one_to_the_window_end(tmp_path):
    _, facts = fx.load_facts(fx.every_corpus(tmp_path))
    pairs = m.held(facts)
    assert len(pairs) == sum(f.kind == schema.INCREMENT for f in facts)
    assert any(n > 1 for _, n in pairs) and any(n == 1 for _, n in pairs)  # vacuity guard
    for f, n in pairs:
        assert 1 <= n <= len(_calls(facts, f.window))
    heads = [(f, n) for f, n in pairs if f.dims[schema.CAUSE_DIM] == schema.STARTING_CONTEXT]
    assert heads and all(n == len(_calls(facts, f.window)) for f, n in heads)


def test_the_identity_holds_signed_rows_and_inherited_included(tmp_path):
    _, facts = fx.load_facts(fx.every_corpus(tmp_path))
    causes = {f.dims[schema.CAUSE_DIM] for f in facts if f.kind == schema.INCREMENT}
    assert {schema.SHRINK, schema.INHERITED} <= causes  # vacuity guard: both are weighed
    check = m.identity(facts)
    assert check.holds and check.windows == query.window_count(facts)
    assert check.occupancy == sum(f.metrics[PEAK_METRIC] for f in facts if f.kind == schema.CALL)
    assert check.held == query.total(m.weighted(facts), DELTA)


def test_a_broken_chain_is_a_mismatch(tmp_path):
    _, facts = fx.load_facts(fx.every_corpus(tmp_path))
    i = next(i for i, f in enumerate(facts) if f.kind == schema.INCREMENT)
    broken = list(facts)
    broken[i] = facts[i]._replace(metrics={DELTA: facts[i].metrics[DELTA] + 1})
    check = m.identity(broken)
    assert not check.holds and check.holding == check.windows - 1


def test_expansion_replaces_every_inherited_increment_exactly(tmp_path):
    _, facts = fx.load_facts(fx.window_corpus(tmp_path))
    inherited = [f for f in facts if f.dims.get(schema.CAUSE_DIM) == schema.INHERITED]
    assert len(inherited) == len(fx.W_INHERITED)  # vacuity guard
    flat, expanded, exact = m.expand(facts)
    assert expanded == exact == len(inherited)
    assert not [f for f in flat if f.dims.get(schema.CAUSE_DIM) == schema.INHERITED]
    assert query.total(flat, DELTA) == query.total(m.weighted(facts), DELTA)
    # The parts sit in the fork's windows, under the fork's window dimensions.
    for f in inherited:
        mine = [p for p in flat if p.window == f.window]
        assert {p.dims[schema.STARTED_BY_DIM] for p in mine} == {f.dims[schema.STARTED_BY_DIM]}


def test_a_peak_is_reported_as_percentiles_of_peaks_never_a_sum(tmp_path):
    _, facts = fx.load_facts(fx.window_corpus(tmp_path))
    found = m.peaks(facts)
    assert len(found) == query.window_count(facts)
    assert max(v for v, _ in found.values()) == query.largest(facts, PEAK_METRIC).metrics[PEAK_METRIC]
    assert sum(sub for _, sub in found.values()) == 2  # the fork and the plain subagent
    assert m.rank([4, 1, 3, 2], 50) == 2 and m.rank([4, 1, 3, 2], 100) == 4 and m.rank([], 90) == 0
    top = query.largest(facts, PEAK_METRIC)
    assert m.shape(found, None).endswith("(window=%s)" % top.dims[schema.WINDOW_DIM])
    assert m.shape({}, None) == "0 windows"


def test_compare_names_rank_and_share_moves():
    line = m.compare({"a": 0.6, "b": 0.4}, {"a": 0.3, "b": 0.7})
    assert line.startswith("2 of top 2 kept, 2 moved, max swing 30.0 pts")
    assert "a 1>2 60.0>30.0" in line


def test_a_fork_read_without_its_parent_walks_the_copied_calls_as_its_own(tmp_path):
    """What a missing parent costs (D-MISSING-PARENT counts it; reading the
    parent anyway was ruled out): the copied prefix is live, so the fork
    gains the parent's calls (phantoms under the average's denominator) and,
    unmarked, is no longer recognised as a copy."""
    root = fx.window_corpus(tmp_path / "all")
    for name, when in ((fx.W_PARENT, 2e9), (fx.W_FORK, 1e9), (fx.W_REPLAY, 3e9)):
        os.utime(str(root / name), (when, when))  # the fork is older than its parent, the replay newer
    loaded, _ = fx.load_facts(root)
    cuts = {s.name: m.windows.cut(s, loaded.usages) for s in loaded.files}
    assert m.parents(loaded, cuts)[:3] == (len(fx.W_INHERITED), len(fx.W_INHERITED), 1)
    with_parent = len(cuts[fx.W_FORK][0].calls)
    every = fx.window_corpus(tmp_path / "copy")
    alone, _ = fx.load_facts(fx.corpus(tmp_path / "alone", {
        fx.W_FORK: [json.loads(line) for line in
                    (every / fx.W_FORK).read_text(encoding="utf-8").splitlines()]}))
    (window,) = m.windows.cut(alone.files[0], alone.usages)
    assert len(window.calls) > with_parent and window.start == schema.SUBAGENT_START


def test_a_since_read_that_drops_the_parent_is_compared_band_for_band(tmp_path):
    """D-PEAK-BAND is measured, not built: the fork read alone walks its
    copied calls live, which hold no more than the branch call its own first
    call exceeds, so its band holds."""
    root = fx.window_corpus(tmp_path)
    for path in root.rglob("*.jsonl"):
        os.utime(str(path), (1e9, 1e9))  # every file old ...
    os.utime(str(root / fx.W_FORK), None)  # ... but the fork
    loaded, facts = fx.load_facts(root)
    assert m.since_bands(loaded, facts) == (0, 1)
    alone = fx.load_facts(root, 7.0)[1]
    assert sum(f.kind == schema.CALL for f in alone) > sum(  # vacuity guard: the copies went live
        f.kind == schema.CALL and f.locator.file == fx.W_FORK for f in facts)


def test_the_engine_books_held_and_reconciles_it_per_window(tmp_path):
    """D-PER-CALL: ``walk.forest`` books ``context_held`` on every increment
    and the reconciliation checks it per window; one token off breaks it."""
    _, facts = fx.load_facts(fx.every_corpus(tmp_path))
    increments = [f for f in facts if f.kind == schema.INCREMENT]
    assert increments and all(fx.HELD in f.metrics for f in increments)
    assert {id(f): n for f, n in m.held(facts) if f.metrics[DELTA]} == {
        id(f): f.metrics[fx.HELD] / f.metrics[DELTA] for f in increments if f.metrics[DELTA]}
    r = reconciliation.reconcile(facts)
    assert r.held_holds and r.holds and r.held == r.occupancy > 0
    i = next(i for i, f in enumerate(facts) if f.kind == schema.INCREMENT)
    broken = list(facts)
    broken[i] = facts[i]._replace(metrics=dict(facts[i].metrics, **{fx.HELD: facts[i].metrics[fx.HELD] + 1}))
    r = reconciliation.reconcile(broken)
    assert not r.held_holds and not r.holds and r.mass_holds
    assert r.held_windows == r.windows - 1
