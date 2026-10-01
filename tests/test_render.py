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
DIM = schema.REASON_DIM  # declared, with no residual note
TOOL, HEAD = schema.TOOL_DIM, schema.HEAD_DIM


def test_table_limit_reports_hidden_rows_and_never_hides_residual_or_shrink():
    table = query.Table(DIM, ROWS, 100)
    lines = render._table(table, M, K, limit=1, whole=False)
    assert lines[0].startswith("by " + DIM) and lines[0].endswith("share of 100")
    assert [l.split()[0] for l in lines[1:]] == ["a", "+2", render.RESIDUAL_LABEL, schema.SHRINK]
    assert re.match(r"\+2 more rows\s+40\s+2\s+40\.0%", lines[2])
    assert [l.split()[0] for l in render._table(table, M, K, limit=3, whole=False)[1:]] == [
        "a", "b", "c", render.RESIDUAL_LABEL, schema.SHRINK]
    for dim in render.RESIDUAL_NOTES:
        noted = render._table(table._replace(dim=dim), M, K, limit=3, whole=False)
        assert noted[-1] == render.RESIDUAL_NOTES[dim]
        no_residual = render._table(query.Table(dim, ROWS[:3], 100), M, K, 3, whole=False)
        assert render.RESIDUAL_NOTES[dim] not in no_residual


def test_the_mass_column_is_the_metric_and_the_count_column_its_carrier_kind():
    table = query.Table(DIM, ROWS, 100)
    for kind in schema.KINDS:
        header = render._table(table, M, kind, limit=3, whole=False)[0].split()
        assert header == ["by", DIM, M, kind + "s", "share", "of", "100"]
    header = render._table(table, M, K, limit=3, whole=False)[0]
    assert "count" not in header
    for name, spec in schema.METRICS.items():  # the unit never heads the mass column
        assert render._table(table, name, spec.carrier, limit=3, whole=False)[0].split() == [
            "by", DIM, name, spec.carrier + "s", "share", "of", "100"]
        assert spec.unit != name  # vacuity guard: the two are distinguishable


def test_a_zero_base_table_truncates_without_a_share():
    zero = query.Table(DIM, [r._replace(mass=0) for r in ROWS[:3]], 0)
    lines = render._table(zero, M, K, limit=1, whole=False)
    assert lines[0].endswith("  share") and "share of" not in lines[0]
    assert re.match(r"\+2 more rows\s+0\s+2\s+-$", lines[2])
    facts = [f._replace(metrics={fx.DELTA: 0}) for f in FACTS[:3]]
    assert render._top(facts, [TOOL], fx.DELTA, total=0) == ""
    assert render._top(facts, [TOOL], fx.DELTA, total=5) == (
        "; top %s=Bash 0 (0.0%% of the 5 total)" % TOOL)  # vacuity guard


def _inc(mass, line, tool=None, head=None, cause=schema.TOOL_RESULT):
    """One increment of ``mass`` with the dimensions given."""
    dims = {schema.CAUSE_DIM: cause, TOOL: tool, HEAD: head}
    return schema.fact(schema.INCREMENT, {d: v for d, v in dims.items() if v is not None},
                       {fx.DELTA: mass}, Locator("f", line, None))


# Bash 90 = Bash:cat 60 + Bash:ls 30, Read 10, a residual 5 and a shrink -7: total 98.
FACTS = [_inc(60, 1, "Bash", "Bash:cat"), _inc(30, 2, "Bash", "Bash:ls"),
         _inc(10, 3, "Read", "Read:py"), _inc(5, 4, cause=schema.USER_TEXT),
         _inc(-7, 5, cause=schema.SHRINK)]


def test_headline_top_row_shares_the_total_it_is_given_never_the_table_base():
    """The tool table's share column is over its base, 100 (the total less
    the residual and signed rows); the headline says the row's share of the
    headline total, and names that total."""
    assert query.group(FACTS, TOOL, fx.DELTA).base == 100 != query.total(FACTS, fx.DELTA) == 98
    assert render._top(FACTS, [TOOL], fx.DELTA, total=98) == (
        "; top %s=Bash 90 (91.8%% of the 98 total)" % TOOL)
    assert render._top(FACTS, [TOOL], fx.DELTA, total=100) == (
        "; top %s=Bash 90 (90.0%% of the 100 total)" % TOOL)
    assert render._top(FACTS[3:], [TOOL], fx.DELTA, total=98) == ""  # no regular row
    assert render._top(FACTS, [], fx.DELTA, total=98) == ""          # every lever pinned


def test_the_headline_walks_down_the_levers_while_the_top_row_lies_within_the_one_before():
    """The top head Bash:cat lies within the top tool Bash: a refinement.
    With Bash = Bash:ls 60 + Bash:make 40 and Read:py 70 the top head lies
    under another tool, so the tool clause stands alone."""
    assert render._top(FACTS, [TOOL, HEAD], fx.DELTA, total=98) == (
        "; top %s=Bash 90 (91.8%% of the 98 total); within it %s=Bash:cat 60 (61.2%%)" % (TOOL, HEAD))
    other = [_inc(60, 1, "Bash", "Bash:ls"), _inc(40, 2, "Bash", "Bash:make"),
             _inc(70, 3, "Read", "Read:py")]
    assert render._top(other, [HEAD], fx.DELTA, total=170).startswith(
        "; top %s=Read:py 70 " % HEAD)  # the top head on its own
    assert render._top(other, [TOOL, HEAD], fx.DELTA, total=170) == (
        "; top %s=Bash 100 (58.8%% of the 170 total)" % TOOL)


def test_a_long_label_keeps_its_tail_behind_an_ellipsis_unless_the_table_is_whole():
    long = "proj/" + "x" * 120 + "/sub.jsonl"
    assert len(long) > render.LABEL_WIDTH  # vacuity guard
    rows = [query.Row(long, 60, 2, query.REGULAR), query.Row("short", 30, 1, query.REGULAR)]
    table = query.Table(schema.WINDOW_DIM, rows, 90)
    lines = render._table(table, M, K, limit=3, whole=False)
    label = lines[1].split()[0]
    assert label == "…" + long[1 - render.LABEL_WIDTH:] and len(label) == render.LABEL_WIDTH
    assert lines[2].startswith("short" + " " * (render.LABEL_WIDTH - 5) + "  ")  # the column is capped
    at_cap = "y" * render.LABEL_WIDTH
    assert render._label(query.Row(at_cap, 1, 1, query.REGULAR), whole=False) == at_cap  # at the cap
    whole = render._table(table, M, K, limit=3, whole=True)
    assert whole[1].split()[0] == long and whole[2].startswith("short" + " " * (len(long) - 5) + "  ")


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
