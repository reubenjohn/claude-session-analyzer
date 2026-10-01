"""``python3 -m sa`` narrowed by ``--where`` and ``--by fact`` against
``fixtures.cli_corpus``: what a drill prints, what a window filter keeps.
What each view prints unnarrowed is ``test_cli``."""
import re

import fixtures as fx
from sa import cli, query, schema, tables

CONTEXT = cli.VIEWS["context"]
CAUSE, TOOL, HEAD = schema.CAUSE_DIM, schema.TOOL_DIM, schema.HEAD_DIM


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
    assert out.startswith("%s: -300 %s over 3 increment facts where %s=%s in 3 windows\n" % (
        CONTEXT.metric, fx.unit(CONTEXT.metric), CAUSE, schema.SHRINK))


def test_a_drill_prints_a_table_that_has_only_a_residual_row(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--where",
                          "%s=%s" % (CAUSE, schema.WINDOW_HEAD), "--by", TOOL)
    assert code == 0, err
    assert re.search(r"^by %s\s" % TOOL, out, re.M)
    assert re.search(r"^%s\s+%s\s+3\s+-$" % (re.escape(tables.RESIDUAL_LABEL), format(3000, ",d")),
                     out, re.M)
    assert "; top" not in out.splitlines()[0]
    assert re.search(r"^by %s\s.*\s+%s\s+share$" % (TOOL, fx.count_column(CONTEXT.metric)), out, re.M)
    assert "share of" not in out


def test_a_drill_prints_the_whole_window_reconciliation_once_as_a_pointer(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--where",
                          "%s=%s" % (CAUSE, schema.TOOL_RESULT))
    assert code == 0, err
    assert out.startswith("%s: %s %s over 3 increment facts where %s=%s in 3 windows" % (
        CONTEXT.metric, format(3 * fx.EXACT_FIRST_DELTA, ",d"), fx.unit(CONTEXT.metric),
        CAUSE, schema.TOOL_RESULT))
    assert "reconciliation: applies to the 3 whole windows above, not to this drill: OK" in out
    assert "reconciliation over" not in out
    assert "reconciliation over 3 windows" in fx.run_cli("context", "--root", str(root))[1]


def test_a_drill_headline_counts_the_windows_its_facts_come_from(tmp_path):
    """Two windows, the second cut after its first interval: a drill on a
    cause only the first carries says so; one both carry names them plain."""
    root = fx.corpus(tmp_path, {
        "proj-a/sess-0001.jsonl": fx.window_records(),
        "proj-b/sess-0002.jsonl": fx.window_records("b-", session="sess-0002")[:3]})
    facts = fx.load_facts(root)[1]
    assert {f.dims.get(CAUSE) for f in facts if f.locator.file.startswith("proj-b/")} == {
        None, schema.WINDOW_HEAD, schema.FEED_FORWARD, schema.TOOL_RESULT}  # None: its calls
    code, out, err = fx.run_cli("context", "--root", str(root),
                                "--where", "%s=%s" % (CAUSE, schema.USER_TEXT))
    assert code == 0, err
    assert out.splitlines()[0].endswith(" over 1 increment fact where %s=%s in 1 of 2 windows"
                                        % (CAUSE, schema.USER_TEXT))  # no lever: no lead
    assert "reconciliation: applies to the 2 whole windows above" in out
    code, out, err = fx.run_cli("context", "--root", str(root),
                                "--where", "%s=%s" % (CAUSE, schema.TOOL_RESULT))
    assert code == 0, err
    assert out.splitlines()[0].endswith(" over 2 increment facts where %s=%s in 2 windows"
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
    headline, peak = out.splitlines()[:2]
    assert " over 3 increment facts where %s=%s in 3 windows" % drill[0] in headline
    assert peak == "single-call peak %s over the 3 whole windows: %s %s at proj-a/sess-0001.jsonl:14" % (
        fx.PEAK, format(fx.FINAL_OCCUPANCY, ",d"), fx.unit(fx.PEAK))


def test_a_main_window_is_selected_by_its_file_name_alone(tmp_path):
    """D-WINDOW-DIM: a main window carries no agent and its session keeps
    every subagent, so ``window`` is the one filter that isolates it; it
    keeps a whole window, so the view still reconciles."""
    root = fx.cli_corpus(tmp_path)
    facts = fx.load_facts(root)[1]
    main = "proj-a/sess-0001.jsonl"
    assert [f.locator.file for f in query.select(facts, [(schema.WINDOW_DIM, main)])] == [
        f.locator.file for f in facts if f.locator.file == main]
    assert {f.locator.file for f in query.select(facts, [(schema.SESSION_DIM, fx.SESSION)])} > {main}
    code, out, err = fx.run_cli("context", "--root", str(root),
                                "--where", "%s=%s" % (schema.WINDOW_DIM, main))
    assert code == 0, err
    assert "= the 1 window's final occupancy;" in out.splitlines()[0]
    assert "\nkept where %s=%s: 1 window, 7 call facts, 11 increment facts\n" % (schema.WINDOW_DIM, main) in out
    assert "reconciliation over 1 window:" in out
    assert "intervals 6 (= 7 calls - 1 window):" in out
    assert "final occupancy %s: OK" % format(fx.FINAL_OCCUPANCY, ",d") in out
    for view in cli.VIEWS:
        assert schema.WINDOW_DIM not in cli.VIEWS[view].tables
        code, out, err = fx.run_cli(view, "--root", str(root), "--by", schema.WINDOW_DIM)
        assert code == 0, err
        rows = [l.split()[0] for l in out.splitlines() if l.endswith("%")]  # the regular rows
        assert sorted(rows) == sorted({f.locator.file for f in facts})  # one row per window, whole
        assert main in rows and len(max(rows, key=len)) > tables.LABEL_WIDTH  # one a default table cuts


def test_an_asked_for_table_prints_its_labels_whole_so_they_copy_into_where(tmp_path):
    """A default table cuts a long label to its tail; ``--by`` names its
    table on purpose, so the labels print whole and one pasted into
    ``--where`` selects."""
    project = "-home-me-workspace-" + "x" * 40
    assert len(project) > tables.LABEL_WIDTH  # vacuity guard
    root = fx.corpus(tmp_path, {project + "/sess-0001.jsonl": fx.window_records()})
    cut = "…" + project[1 - tables.LABEL_WIDTH:]
    for by, label in (([], cut), (["--by", schema.PROJECT_DIM], project)):
        code, out, err = fx.run_cli("context", "--root", str(root), *by)
        assert code == 0, err
        rows = [l.split()[0] for l in out.splitlines() if l.endswith("%")]
        assert label in rows and ({cut, project} - {label}).isdisjoint(rows), by
    code, out, err = fx.run_cli("context", "--root", str(root),
                                "--where", "%s=%s" % (schema.PROJECT_DIM, project))
    assert code == 0, err
    assert "\nkept where %s=%s: 1 window, " % (schema.PROJECT_DIM, project) in out


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
    population = [l for l in out.splitlines() if l.startswith(("read: ", "kept"))]
    assert population == [l for l in unpinned.splitlines() if l.startswith(("read: ", "kept"))] == [
        "read: root %s, 4 files, 0 lines skipped, 0 duplicate records excluded" % root,
        "kept where %s: 2 windows, 14 call facts, 22 increment facts" % window]
    assert drill not in "".join(population)
    assert out.startswith("%s: %s %s over 2 increment facts where %s in 2 windows" % (
        CONTEXT.metric, format(2 * fx.EXACT_FIRST_DELTA, ",d"), fx.unit(CONTEXT.metric), drill))
    assert window not in out.splitlines()[0]  # a window pin narrows no headline count


def test_by_fact_lists_leaves_with_their_dimensions_and_evidence(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--by", "fact",
                          "--where", "%s=%s" % (CAUSE, schema.TOOL_RESULT), "--limit", "2")
    assert code == 0, err
    assert re.search(r"^\s+%s  file:line  uuid  dimensions$" % CONTEXT.metric, out, re.M)
    assert fx.unit(CONTEXT.metric) != CONTEXT.metric  # vacuity guard: the header names the metric
    leaves = [l for l in out.splitlines() if re.match(r"\s+[\d,]+\s+\S+:\d+\s", l)]
    assert len(leaves) == 2 and all("%s=%s" % (CAUSE, schema.TOOL_RESULT) in l for l in leaves)
    assert re.search(r"\sproj-a/sess-0001\.jsonl:2\s+uuid-0002\s", out)

    code, out, err = fx.run_cli("context", "--root", str(root), "--by", "fact", "--where",
                          "%s=%s" % (schema.REASON_DIM, schema.MULTI_CONTRIBUTOR),
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
                          "%s=%s" % (CAUSE, schema.WINDOW_HEAD), "--where", "agent=agent-fake1")
    assert code == 0, err
    assert re.search(r"^\s+%s: %s$" % (schema.PARENT_SESSION, fx.FORK_PARENT), out, re.M)

    code, out, err = fx.run_cli("spend", "--root", str(root), "--by", "fact", "--limit", "1",
                          "--where", "%s=agent-fake1" % schema.AGENT_DIM)
    assert code == 0, err
    (leaf,) = [l for l in out.splitlines() if re.match(r"\s+[\d,]+\s+\S+:\d+\s", l)]
    window = "proj-a/sess-0001/subagents/agent-fake1.jsonl"
    assert leaf.split()[1].startswith(window + ":")  # the locator names the window...
    assert "%s=" % schema.WINDOW_DIM not in leaf       # ...so the tags do not repeat it
    assert all("%s=" % dim in leaf for dim in schema.WINDOW_DIMENSIONS if dim != schema.WINDOW_DIM)
    assert query.select(fx.load_facts(root)[1], [(schema.WINDOW_DIM, window)])  # vacuity guard
