"""Table, headline and leaf rendering over hand-built rows and facts:
truncation, the rows that never hide, the headline share of the total, and
the leaf order."""
import re

import pytest

import fixtures as fx
from sa import cli, glossary, headline, query, render, schema, tables
from sa.schema import Locator

ROWS = [query.Row("a", 60, 2, query.REGULAR), query.Row("b", 30, 1, query.REGULAR),
        query.Row("c", 10, 1, query.REGULAR), query.Row(None, 5, 1, query.RESIDUAL),
        query.Row(schema.SHRINK, -7, 1, query.SIGNED)]
M = fx.DELTA  # the increment metric; its carrier kind names the count column
DIM = schema.PROJECT_DIM  # declared, with no residual note
TOOL, HEAD = schema.TOOL_DIM, schema.COMMAND_DIM


def _top(*args, **kwargs):
    """The lever walk's clauses as the headline reads them, ``; ``-joined."""
    return "".join("; " + clause for clause in headline._top(*args, **kwargs))


def test_table_limit_reports_hidden_rows_and_never_hides_residual_or_shrink():
    table = query.Table(DIM, ROWS, 100)
    lines = tables.table(table, M, limit=1, whole=False)
    assert lines[0].startswith("by " + DIM) and lines[0].endswith("share of 100 (all but ∅)")
    assert [l.split()[0] for l in lines[1:]] == ["a", "+2", tables.RESIDUAL_LABEL, schema.SHRINK]
    assert re.match(r"\+2 more rows\s+40\s+2\s+40\.0%", lines[2])
    assert [l.split()[0] for l in tables.table(table, M, limit=3, whole=False)[1:]] == [
        "a", "b", "c", tables.RESIDUAL_LABEL, schema.SHRINK]
    for dim, (meaning, _) in tables.RESIDUAL_NOTES.items():  # a residual row's note is in the key
        noted = tables.notes(table._replace(dim=dim))
        assert noted[-1] == (tables.residual_label(dim), meaning) == (
            tables.marked(tables.RESIDUAL_LABEL) + " by " + dim, tables.residual_note(dim, ()))
        assert noted[-1] not in tables.notes(query.Table(dim, ROWS[:3], 100))  # no residual row
    assert tables.notes(table) == []  # vacuity guard: DIM has no note


def test_every_dimension_a_view_can_group_with_a_residual_row_has_a_note(tmp_path):
    """The fixture carries every cause and reason, a main window and a
    subagent's, so each dimension that can lack a value does so here, and
    every fact in a residual row is read by a case of the row's note."""
    facts = fx.load_facts(fx.every_corpus(tmp_path))[1]
    grouped = [query.group(facts, dim, view.metric) for view in cli.VIEWS.values()
               for dim in schema.KIND_DIMENSIONS[schema.metric(view.metric).carrier]]
    with_residual = {t.dim for t in grouped if t.residual}
    assert schema.REASON_DIM in with_residual and len(with_residual) > 1  # vacuity guard
    assert with_residual <= set(tables.RESIDUAL_NOTES), with_residual - set(tables.RESIDUAL_NOTES)
    for t in grouped:
        cases = tables.RESIDUAL_NOTES.get(t.dim, ("", []))[1]
        if cases:
            assert all(any(holds(dims) for _, holds in cases) for dims in t.residual), t.dim
    note = tables.residual_note(schema.REASON_DIM, next(t.residual for t in grouped
                                                        if t.dim == schema.REASON_DIM))
    assert all(c in note for c in schema.CAUSES if c not in (schema.AMBIGUOUS, schema.SHRINK))
    assert schema.SHRINK not in note  # it is the signed row, never the residual


def test_the_mass_column_is_the_metric_and_the_count_column_its_carrier_kind():
    table = query.Table(DIM, ROWS, 100)
    for name, spec in schema.METRICS.items():  # the metric as printed heads the mass column
        header = tables.table(table, name, limit=3, whole=False)[0]
        assert re.match(r"by %s +%s +%s +share of 100 \(all but ∅\)$" % (
            DIM, re.escape(glossary.printed(name)), schema.PLURAL[spec.carrier]), header), header
        assert "count" not in header
    assert {spec.carrier for spec in schema.METRICS.values()} == set(schema.KINDS)  # both kinds seen


def test_a_zero_base_table_truncates_without_a_share():
    zero = query.Table(DIM, [r._replace(mass=0) for r in ROWS[:3]], 0)
    lines = tables.table(zero, M, limit=1, whole=False)
    assert lines[0].endswith("  share") and "share of" not in lines[0]
    assert re.match(r"\+2 more rows\s+0\s+2\s+-$", lines[2])
    facts = [f._replace(metrics={fx.DELTA: 0}) for f in FACTS[:3]]
    assert _top(facts, [TOOL], fx.DELTA, total=0) == ""
    assert _top(facts, [TOOL], fx.DELTA, total=5) == (
        "; %s=Bash 0 (0.0%%)" % TOOL)  # vacuity guard
    assert _top(facts, [TOOL, HEAD], fx.DELTA, total=5).endswith(
        "; %s=Bash:cat 0 (- of Bash, 0.0%%)" % HEAD)  # no share of a 0 row


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
    headline total, which the total line names once."""
    assert query.group(FACTS, TOOL, fx.DELTA).base == 100 != query.total(FACTS, fx.DELTA) == 98
    assert _top(FACTS, [TOOL], fx.DELTA, total=98) == (
        "; %s=Bash 90 (91.8%%)" % TOOL)
    assert _top(FACTS, [TOOL], fx.DELTA, total=100) == (
        "; %s=Bash 90 (90.0%%)" % TOOL)
    assert _top(FACTS[3:], [TOOL], fx.DELTA, total=98) == ""  # no regular row
    assert _top(FACTS, [], fx.DELTA, total=98) == ""          # every lever pinned


def test_the_headline_refines_the_top_row_and_names_both_bases():
    """The head within the top tool Bash is Bash:cat, 60 of Bash's 90 and
    of the 98 total: both shares print, the first naming Bash, since a
    lone share would read as a share of Bash. Here it is also the top
    head overall, so nothing follows."""
    assert _top(FACTS, [TOOL, HEAD], fx.DELTA, total=98) == (
        "; %s=Bash 90 (91.8%%); %s=Bash:cat 60 (66.7%% of Bash, 61.2%%)" % (TOOL, HEAD))


def test_a_top_row_under_another_lead_follows_the_refinement_naming_what_it_lies_under():
    """Bash = Bash:ls 60 + Bash:make 40 and Read:py 70: the head within
    Bash is Bash:ls, but the top head overall is Read:py, under Read, so
    it is named too with its tool and its share of the total."""
    other = [_inc(60, 1, "Bash", "Bash:ls"), _inc(40, 2, "Bash", "Bash:make"),
             _inc(70, 3, "Read", "Read:py")]
    assert _top(other, [HEAD], fx.DELTA, total=170) == (
        "; %s=Read:py 70 (41.2%%)" % HEAD)  # the top head on its own
    assert _top(other, [TOOL, HEAD], fx.DELTA, total=170) == (
        "; %s=Bash 100 (58.8%%); %s=Bash:ls 60 (60.0%% of Bash, 35.3%%); %s=Read:py 70 (41.2%%)"
        " under %s=Read" % (TOOL, HEAD, HEAD, TOOL))
    assert "under" not in _top(FACTS, [TOOL, HEAD], fx.DELTA, total=98)  # vacuity guard
    with pytest.raises(ValueError):  # Bash lies under two heads: the levers must nest
        _top(other, [HEAD, TOOL], fx.DELTA, total=170)


def test_an_equal_head_under_another_tool_is_not_named_as_the_top():
    """Read:py 60 ties Bash:ls 60 within Bash and, booked first, wins the
    head table's stable sort: ``under`` names only a strictly larger head."""
    tie = [_inc(60, 1, "Read", "Read:py"), _inc(60, 2, "Bash", "Bash:ls"), _inc(40, 3, "Bash", "Bash:make")]
    assert headline._largest(query.group(tie, HEAD, fx.DELTA)).value == "Read:py"
    assert _top(tie, [TOOL, HEAD], fx.DELTA, total=160) == (
        "; %s=Bash 100 (62.5%%); %s=Bash:ls 60 (60.0%% of Bash, 37.5%%)" % (TOOL, HEAD))
    larger = [tie[0]._replace(metrics={fx.DELTA: 61})] + tie[1:]  # vacuity guard
    assert _top(larger, [TOOL, HEAD], fx.DELTA, total=161).endswith(
        "; %s=Read:py 61 (37.9%%) under %s=Read" % (HEAD, TOOL))


def test_a_top_tool_with_no_head_still_names_the_top_head_under_its_tool():
    """Agent 90 carries no head, so nothing is within it; the top head
    anywhere, Bash:cat 60 under Bash, is still named. With no head anywhere
    the tool clause stands alone."""
    headless = [_inc(90, 1, "Agent"), _inc(60, 2, "Bash", "Bash:cat")]
    assert _top(headless, [TOOL, HEAD], fx.DELTA, total=150) == (
        "; %s=Agent 90 (60.0%%); %s=Bash:cat 60 (40.0%%) under %s=Bash" % (TOOL, HEAD, TOOL))
    assert _top(headless[:1], [TOOL, HEAD], fx.DELTA, total=90) == "; %s=Agent 90 (100.0%%)" % TOOL
    assert "%s=" % HEAD in _top(FACTS, [TOOL, HEAD], fx.DELTA, total=98)  # vacuity guard


def test_the_cause_table_prints_whole_whatever_the_limit(tmp_path):
    """D-PLAIN-TERMS: ``--limit 1`` folds the tool table but never the cause
    table, whose starting_context and ambiguous rows keep their notes; the
    folded line counts only the rows it hides."""
    root = fx.cli_corpus(tmp_path)

    def rows(*args):
        out = fx.run_cli("context", "--root", str(root), "--by", schema.CAUSE_DIM, *args)[1]
        return out, [l.split() for l in out.splitlines() if l.endswith("%")]

    full = rows()[1]
    assert len(full) > 2  # vacuity guard: a limit of 1 would fold it
    out, shown = rows("--limit", "1")
    assert shown == full and "more row" not in out
    for value, note in tables.UNSPLITTABLE.items():
        assert (tables.marked(value), note) in fx.key(out)
    grouped = query.Table(DIM, ROWS, 100)
    folded = [l.split() for l in tables.table(grouped, M, limit=1, whole=False)[1:]]
    regular = [r for r in ROWS if r.kind == query.REGULAR]
    assert folded[1][:3] == ["+%d" % (len(regular) - 1), "more", "rows"]
    assert folded[1][3:5] == [tables.num(sum(r.mass for r in regular[1:])),
                              tables.num(sum(r.count for r in regular[1:]))]


def test_a_row_named_like_a_cause_folds_and_gets_no_note_outside_the_cause_table():
    """A project called ``ambiguous`` is an ordinary row: ``--limit 1`` folds
    it and no cause note prints; the same rows as the cause table keep it."""
    rows = [query.Row("a", 60, 2, query.REGULAR)] + [
        query.Row(cause, 10, 1, query.REGULAR) for cause in tables.UNSPLITTABLE]
    assert DIM != schema.CAUSE_DIM and len(rows) > 2  # vacuity guard
    lines = tables.table(query.Table(DIM, rows, 80), M, limit=1, whole=False)
    assert [l.split()[0] for l in lines[1:]] == ["a", "+%d" % len(tables.UNSPLITTABLE)]
    kept = tables.table(query.Table(schema.CAUSE_DIM, rows, 80), M, limit=1, whole=False)
    assert [l.split()[0] for l in kept[1:] if l.endswith("%")] == ["a"] + list(tables.UNSPLITTABLE)
    assert tables.notes(query.Table(schema.CAUSE_DIM, rows, 80)) == [
        (tables.marked(cause), note) for cause, note in tables.UNSPLITTABLE.items()]
    assert tables.notes(query.Table(DIM, rows, 80)) == []


def test_the_ambiguous_entry_names_every_declared_reason_and_the_key_none():
    """D-PLAIN-TERMS: the key prints one clause; ``sa explain`` the reasons."""
    meaning, note = glossary.GLOSSARY[schema.AMBIGUOUS].meaning, tables.UNSPLITTABLE[schema.AMBIGUOUS]
    assert len(schema.REASONS) > 1 and all(reason in meaning for reason in schema.REASONS)
    assert not any(reason in note for reason in schema.REASONS) and note in glossary.brief(schema.AMBIGUOUS)


def test_the_glossary_states_the_measured_conditions():
    """exact needs growth >= the previous call's output, ambiguous covers the
    negative remainder, and a shrink is not always a compaction (measured:
    3 of 8 carried no compaction marker)."""
    meaning = lambda term: glossary.GLOSSARY[term].meaning
    condition = "less than the previous call's reply"
    assert condition in meaning(schema.AMBIGUOUS)
    assert condition in glossary.GLOSSARY[schema.LESS_THAN_REPLY].meaning  # the same wording
    assert "at least the previous call's reply" in meaning(glossary.EXACT)
    assert "compaction" in meaning(schema.SHRINK) and "not always" in meaning(schema.SHRINK)


def test_a_long_label_keeps_its_tail_behind_an_ellipsis_unless_the_table_is_whole():
    long = "proj/" + "x" * 120 + "/sub.jsonl"
    assert len(long) > tables.LABEL_WIDTH  # vacuity guard
    rows = [query.Row(long, 60, 2, query.REGULAR), query.Row("short", 30, 1, query.REGULAR)]
    table = query.Table(schema.WINDOW_DIM, rows, 90)
    lines = tables.table(table, M, limit=3, whole=False)
    label = lines[1].split()[0]
    assert label == "…" + long[1 - tables.LABEL_WIDTH:] and len(label) == tables.LABEL_WIDTH
    assert lines[2].startswith("short" + " " * (tables.LABEL_WIDTH - 5) + "  ")  # the column is capped
    at_cap = "y" * tables.LABEL_WIDTH
    assert tables._label(query.Row(at_cap, 1, 1, query.REGULAR), whole=False) == at_cap  # at the cap
    whole = tables.table(table, M, limit=3, whole=True)
    assert whole[1].split()[0] == long and whole[2].startswith("short" + " " * (len(long) - 5) + "  ")


def test_leaves_are_ordered_by_magnitude_so_a_large_shrink_is_not_hidden_by_limit():
    def leaf(cause, delta, line):
        return schema.fact(schema.INCREMENT, {schema.CAUSE_DIM: cause}, {fx.DELTA: delta},
                           Locator("f", line, "u-%d" % line))
    exact, shrink = leaf(schema.USER_TEXT, 100, 1), leaf(schema.SHRINK, -500, 2)
    assert abs(shrink.metrics[fx.DELTA]) > exact.metrics[fx.DELTA]  # the shrink is the larger
    lines = tables.leaves([exact, shrink], fx.DELTA, limit=1)
    assert len(lines) == 2 and lines[1].split()[:3] == ["-500", "f:2", "u-2"]
    both = tables.leaves([exact, shrink], fx.DELTA, limit=2)
    assert [l.split()[0] for l in both[1:]] == ["-500", "100"]


def test_a_leaf_without_a_uuid_prints_a_dash_in_the_uuid_column():
    """A bookkeeping record carries no uuid; its locator still has a line."""
    with_uuid = FACTS[0]._replace(locator=Locator("f", 1, "u-1"), evidence={
        schema.CANDIDATES: [schema.Candidate(Locator("f", 2, None), {})]})
    lines = tables.leaves([with_uuid, FACTS[1]], fx.DELTA, limit=2)
    assert lines[1].split()[:3] == ["60", "f:1", "u-1"]  # vacuity guard: a uuid prints
    assert lines[2].split() == [schema.CANDIDATES + ":"]
    assert lines[3].split()[:2] == ["f:2", "-"]           # the candidate without one
    assert lines[4].split()[:3] == ["30", "f:2", "-"]     # the leaf without one
    assert "None" not in "\n".join(lines)
