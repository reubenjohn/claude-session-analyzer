"""The schema is the only source of metric and cause names; the query
layer honours it."""
import pytest

import fixtures as fx
from sa import query, schema
from sa.schema import Locator


@pytest.fixture
def facts(tmp_path):
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": fx.window_records()})
    return fx.load_facts(root)[1]


def test_every_metric_is_carried_only_by_its_kind(facts):
    classes_seen = set()
    for name, spec in schema.METRICS.items():
        carriers = [f for f in facts if name in f.metrics]
        assert carriers, "fixture carries no %s" % name
        assert {f.kind for f in carriers} == {spec.carrier}
        classes_seen.add(spec.aggregation)
    assert classes_seen == {schema.ADDITIVE, schema.PEAK}


def test_group_refuses_every_peak_and_sums_every_additive(facts):
    peaks = [n for n, s in schema.METRICS.items() if s.aggregation == schema.PEAK]
    assert peaks
    for name in peaks:
        with pytest.raises(ValueError):
            query.group(facts, "cause", name)
        assert query.largest(facts, name).metrics[name] == fx.FINAL_OCCUPANCY
    for name, spec in schema.METRICS.items():
        if spec.aggregation == schema.ADDITIVE:
            rows = query.group(facts, "session", name)
            assert sum(r.mass for r in rows) == sum(
                f.metrics[name] for f in facts if f.kind == spec.carrier)


def test_unknown_names_fail_closed(facts):
    with pytest.raises(schema.SchemaError):
        query.group(facts, "cause", "not_a_metric")
    with pytest.raises(schema.SchemaError):
        query.group(facts, "not_a_dim", "context_delta")
    with pytest.raises(schema.SchemaError):
        query.select(facts, [("not_a_dim", "x")])
    loc = Locator("f", 1, None)
    with pytest.raises(schema.SchemaError):
        schema.fact(schema.INCREMENT, {"cause": "not_a_cause"}, {"context_delta": 1}, loc)
    with pytest.raises(schema.SchemaError):
        schema.fact(schema.CALL, {}, {"context_delta": 1}, loc)


def test_group_keeps_residual_and_signed_rows_out_of_shares(facts):
    rows = query.group(facts, "tool", "context_delta")
    labels = [r.value for r in rows]
    assert labels[-2:] == [schema.RESIDUAL, schema.SHRINK]
    residual, shrink = rows[-2], rows[-1]
    assert residual.share is None and shrink.share is None and shrink.signed
    assert shrink.mass < 0 and residual.mass > 0
    regular = rows[:-2]
    assert regular == sorted(regular, key=lambda r: -r.mass)
    assert abs(sum(r.share for r in regular) - 1.0) < 1e-9
    # The shrink increment has no tool, yet it never lands in the residual.
    assert residual.count == sum(1 for f in facts if f.kind == schema.INCREMENT
                                 and "tool" not in f.dims
                                 and f.dims["cause"] != schema.SHRINK)


def test_select_matches_every_pair_regardless_of_order(facts):
    where = [("head", "pytest"), ("cause", schema.TOOL_RESULT)]
    hits = query.select(facts, where)
    assert hits and hits == query.select(facts, where[::-1])
    assert all(f.dims["head"] == "pytest" for f in hits)
    assert query.select(facts, [("candidate_count", "2")])
