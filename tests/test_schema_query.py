"""The schema is the only source of metric and cause names; the query
layer honours it."""
import re

import pytest

import fixtures as fx
from sa import query, schema
from sa.schema import Locator


@pytest.fixture
def facts(tmp_path):
    """A main window and a subagent's: only the latter carries ``agent``."""
    fork = {"type": "fork-context-ref", "agentId": "agent-fake1"}
    root = fx.corpus(tmp_path, {
        "proj-a/sess-0001.jsonl": fx.window_records(),
        "proj-a/sess-0001/subagents/agent-fake1.jsonl": [fork] + fx.window_records("fork-")})
    return fx.load_facts(root)[1]


def test_every_metric_is_carried_only_by_its_kind(facts):
    classes_seen = set()
    for name, spec in schema.METRICS.items():
        carriers = [f for f in facts if name in f.metrics]
        assert carriers, "fixture carries no %s" % name
        assert {f.kind for f in carriers} == {spec.carrier}
        classes_seen.add(spec.aggregation)
    assert classes_seen == {schema.ADDITIVE, schema.PEAK}


def test_every_fact_carries_only_its_kinds_dimensions(facts):
    for kind in schema.KINDS:
        carried = set().union(*(f.dims for f in facts if f.kind == kind))
        assert carried == set(schema.KIND_DIMENSIONS[kind]), kind
    loc = Locator("f", 1, None)
    with pytest.raises(schema.SchemaError):
        schema.fact(schema.CALL, {schema.TOOL_DIM: "Bash"}, {}, loc)
    for dim in schema.DIMENSIONS:
        schema.check_dimension(dim, schema.INCREMENT)
    with pytest.raises(schema.SchemaError):
        schema.check_dimension(schema.TOOL_DIM, schema.CALL)


def test_group_refuses_every_peak_and_sums_every_additive(facts):
    peaks = [n for n, s in schema.METRICS.items() if s.aggregation == schema.PEAK]
    assert peaks
    for name in peaks:
        with pytest.raises(schema.SchemaError, match="peak"):
            query.group(facts, schema.CAUSE_DIM, name)
        assert query.largest(facts, name).metrics[name] == fx.FINAL_OCCUPANCY
    for name, spec in schema.METRICS.items():
        if spec.aggregation == schema.ADDITIVE:
            table = query.group(facts, schema.SESSION_DIM, name)
            assert sum(r.mass for r in table.rows) == query.total(facts, name) == sum(
                f.metrics[name] for f in facts if f.kind == spec.carrier)


def test_unknown_names_fail_closed(facts):
    with pytest.raises(schema.SchemaError):
        query.group(facts, schema.CAUSE_DIM, "not_a_metric")
    with pytest.raises(schema.SchemaError):
        query.group(facts, "not_a_dim", fx.DELTA)
    with pytest.raises(schema.SchemaError):
        query.narrow(facts, [("not_a_dim", "x")], fx.DELTA)
    with pytest.raises(schema.SchemaError):
        query.narrow(facts, [(schema.TOOL_DIM, "Bash")], schema.SPEND)  # never on a call fact
    assert query.narrow(facts, [(schema.TOOL_DIM, "Bash")], fx.DELTA)  # vacuity guard
    loc = Locator("f", 1, None)
    with pytest.raises(schema.SchemaError):
        schema.fact(schema.INCREMENT, {schema.CAUSE_DIM: "not_a_cause"}, {fx.DELTA: 1}, loc)
    with pytest.raises(schema.SchemaError):
        schema.fact(schema.CALL, {}, {fx.DELTA: 1}, loc)


def test_group_keeps_residual_and_signed_rows_out_of_shares(facts):
    table = query.group(facts, schema.TOOL_DIM, fx.DELTA)
    rows = table.rows
    assert [r.kind for r in rows[-2:]] == [query.RESIDUAL, query.SIGNED]
    residual, shrink = rows[-2], rows[-1]
    assert (residual.value, shrink.value) == (None, schema.SHRINK)
    assert shrink.mass < 0 and residual.mass > 0
    regular = rows[:-2]
    assert regular and all(r.kind == query.REGULAR for r in regular)
    assert regular == sorted(regular, key=lambda r: -r.mass)
    assert table.base == sum(r.mass for r in regular) == query.total(facts, fx.DELTA) \
        - residual.mass - shrink.mass
    assert abs(sum(table.share(r.mass) for r in regular) - 1.0) < 1e-9
    # The shrink increment has no tool, yet it never lands in the residual.
    assert residual.count == sum(1 for f in facts if f.kind == schema.INCREMENT
                                 and schema.TOOL_DIM not in f.dims
                                 and f.dims[schema.CAUSE_DIM] != schema.SHRINK)


def test_a_zero_base_leaves_rows_regular_with_no_share(facts):
    head = next(f for f in facts if f.dims.get(schema.CAUSE_DIM) == schema.WINDOW_HEAD)
    table = query.group([head._replace(metrics={fx.DELTA: 0})], schema.CAUSE_DIM, fx.DELTA)
    (row,) = table.rows
    assert (row.kind, row.mass, table.base, table.share(row.mass)) == (query.REGULAR, 0, 0, None)


def test_narrow_refuses_an_undeclared_value_and_an_open_one_no_fact_carries(facts):
    for dim, vocabulary in schema.VOCABULARY.items():
        with pytest.raises(schema.SchemaError, match="unknown %s" % dim):
            query.narrow(facts, [(dim, "bogus")], fx.DELTA)
        assert query.narrow(facts, [(dim, vocabulary[0])], fx.DELTA)  # vacuity guard
        without = [f for f in facts if f.dims.get(dim) != vocabulary[0]]
        assert len(without) < len(facts)  # vacuity guard: the value was carried
        assert query.narrow(without, [(dim, vocabulary[0])], fx.DELTA) == []  # declared: a zero, answered
    with pytest.raises(schema.SchemaError) as refused:
        query.narrow(facts, [(schema.TOOL_DIM, "bogus")], fx.DELTA)
    assert str(refused.value).endswith("present: Bash")  # the one tool an exact increment carries
    assert not query.select(facts, [(schema.TOOL_DIM, "bogus")])  # the plain filter just matches nothing


def test_a_refusal_names_the_first_values_present_and_counts_the_rest():
    def booked(tool):
        return schema.fact(schema.INCREMENT, {schema.CAUSE_DIM: schema.TOOL_RESULT, schema.TOOL_DIM: tool},
                           {fx.DELTA: 1}, Locator("f", 1, None))
    many = [booked("t%02d" % i) for i in range(query.LISTED + 3)]
    with pytest.raises(schema.SchemaError) as refused:
        query.narrow(many, [(schema.TOOL_DIM, "bogus")], fx.DELTA)
    message = str(refused.value)  # what the cli prints: the text, never a repr
    assert message.endswith("t%02d (+3 more; --by %s lists them all)" % (query.LISTED - 1, schema.TOOL_DIM))
    assert "t%02d" % query.LISTED not in message
    with pytest.raises(schema.SchemaError) as refused:
        query.narrow(many[:query.LISTED], [(schema.TOOL_DIM, "bogus")], fx.DELTA)
    assert str(refused.value).endswith("t%02d" % (query.LISTED - 1))  # at the cap, every value is named


def test_select_matches_every_pair_regardless_of_order(facts):
    where = [(schema.HEAD_DIM, "Bash:pytest"), (schema.CAUSE_DIM, schema.TOOL_RESULT)]
    hits = query.select(facts, where)
    assert hits and hits == query.select(facts, where[::-1])
    assert all(f.dims[schema.HEAD_DIM] == "Bash:pytest" for f in hits)
    assert query.select(facts, [(schema.REASON_DIM, schema.MULTI_CONTRIBUTOR)])
    assert not query.select(facts, [(schema.HEAD_DIM, "pytest")])  # a head carries its tool


def test_relabels_maps_only_dimensions_that_split_the_facts_alike(tmp_path):
    """In the CLI corpus each project holds one session and each tool one
    head: their tables would repeat row for row. Agent and session split
    the facts otherwise (two main sessions share no agent)."""
    facts = fx.load_facts(fx.cli_corpus(tmp_path))[1]
    assert query.relabels(facts, schema.SESSION_DIM, schema.PROJECT_DIM, fx.DELTA) == {
        "sess-0001": "proj-a", "sess-0002": "proj-b"}
    assert query.relabels(facts, schema.TOOL_DIM, schema.HEAD_DIM, fx.DELTA) == {"Bash": "Bash:pytest"}
    assert query.relabels(facts, schema.AGENT_DIM, schema.SESSION_DIM, fx.DELTA) is None
    assert query.relabels(facts, schema.CAUSE_DIM, schema.TOOL_DIM, fx.DELTA) is None
    out = fx.run_cli("context", "--root", str(fx.cli_corpus(tmp_path / "cli")))[1]
    assert "\nby %s: the rows above, labelled proj-a, proj-b\n" % schema.PROJECT_DIM in out
    assert not re.search(r"^by %s\s" % schema.PROJECT_DIM, out, re.M)  # guard: no table besides
