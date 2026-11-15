"""``python3 -m sa`` narrowed by ``--where`` and ``--by fact`` against
``fixtures.cli_corpus``: what a drill prints, what a window filter keeps.
What each view prints unnarrowed is ``test_cli``."""
import re

import fixtures as fx
from sa import cli, query, schema, tables

CONTEXT = cli.VIEWS["context"]
CAUSE, TOOL, HEAD = schema.CAUSE_DIM, schema.TOOL_DIM, schema.COMMAND_DIM


def test_shrink_is_selectable_and_its_leaves_are_listed(tmp_path):
    """Every table files shrink as a signed row, which is no reason for
    ``--where`` to deny the facts exist."""
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--where",
                                "%s=%s" % (CAUSE, schema.SHRINK), "--by", "fact")
    assert code == 0, err
    leaves = [l for l in out.splitlines() if re.match(r"\s+-?[\d,]+\s+\S+:\d+\s", l)]
    assert len(leaves) == 3 and all("%s=%s" % (CAUSE, schema.SHRINK) in l for l in leaves)
    assert all(l.split()[0] == "-100" for l in leaves)
    assert fx.headline(out).startswith("%s-300 over 3 changes where %s=%s in 3 windows" % (
        fx.total_line(CONTEXT.metric), CAUSE, schema.SHRINK))


def test_a_drill_prints_a_table_that_has_only_a_residual_row(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--where",
                          "%s=%s" % (CAUSE, schema.STARTING_CONTEXT), "--by", TOOL)
    assert code == 0, err
    assert re.search(r"^by %s\s" % TOOL, out, re.M)
    assert re.search(r"^%s\s+%s\s+3\s+-$" % (re.escape(tables.RESIDUAL_LABEL), format(3000, ",d")),
                     out, re.M)
    assert "; largest" not in fx.headline(out)
    assert re.search(r"^by %s\s.*\s+%s\s+share$" % (TOOL, fx.count_column(CONTEXT.metric)), out, re.M)
    assert "share of" not in out


def test_a_pinned_table_notes_only_the_cases_its_residual_row_holds(tmp_path):
    """Two Read results batched in one record: under ``--where tool=Read``
    the head table's residual is one ambiguous increment sharing the tool,
    so its note names that case alone, not ``no tool`` or a headless tool."""
    root = fx.batched_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--where", "%s=Read" % TOOL,
                                "--by", HEAD)
    assert code == 0, err
    notes = [text for label, text in fx.key(out) if label == tables.residual_label(HEAD)]
    assert notes == [tables.residual_note(HEAD, ({CAUSE: schema.AMBIGUOUS, TOOL: "Read"},))]
    assert schema.AMBIGUOUS in notes[0] and "no tool" not in notes[0] and "any but" not in notes[0]
    code, out, err = fx.run_cli("context", "--root", str(root), "--by", HEAD)
    unpinned = [text for label, text in fx.key(out) if label == tables.residual_label(HEAD)]
    assert code == 0 and "no tool" in unpinned[0]  # vacuity guard: the pin removed the case


def test_a_drill_prints_the_whole_window_checks_with_their_mass(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--where",
                          "%s=%s" % (CAUSE, schema.TOOL_RESULT))
    assert code == 0, err
    assert fx.headline(out).startswith("%s%s over 3 changes where %s=%s in 3 windows" % (
        fx.total_line(CONTEXT.metric), format(3 * fx.EXACT_FIRST_DELTA, ",d"), CAUSE, schema.TOOL_RESULT))
    last = out.splitlines()[-1]
    assert last.startswith("%s checks over the 3 whole windows (a drill is not reconciled): %s booked"
                           % (tables.OK_MARK, format(3 * fx.FINAL_OCCUPANCY, ",d")))
    assert " %d gaps between calls (" % (3 * fx.INTERVALS) in last
    assert tables.TOTAL_LABEL not in out  # no total row on a drill
    whole = fx.run_cli("context", "--root", str(root))[1]
    assert tables.TOTAL_LABEL in whole  # vacuity guard


def test_by_fact_prints_the_checks_with_their_mass(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--by", "fact", "--limit", "1")
    assert code == 0, err
    last = out.splitlines()[-1]
    assert last.startswith("%s checks: %s booked" % (tables.OK_MARK, format(3 * fx.FINAL_OCCUPANCY, ",d")))
    assert " %d gaps between calls (" % (3 * fx.INTERVALS) in last


def test_a_drill_headline_counts_the_windows_its_facts_come_from(tmp_path):
    """Two windows, the second cut after its first interval: a drill on a
    cause only the first carries says so; one both carry names them plain."""
    root = fx.corpus(tmp_path, {
        "proj-a/sess-0001.jsonl": fx.window_records(),
        "proj-b/sess-0002.jsonl": fx.window_records("b-", session="sess-0002")[:3]})
    facts = fx.load_facts(root)[1]
    assert {f.dims.get(CAUSE) for f in facts if f.locator.file.startswith("proj-b/")} == {
        None, schema.STARTING_CONTEXT, schema.REPLIES, schema.TOOL_RESULT}  # None: its calls
    code, out, err = fx.run_cli("context", "--root", str(root),
                                "--where", "%s=%s" % (CAUSE, schema.USER_TEXT))
    assert code == 0, err
    assert fx.headline(out).endswith(" over 1 change where %s=%s in 1 of 2 windows"
                                        % (CAUSE, schema.USER_TEXT))  # no lever: no lead
    assert "checks over the 2 whole windows (a drill is not reconciled)" in out
    code, out, err = fx.run_cli("context", "--root", str(root),
                                "--where", "%s=%s" % (CAUSE, schema.TOOL_RESULT))
    assert code == 0, err
    assert fx.headline(out).endswith(" over 2 changes where %s=%s in 2 windows"
                                        % (CAUSE, schema.TOOL_RESULT))
    assert query.values(query.select(facts, [(CAUSE, schema.TOOL_RESULT)]), TOOL, CONTEXT.metric
                        ) == ["Bash"]  # the one tool every drilled fact shares leads nothing


def test_a_drill_reports_the_peak_over_the_whole_windows_it_names(tmp_path):
    root = fx.cli_corpus(tmp_path)
    facts = fx.load_facts(root)[1]
    drill = [(CAUSE, schema.TOOL_RESULT)]
    assert not [f for f in query.select(facts, drill) if fx.PEAK in f.metrics]  # a drill keeps no call
    code, out, err = fx.run_cli("context", "--root", str(root), "--where", "%s=%s" % drill[0])
    assert code == 0, err
    headline, (peak,) = fx.headline(out), fx.peaks(out)
    assert " over 3 changes where %s=%s in 3 windows" % drill[0] in headline
    top = query.largest(facts, fx.PEAK)
    assert top.locator.file == "proj-a/sess-0001.jsonl"  # vacuity guard: one of the windows named
    assert peak == "%s%s %s (of 3 windows), %s=%s" % (
        fx.PEAK_LINE, format(fx.FINAL_OCCUPANCY, ",d"), fx.unit(fx.PEAK), schema.WINDOW_DIM,
        schema.window_value(top.window))


def test_a_main_window_is_selected_by_its_window_value_alone(tmp_path):
    """D-WINDOW-DIM as amended by D-CONTEXT-WINDOW: a main window carries no
    agent and its session keeps every subagent, so ``window`` (its key's
    hash) is the one filter that isolates it; it keeps a whole window, so
    the view still reconciles."""
    root = fx.cli_corpus(tmp_path)
    facts = fx.load_facts(root)[1]
    name = "proj-a/sess-0001.jsonl"
    main = fx.window_value(name)
    assert [f.locator.file for f in query.select(facts, [(schema.WINDOW_DIM, main)])] == [
        f.locator.file for f in facts if f.locator.file == name]
    assert {f.locator.file for f in query.select(facts, [(schema.SESSION_DIM, fx.SESSION)])} > {name}
    code, out, err = fx.run_cli("context", "--root", str(root),
                                "--where", "%s=%s" % (schema.WINDOW_DIM, main))
    assert code == 0, err
    assert "= the 1 window's final size (" in fx.headline(out)
    assert "\nin view where %s=%s: 1 window°, 11 changes\n" % (schema.WINDOW_DIM, main) in out
    assert re.search(r"^%s\s+%s\s.*%s = final window sizes$" % (
        tables.TOTAL_LABEL, format(fx.FINAL_OCCUPANCY, ",d"), tables.OK_MARK), out, re.M)
    assert out.splitlines()[-1].startswith("%s checks: 6 gaps between calls (7 calls - 1 window): " % tables.OK_MARK)
    for view in cli.VIEWS:
        assert schema.WINDOW_DIM not in cli.VIEWS[view].tables
        code, out, err = fx.run_cli(view, "--root", str(root), "--by", schema.WINDOW_DIM)
        assert code == 0, err
        rows = [l.split()[0] for l in out.splitlines() if l.endswith("%")]  # the regular rows
        assert sorted(rows) == sorted({f.dims[schema.WINDOW_DIM] for f in facts})  # one row per window
        assert main in rows


def test_an_asked_for_table_prints_its_labels_whole_so_they_copy_into_where(tmp_path):
    """A default table cuts a long label to its tail; ``--by`` names its
    table on purpose, so the labels print whole and one pasted into
    ``--where`` selects."""
    project = "-home-me-workspace-" + "x" * 40
    assert len(project) > tables.LABEL_WIDTH  # vacuity guard
    root = fx.corpus(tmp_path, {project + "/sess-0001.jsonl": fx.window_records(),  # two sessions:
                                project + "/sess-0002.jsonl":  # the project table is no relabel
                                fx.window_records("b-", session="sess-0002")})
    cut = "…" + project[1 - tables.LABEL_WIDTH:]
    for by, label in (([], cut), (["--by", schema.PROJECT_DIM], project)):
        code, out, err = fx.run_cli("context", "--root", str(root), *by)
        assert code == 0, err
        rows = [l.split()[0] for l in out.splitlines() if l.endswith("%")]
        assert label in rows and ({cut, project} - {label}).isdisjoint(rows), by
    code, out, err = fx.run_cli("context", "--root", str(root),
                                "--where", "%s=%s" % (schema.PROJECT_DIM, project))
    assert code == 0, err
    assert "\nin view where %s=%s: 2 windows°, " % (schema.PROJECT_DIM, project) in out


def test_each_pin_is_named_beside_the_one_count_it_narrows(tmp_path):
    """A window pin on the kept line, a drill pin on the headline; the read
    line is corpus-wide and names neither, so the population lines are the
    same with the drill and without."""
    root = fx.cli_corpus(tmp_path)
    window, drill = "%s=proj-a" % schema.PROJECT_DIM, "%s=%s" % (CAUSE, schema.TOOL_RESULT)
    code, out, err = fx.run_cli("context", "--root", str(root), "--where", window, "--where", drill)
    assert code == 0, err
    code, unpinned, err = fx.run_cli("context", "--root", str(root), "--where", window)
    assert code == 0, err
    population = [l for l in out.splitlines() if l.startswith(("read: ", "in view"))]
    assert population == [l for l in unpinned.splitlines() if l.startswith(("read: ", "in view"))] == [
        "read: 4 files modified in the last 7d (default) under %s, 0 lines skipped,"
        " 0 duplicates excluded" % root,
        "in view where %s: 2 windows°, 22 changes" % window]
    assert drill not in "".join(population)
    assert fx.headline(out).startswith("%s%s over 2 changes where %s in 2 windows" % (
        fx.total_line(CONTEXT.metric), format(2 * fx.EXACT_FIRST_DELTA, ",d"), drill))
    assert window not in fx.headline(out)  # a window pin narrows no headline count


def test_by_fact_lists_leaves_with_their_dimensions_and_evidence(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--by", "fact",
                          "--where", "%s=%s" % (CAUSE, schema.TOOL_RESULT), "--limit", "2")
    assert code == 0, err
    assert re.search(r"^\s+%s  file:line  uuid  dimensions$" % fx.printed(CONTEXT.metric), out, re.M)
    leaves = [l for l in out.splitlines() if re.match(r"\s+[\d,]+\s+\S+:\d+\s", l)]
    assert len(leaves) == 2 and all("%s=%s" % (CAUSE, schema.TOOL_RESULT) in l for l in leaves)
    assert re.search(r"\sproj-a/sess-0001\.jsonl:2\s+uuid-0002\s", out)

    code, out, err = fx.run_cli("context", "--root", str(root), "--by", "fact", "--where",
                          "%s=%s" % (schema.REASON_DIM, schema.SEVERAL),
                          "--where", "project=proj-a", "--limit", "1")
    assert code == 0, err
    assert re.search(r"^\s+%s:\n"
                     r"\s+proj-a/sess-0001\.jsonl:4 uuid-0004  %s=%s\n"
                     r"\s+proj-a/sess-0001\.jsonl:5 uuid-0005  %s=%s %s=Read %s=Read:py$"
                     % (schema.CANDIDATES, CAUSE, schema.USER_TEXT, CAUSE, schema.TOOL_RESULT,
                        TOOL, HEAD), out, re.M)
    assert out.count("%s:" % schema.CANDIDATES) == 1
    (leaf,) = [l for l in out.splitlines() if re.match(r"\s+[\d,]+\s+\S+:\d+\s", l)]
    assert "%s=" % TOOL not in leaf  # the candidates share no tool

    code, out, err = fx.run_cli("context", "--root", str(root), "--by", "fact", "--where",
                          "%s=%s" % (CAUSE, schema.STARTING_CONTEXT), "--where", "%s=agent-fake1" % schema.SUBAGENT_DIM)
    assert code == 0, err
    assert re.search(r"^\s+%s: %s$" % (schema.PARENT_SESSION, fx.FORK_PARENT), out, re.M)

    code, out, err = fx.run_cli("spend", "--root", str(root), "--by", "fact", "--limit", "1",
                          "--where", "%s=agent-fake1" % schema.SUBAGENT_DIM)
    assert code == 0, err
    (leaf,) = [l for l in out.splitlines() if re.match(r"\s+[\d,]+\s+\S+:\d+\s", l)]
    name = "proj-a/sess-0001/subagents/agent-fake1.jsonl"
    assert leaf.split()[1].startswith(name + ":")  # the locator names the file; a file can hold
    assert all("%s=" % dim in leaf for dim in schema.WINDOW_DIMENSIONS)  # several windows, so tagged
    window = "%s=%s" % (schema.WINDOW_DIM, fx.window_value(name))
    assert window in leaf
    assert query.select(fx.load_facts(root)[1], [tuple(window.split("="))])  # vacuity guard
