"""Table and headline rendering over hand-built rows: truncation, the rows
that never hide, and the share whose base is not the total."""
import re

from sa import query, render, schema

ROWS = [query.Row("a", 60, 2, query.REGULAR), query.Row("b", 30, 1, query.REGULAR),
        query.Row("c", 10, 1, query.REGULAR), query.Row(None, 5, 1, query.RESIDUAL),
        query.Row(schema.SHRINK, -7, 1, query.SIGNED)]
U = schema.Metric(schema.ADDITIVE, schema.INCREMENT, "u")


def test_table_limit_reports_hidden_rows_and_never_hides_residual_or_shrink():
    table = query.Table("x", ROWS, 100)
    lines = render._table(table, U, limit=1)
    assert lines[0].startswith("by x") and lines[0].endswith("share of 100")
    assert [l.split()[0] for l in lines[1:]] == ["a", "+2", render.RESIDUAL_LABEL, schema.SHRINK]
    assert re.match(r"\+2 more rows\s+40\s+2\s+40\.0%", lines[2])
    assert [l.split()[0] for l in render._table(table, U, limit=3)[1:]] == [
        "a", "b", "c", render.RESIDUAL_LABEL, schema.SHRINK]
    for dim in render.RESIDUAL_NOTES:
        assert render._table(table._replace(dim=dim), U, limit=3)[-1] == render.RESIDUAL_NOTES[dim]
        no_residual = render._table(query.Table(dim, ROWS[:3], 100), U, 3)
        assert render.RESIDUAL_NOTES[dim] not in no_residual


def test_the_count_column_is_named_for_the_carrier_kind():
    table = query.Table("x", ROWS, 100)
    for kind in schema.KINDS:
        header = render._table(table, U._replace(carrier=kind), limit=3)[0].split()
        assert header == ["by", "x", "u", kind + "s", "share", "of", "100"]
    assert "count" not in render._table(table, U, limit=3)[0]


def test_a_zero_base_table_truncates_without_a_share():
    zero = query.Table("x", [r._replace(mass=0) for r in ROWS[:3]], 0)
    lines = render._table(zero, U, limit=1)
    assert lines[0].endswith("  share") and "share of" not in lines[0]
    assert re.match(r"\+2 more rows\s+0\s+2\s+-$", lines[2])
    assert render._top(zero) == ""


def test_headline_top_row_names_its_base_by_what_the_other_rows_lack():
    assert render._top(query.Table("x", ROWS, 100)) == "; top x=a 60 (60.0% of 100 added with a x)"
    assert render._top(query.Table("x", ROWS[:4], 100)) == "; top x=a 60 (60.0% of 100 with a x)"
    assert render._top(query.Table("x", ROWS[:3] + ROWS[4:], 100)) == "; top x=a 60 (60.0% of 100 added)"
    assert render._top(query.Table("x", ROWS[:3], 100)) == "; top x=a 60 (60.0%)"
    assert render._top(query.Table("x", ROWS[3:], 0)) == ""  # no regular row
    unsplittable = query.Row(next(iter(render.UNSPLITTABLE)), 900, 1, query.REGULAR)
    assert render._top(query.Table("x", [unsplittable] + ROWS[:3], 1000)) == "; top x=a 60 (6.0%)"
