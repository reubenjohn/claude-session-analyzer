"""Table, headline and leaf rendering over hand-built rows and facts:
truncation, the rows that never hide, the headline share of the total, and
the leaf order."""
import re

import fixtures as fx
from sa import query, render, schema
from sa.schema import Locator

ROWS = [query.Row("a", 60, 2, query.REGULAR), query.Row("b", 30, 1, query.REGULAR),
        query.Row("c", 10, 1, query.REGULAR), query.Row(None, 5, 1, query.RESIDUAL),
        query.Row(schema.SHRINK, -7, 1, query.SIGNED)]
M, K = "m", schema.INCREMENT  # a metric name and its carrier kind


def test_table_limit_reports_hidden_rows_and_never_hides_residual_or_shrink():
    table = query.Table("x", ROWS, 100)
    lines = render._table(table, M, K, limit=1)
    assert lines[0].startswith("by x") and lines[0].endswith("share of 100")
    assert [l.split()[0] for l in lines[1:]] == ["a", "+2", render.RESIDUAL_LABEL, schema.SHRINK]
    assert re.match(r"\+2 more rows\s+40\s+2\s+40\.0%", lines[2])
    assert [l.split()[0] for l in render._table(table, M, K, limit=3)[1:]] == [
        "a", "b", "c", render.RESIDUAL_LABEL, schema.SHRINK]
    for dim in render.RESIDUAL_NOTES:
        assert render._table(table._replace(dim=dim), M, K, limit=3)[-1] == render.RESIDUAL_NOTES[dim]
        no_residual = render._table(query.Table(dim, ROWS[:3], 100), M, K, 3)
        assert render.RESIDUAL_NOTES[dim] not in no_residual


def test_the_mass_column_is_the_metric_and_the_count_column_its_carrier_kind():
    table = query.Table("x", ROWS, 100)
    for kind in schema.KINDS:
        header = render._table(table, M, kind, limit=3)[0].split()
        assert header == ["by", "x", M, kind + "s", "share", "of", "100"]
    header = render._table(table, M, K, limit=3)[0]
    assert "count" not in header
    for name, spec in schema.METRICS.items():  # the unit never heads the mass column
        assert render._table(table, name, spec.carrier, limit=3)[0].split() == [
            "by", "x", name, spec.carrier + "s", "share", "of", "100"]
        assert spec.unit != name  # vacuity guard: the two are distinguishable


def test_a_zero_base_table_truncates_without_a_share():
    zero = query.Table("x", [r._replace(mass=0) for r in ROWS[:3]], 0)
    lines = render._table(zero, M, K, limit=1)
    assert lines[0].endswith("  share") and "share of" not in lines[0]
    assert re.match(r"\+2 more rows\s+0\s+2\s+-$", lines[2])
    assert render._top(zero, total=0) == ""
    assert render._top(zero, total=5) == "; top x=a 0 (0.0% of the 5 total)"  # vacuity guard


def test_headline_top_row_shares_the_total_it_is_given_never_the_table_base():
    """The table's share column is over its base (100 here); the headline
    says the row's share of the headline total, and names that total."""
    table = query.Table("x", ROWS, 100)
    assert render._top(table, total=98) == "; top x=a 60 (61.2% of the 98 total)"
    assert render._top(table, total=100) == "; top x=a 60 (60.0% of the 100 total)"
    assert render._top(query.Table("x", ROWS[3:], 0), total=98) == ""  # no regular row
    unsplittable = [query.Row(value, 900 - n, 1, query.REGULAR)
                    for n, value in enumerate(render.UNSPLITTABLE)]
    assert schema.AMBIGUOUS in render.UNSPLITTABLE  # the residual bucket is never the lever
    assert render._top(query.Table("x", unsplittable + ROWS[:3], 1000), total=1000) == (
        "; top x=a 60 (6.0% of the 1,000 total)")
    assert render._top(query.Table("x", unsplittable, 1000), total=1000) == ""


def test_leaves_are_ordered_by_magnitude_so_a_large_shrink_is_not_hidden_by_limit():
    def leaf(cause, delta, line):
        return schema.fact(schema.INCREMENT, {schema.CAUSE_DIM: cause}, {fx.DELTA: delta},
                           Locator("f", line, "u-%d" % line))
    exact, shrink = leaf(schema.USER_TEXT, 100, 1), leaf(schema.SHRINK, -500, 2)
    assert abs(shrink.metrics[fx.DELTA]) > exact.metrics[fx.DELTA]  # the shrink is the larger
    lines = render._leaves([exact, shrink], fx.DELTA, limit=1)
    assert len(lines) == 2 and lines[1].split()[:2] == ["-500", "f:2"]
    both = render._leaves([exact, shrink], fx.DELTA, limit=2)
    assert [l.split()[0] for l in both[1:]] == ["-500", "100"]
