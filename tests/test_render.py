"""Table, headline and leaf rendering over hand-built rows and facts:
truncation, the rows that never hide, the headline share of the total, and
the leaf order."""
import re

import pytest

import fixtures as fx
from sa import cli, glossary, grammar, headline, leaves, query, render, residual, schema, tables
from sa.schema import Locator

ROWS = [query.Row("a", 60, 2, query.REGULAR), query.Row("b", 30, 1, query.REGULAR),
        query.Row("c", 10, 1, query.REGULAR), query.Row(None, 5, 1, query.RESIDUAL),
        query.Row(schema.SHRINK, -7, 1, query.SIGNED)]
M = fx.DELTA  # the increment metric; its carrier kind names the count column
DIM = schema.PROJECT_DIM  # declared, with no residual note
TOOL, HEAD = schema.TOOL_DIM, schema.COMMAND_DIM


def _top(facts, levers, metric):
    """The lever walk as the headline reads it: the top row, then the path."""
    top, path = headline._path(facts, levers, metric)
    return "" if top is None else "%s %s%s" % (top.value, tables.num(top.mass), path)


def test_table_limit_reports_hidden_rows_and_never_hides_residual_or_shrink():
    table = query.Table(DIM, ROWS, 100)
    more = grammar.run("context", grammar.BY, DIM)
    lines = tables.table(table, M, limit=1, more=more)
    assert lines[0].startswith(tables.title(DIM)) and lines[0].endswith("  share")
    assert [l.split()[0] for l in lines[1:]] == ["a", "+2", tables.BASE_LABEL.split()[0],
                                                 residual.label(DIM).split()[0], schema.SHRINK]
    assert re.match(r"\+2 more\s+40\s+2\s+40\.0%%  %s$" % re.escape(more), lines[2])  # what it cut, and how to see it
    assert re.match(r"%s\s+100\s+4  %s$" % (re.escape(tables.BASE_LABEL), re.escape(  # its base, named
        tables.BASE_NOTE % residual.label(DIM))), lines[3])
    assert [l.split()[0] for l in tables.table(table, M, limit=3)[1:]] == [
        "a", "b", "c", tables.BASE_LABEL.split()[0], residual.label(DIM).split()[0], schema.SHRINK]
    for dim, (meaning, cases) in residual.RESIDUAL_NOTES.items():  # -v says each
        assert all(
            text in residual.residual_cases(dim) for text, _ in cases)


def test_every_dimension_a_view_can_group_with_a_residual_row_has_a_note(tmp_path):
    """The fixture carries every cause and reason, a main window and a
    subagent's, so each dimension that can lack a value does so here, and
    every fact in a residual row is read by a case of the row's note."""
    facts = fx.load_facts(fx.every_corpus(tmp_path))[1]
    calls = sum(f.kind == schema.CALL for f in facts)
    grouped = [query.group(facts, dim, view.metric, calls if schema.metric(view.metric).aggregation
                           == schema.PER_CALL else None) for view in cli.VIEWS.values()
               for dim in schema.KIND_DIMENSIONS[schema.metric(view.metric).carrier]]
    with_residual = {t.dim for t in grouped if t.residual}
    assert schema.REASON_DIM in with_residual and len(with_residual) > 1  # vacuity guard
    assert with_residual <= set(residual.RESIDUAL_NOTES), with_residual - set(residual.RESIDUAL_NOTES)
    for t in grouped:
        cases = residual.RESIDUAL_NOTES.get(t.dim, ("", []))[1]
        if cases:
            assert all(any(holds(dims) for _, holds in cases) for dims in t.residual), t.dim
    note = residual.residual_note(schema.REASON_DIM, next(t.residual for t in grouped
                                                        if t.dim == schema.REASON_DIM))
    assert all(c in note for c in schema.CAUSES if c not in (schema.AMBIGUOUS, schema.SHRINK))
    assert schema.SHRINK not in note  # it is the signed row, never the residual


def test_the_mass_column_is_the_metric_and_the_count_column_its_carrier_kind():
    table = query.Table(DIM, ROWS, 100)
    for name, spec in schema.METRICS.items():  # the metric as printed heads the mass column
        header = tables.table(table, name, limit=3)[0]
        assert re.match(r"by %s +%s +%s +share$" % (
            DIM, re.escape(glossary.printed(name)), schema.PLURAL[spec.carrier]), header), header
        assert "count" not in header
    assert {spec.carrier for spec in schema.METRICS.values()} == set(schema.KINDS)  # both kinds seen


def test_a_zero_base_table_truncates_without_a_share():
    zero = query.Table(DIM, [r._replace(mass=0) for r in ROWS[:3]], 0)
    lines = tables.table(zero, M, limit=1)
    assert lines[0].endswith("  share")
    assert re.match(r"\+2 more\s+0\s+2\s+-$", lines[2])
    assert headline._block([("growth", 0, 0 / 5, "Bash")], [])[0].split()[2] == "0.0%"


def _inc(mass, line, tool=None, head=None, cause=schema.TOOL_RESULT):
    """One increment of ``mass`` with the dimensions given."""
    dims = {schema.CAUSE_DIM: cause, TOOL: tool, HEAD: head}
    return schema.fact(schema.INCREMENT, {d: v for d, v in dims.items() if v is not None},
                       {fx.DELTA: mass}, Locator("f", line, None))


# Bash 90 = Bash:cat 60 + Bash:ls 30, Read 10, a residual 5 and a shrink -7: total 98.
FACTS = [_inc(60, 1, "Bash", "Bash:cat"), _inc(30, 2, "Bash", "Bash:ls"),
         _inc(10, 3, "Read", "Read:py"), _inc(5, 4, cause=schema.USER_TEXT),
         _inc(-7, 5, cause=schema.SHRINK)]


def test_headline_block_shares_the_mass_added_never_the_table_base():
    """The tool table's share column is over its base, 100 (the total less
    the residual and signed rows); the headline's block says a line's
    share of the added when it has one (a largest row's is its table's:
    one share a figure), aligned in columns."""
    assert query.group(FACTS, TOOL, fx.DELTA).base == 100 != query.total(FACTS, fx.DELTA) == 98
    assert _top(FACTS, [TOOL], fx.DELTA) == "Bash 90"
    block = headline._block([("starting", 8, 8 / 98, ""), ("largest tool", 90, None, "Bash")], [])
    assert block == ["  starting       8   8.2%", "  largest tool  90  Bash"]
    assert block[1].values == ((len(block[1]) - len("Bash"), len(block[1])),)  # a value, never a term
    assert _top(FACTS[3:], [TOOL], fx.DELTA) == ""  # no regular row
    assert _top(FACTS, [], fx.DELTA) == ""          # every lever pinned


def test_the_headline_refines_the_top_row():
    """The head within the top tool Bash is Bash:cat, 60 of Bash's 90.
    Here it is also the top head overall, so nothing follows."""
    assert _top(FACTS, [TOOL, HEAD], fx.DELTA) == "Bash 90 → Bash:cat 60"


def test_a_larger_head_under_another_lead_follows_the_refinement():
    """Bash = Bash:ls 60 + Bash:make 40 and Read:py 70: the head within
    Bash is Bash:ls, but the top head overall is Read:py, so it is named
    too."""
    other = [_inc(60, 1, "Bash", "Bash:ls"), _inc(40, 2, "Bash", "Bash:make"),
             _inc(70, 3, "Read", "Read:py")]
    assert _top(other, [HEAD], fx.DELTA) == "Read:py 70"  # the top head on its own
    assert _top(other, [TOOL, HEAD], fx.DELTA) == "Bash 100 → Bash:ls 60; top %s Read:py 70" % HEAD
    assert "; top" not in _top(FACTS, [TOOL, HEAD], fx.DELTA)  # vacuity guard


def test_an_equal_head_under_another_tool_is_not_named_as_the_top():
    """Read:py 60 ties Bash:ls 60 within Bash and, booked first, wins the
    head table's stable sort: only a strictly larger head is named."""
    tie = [_inc(60, 1, "Read", "Read:py"), _inc(60, 2, "Bash", "Bash:ls"), _inc(40, 3, "Bash", "Bash:make")]
    assert headline._largest(query.group(tie, HEAD, fx.DELTA)).value == "Read:py"
    assert _top(tie, [TOOL, HEAD], fx.DELTA) == "Bash 100 → Bash:ls 60"
    larger = [tie[0]._replace(metrics={fx.DELTA: 61})] + tie[1:]  # vacuity guard
    assert _top(larger, [TOOL, HEAD], fx.DELTA).endswith("; top %s Read:py 61" % HEAD)


def test_a_top_tool_with_no_head_still_names_the_top_head():
    """Agent 90 carries no head, so nothing is within it; the top head
    anywhere, Bash:cat 60, is still named. With no head anywhere the tool
    stands alone."""
    headless = [_inc(90, 1, "Agent"), _inc(60, 2, "Bash", "Bash:cat")]
    assert _top(headless, [TOOL, HEAD], fx.DELTA) == "Agent 90; top %s Bash:cat 60" % HEAD
    assert _top(headless[:1], [TOOL, HEAD], fx.DELTA) == "Agent 90"
    assert "→" in _top(FACTS, [TOOL, HEAD], fx.DELTA)  # vacuity guard


def test_the_cause_table_prints_whole_whatever_the_limit(tmp_path):
    """The default limit folds the other tables but never the cause
    table; the folded line counts only the rows it hides."""
    root = fx.cli_corpus(tmp_path)
    facts = fx.load_facts(root)[1]
    grouped = query.group(facts, schema.CAUSE_DIM, fx.DELTA)
    regular = [r for r in grouped.rows if r.kind == query.REGULAR]
    assert len(regular) > 2  # vacuity guard: a limit of 1 would fold it
    whole = tables.table(grouped, M, limit=1)
    assert [l.split()[0] for l in whole[1:len(regular) + 1]] == [r.value for r in regular]
    assert not any(l.startswith("+") for l in whole)
    grouped = query.Table(DIM, ROWS, 100)
    folded = [l.split() for l in tables.table(grouped, M, limit=1)[1:]]
    regular = [r for r in ROWS if r.kind == query.REGULAR]
    assert folded[1][:2] == ["+%d" % (len(regular) - 1), "more"]
    assert folded[1][2:4] == [tables.num(sum(r.mass for r in regular[1:])),
                              tables.num(sum(r.count for r in regular[1:]))]


def test_a_row_named_like_a_cause_folds_and_gets_no_note_outside_the_cause_table():
    """A project called ``ambiguous`` is an ordinary row: a limit of 1 folds
    it; the same rows as the cause table keep it, with their gloss."""
    causes = [schema.STARTING_CONTEXT, schema.AMBIGUOUS]
    rows = [query.Row("a", 60, 2, query.REGULAR)] + [query.Row(cause, 10, 1, query.REGULAR) for cause in causes]
    assert DIM != schema.CAUSE_DIM  # vacuity guard
    lines = tables.table(query.Table(DIM, rows, 80), M, limit=1, glosses=render.GLOSSES)
    assert [l.split()[0] for l in lines[1:]] == ["a", "+%d" % len(causes), tables.BASE_LABEL.split()[0]]
    kept = tables.table(query.Table(schema.CAUSE_DIM, rows, 80), M, limit=1, glosses=render.GLOSSES)
    assert [l.split()[0] for l in kept[1:len(rows) + 1]] == ["a"] + causes
    assert all(l.endswith(render.GLOSSES[c]) for l, c in zip(kept[2:], causes))


def test_the_ambiguous_entry_names_every_declared_reason_and_the_gloss_none():
    """The gloss beside the row is a few words; ``-v`` the reasons."""
    entry, gloss = glossary.GLOSSARY[schema.AMBIGUOUS], render.GLOSSES[schema.AMBIGUOUS]
    meaning = entry.meaning + " " + entry.surprise  # -v prints both: the sentence, then the cases
    assert len(schema.REASONS) > 1 and all(reason in meaning for reason in schema.REASONS)
    assert gloss and not any(reason in gloss for reason in schema.REASONS)


def test_the_glossary_states_the_measured_conditions():
    """ambiguous covers the negative remainder, and a shrink is not always a
    compaction (measured: 3 of 8 carried no compaction marker)."""
    meaning = lambda term: glossary.GLOSSARY[term].meaning + " " + glossary.GLOSSARY[term].surprise
    condition = "less than the previous call's reply"
    assert condition in meaning(schema.AMBIGUOUS)
    assert condition in meaning(schema.LESS_THAN_REPLY)  # the same wording
    assert "compaction" in meaning(schema.SHRINK) and "not always" in meaning(schema.SHRINK)


def test_a_long_label_prints_whole_and_widens_its_column():
    """A label pins its row as printed, so it is never cut."""
    long = "proj/" + "x" * 120 + "/sub.jsonl"
    rows = [query.Row(long, 60, 2, query.REGULAR), query.Row("short", 30, 1, query.REGULAR)]
    lines = tables.table(query.Table(schema.WINDOW_DIM, rows, 90), M, limit=3)
    assert lines[1].split()[0] == long and lines[2].startswith("short" + " " * (len(long) - 5) + "  ")


def test_leaves_are_ordered_by_magnitude_so_a_large_shrink_leads():
    def leaf(cause, delta, line):
        return schema.fact(schema.INCREMENT, {schema.CAUSE_DIM: cause}, {fx.DELTA: delta},
                           Locator("f", line, "u-%d" % line))
    exact, shrink = leaf(schema.USER_TEXT, 100, 1), leaf(schema.SHRINK, -500, 2)
    assert abs(shrink.metrics[fx.DELTA]) > exact.metrics[fx.DELTA]  # the shrink is the larger
    lines = leaves.leaves([exact, shrink], fx.DELTA, None, -400)
    rows = [l.split()[:2] for l in lines if fx.LEAF.match(l)]
    assert rows == [["-500", ":2"], ["100", ":1"]]
    assert lines[-1].startswith("Σ 2 ") and lines[-1].endswith("%s the headline's -400" % tables.OK_MARK)


def test_a_leaf_and_a_candidate_without_a_uuid_print_their_line():
    """A bookkeeping record carries no uuid; its locator still has a line,
    which is unique in its file."""
    with_uuid = FACTS[0]._replace(locator=Locator("f", 1, "u-1"), evidence={
        schema.CANDIDATES: [schema.Candidate(Locator("f", 2, None), {})]})
    lines = leaves.leaves([with_uuid, FACTS[1]], fx.DELTA, None, 90)
    body = [l.split() for l in lines[3:-1]]
    assert body[0][:2] == ["60", ":1"]
    assert body[1] == [schema.CANDIDATES + ":"] and body[2] == ["└", ":2"]  # the candidate without one
    assert body[3][:2] == ["30", ":2"]  # the leaf without one
    assert "None" not in "\n".join(lines)