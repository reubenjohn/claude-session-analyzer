"""``python3 -m sa`` narrowed by pins and ``by change`` against
``fixtures.cli_corpus``: what a drill prints, what a window filter keeps.
What each view prints unnarrowed is ``test_cli``."""
import re

import fixtures as fx
from sa import checks, cli, glossary, grammar, leaves as leaves_module, query, residual, schema, tables
from sa.leaves import HEAVIEST

CONTEXT = cli.VIEWS["context"]
CAUSE, TOOL, HEAD = schema.CAUSE_DIM, schema.TOOL_DIM, schema.COMMAND_DIM


def test_shrink_is_selectable_and_its_leaves_are_listed(tmp_path):
    """Every table files shrink as a signed row, which is no reason for a
    pin to deny the facts exist."""
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "%s=%s" % (CAUSE, schema.SHRINK), "by", "change")
    assert code == 0, err
    leaves = [l for l in out.splitlines() if fx.LEAF.match(l)]
    assert len(leaves) == 3 and all(l.split()[1] == "-100" for l in leaves)  # its raw tokens, beside its part
    assert all(l.split()[0].startswith("-") for l in leaves)
    head = next(l for l in out.splitlines() if l.lstrip().startswith(fx.printed(CONTEXT.metric)))
    assert CAUSE not in head  # a pin prints no column
    assert CAUSE in fx.run_cli("context", "--root", str(root), "by", "change")[1]  # vacuity guard
    assert re.match(r"^%s\*?: -57 of the 84,709-token average call, over 21 calls in 3 windows; from 3 changes"
                    r" in 3 windows$" % schema.SHRINK, fx.headline(out))


def test_a_drill_prints_a_table_that_has_only_a_residual_row(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "%s=%s" % (CAUSE, schema.STARTING_CONTEXT), "by", TOOL)
    assert code == 0, err
    assert re.search(r"^%s\s+84,333\s+3\s+-  = %s 84,333$" % (re.escape(residual.label(TOOL)), schema.STARTING_CONTEXT),
                     out, re.M)  # all it holds: one part, named
    assert "; largest" not in fx.headline(out)
    assert re.search(r"^by %s\s+%s\s+%s$" % (TOOL, fx.printed(CONTEXT.metric), fx.count_column(CONTEXT.metric)),
                     out, re.M)  # no row has a share, so no share column
    assert tables.BASE_LABEL not in out


def test_a_drill_prints_the_whole_window_checks_with_their_mass(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "%s=%s" % (CAUSE, schema.TOOL_RESULT))
    assert code == 0, err
    assert fx.headline(out) == ("%s: 214 of the 84,709-token average call, over 21 calls in 3 windows; from 3"
                                " changes in 3 windows" % schema.TOOL_RESULT)
    assert fx.checks(out).startswith("%s over 3 windows in view: " % checks.OK)  # whole windows, as by default
    worked = fx.worked(fx.run_cli("context", "--root", str(root), "%s=%s" % (CAUSE, schema.TOOL_RESULT), "-v")[1])
    assert re.search(r"\n  tokens added 254,860 - tokens shrunk 300 += 254,560  ✓ same as the final window sizes\n",
                     worked), worked
    assert "\n  %d calls after their window's first = " % (3 * fx.INTERVALS) in worked
    assert tables.TOTAL_LABEL not in out  # no total row on a drill
    whole = fx.run_cli("context", "--root", str(root))[1]
    assert tables.TOTAL_LABEL in whole  # vacuity guard


def test_by_change_prints_the_checks_with_their_mass(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "by", "change")
    assert code == 0, err
    assert fx.checks(out).startswith("%s over 3 windows in view: " % checks.OK)
    worked = fx.worked(fx.run_cli("context", "--root", str(root), "by", "change", "-v")[1])
    assert re.search(r"\n  tokens added 254,860 - tokens shrunk 300 += 254,560  ✓ ", worked), worked
    assert "\n  %d calls after their window's first = " % (3 * fx.INTERVALS) in worked


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
                                "%s=%s" % (CAUSE, schema.USER_TEXT))
    assert code == 0, err
    assert fx.headline(out).endswith(", over 9 calls in 2 windows; from 1 change in 1 of those windows")
    assert "%s over 2 windows in view: " % checks.OK in out
    code, out, err = fx.run_cli("context", "--root", str(root),
                                "%s=%s" % (CAUSE, schema.TOOL_RESULT))
    assert code == 0, err
    assert fx.headline(out).endswith("; from 2 changes in 2 windows")
    assert query.values(query.select(facts, [(CAUSE, schema.TOOL_RESULT)]), TOOL, CONTEXT.metric
                        ) == ["Bash"]  # the one tool every drilled fact shares leads nothing


def test_a_drill_reports_the_average_over_the_whole_windows_it_names(tmp_path):
    root = fx.cli_corpus(tmp_path)
    facts = fx.load_facts(root)[1]
    drill = [(CAUSE, schema.TOOL_RESULT)]
    assert not [f for f in query.select(facts, drill) if fx.PEAK in f.metrics]  # a drill keeps no call
    code, out, err = fx.run_cli("context", "--root", str(root), "%s=%s" % drill[0])
    assert code == 0, err
    assert not fx.average(out)  # the drilled part names the average it is part of
    mean, calls = query.mean(facts, fx.PEAK)
    assert calls == 21 and mean > fx.FINAL_OCCUPANCY  # vacuity guard: every call of the 3 windows
    # D-PER-CALL: the drilled changes, each times the calls that held it, over every call in view
    held = sum(f.metrics[fx.HELD] for f in query.select(facts, drill))
    assert 0 < held / calls < mean
    assert fx.headline(out) == "%s: %s of the %s-token average call, over %d calls in 3 windows; from 3 changes" \
        " in 3 windows" % (drill[0][1], tables.num(held / calls), tables.num(mean), calls)


def test_a_main_window_is_selected_by_its_window_value_alone(tmp_path):
    """D-CONTEXT-WINDOW: a main window carries no
    subagent and its session keeps every subagent, so ``window`` (its key's
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
                                "%s=%s" % (schema.WINDOW_DIM, main))
    assert code == 0, err
    mean = tables.num(query.mean(query.select(facts, [(schema.WINDOW_DIM, main)]), fx.PEAK)[0])
    assert fx.headline(out).startswith("%s%s %s, over 7 calls in 1 window where %s=%s; " % (
        fx.total_line(CONTEXT.metric), mean, fx.unit(CONTEXT.metric), schema.WINDOW_DIM, main))
    assert "\nin view where %s=%s: 1 window*, 11 changes*\n" % (schema.WINDOW_DIM, main) in out
    assert re.search(r"^%s\s+%s\s.*%s = mean call size$" % (tables.TOTAL_LABEL, mean, tables.OK_MARK), out, re.M)
    worked = fx.worked(fx.run_cli("context", "--root", str(root), "%s=%s" % (schema.WINDOW_DIM, main), "-v")[1])
    assert re.search(r"\n  tokens added 1,620 - tokens shrunk 100 += %s  ✓ [^\n]+\n  6 calls after their" % (
        format(fx.FINAL_OCCUPANCY, ",d")), worked), worked
    for view in cli.VIEWS:
        assert schema.WINDOW_DIM not in cli.VIEWS[view].tables
        code, out, err = fx.run_cli(view, "--root", str(root), "by", schema.WINDOW_DIM)
        assert code == 0, err
        rows = [l.split()[0] for l in out.splitlines() if l.endswith("%")]  # the regular rows
        assert sorted(rows) == sorted({f.dims[schema.WINDOW_DIM] for f in facts})  # one row per window
        assert main in rows


def test_a_long_label_prints_whole_so_it_pins_as_printed(tmp_path):
    """No label is cut, in a default table or in ``by DIM``: one pasted
    into a pin selects."""
    project = "-nowhere-me-workspace-" + "x" * 40
    root = fx.corpus(tmp_path, {project + "/sess-0001.jsonl": fx.window_records(),  # three sessions,
                                project + "/sess-0002.jsonl":  # two projects: the project table
                                fx.window_records("b-", session="sess-0002"),  # is no relabel
                                "proj-b/sess-0003.jsonl": fx.window_records("c-", session="sess-0003")})
    for by in (["by", schema.PROJECT_DIM],):
        code, out, err = fx.run_cli("context", "--root", str(root), *by)
        assert code == 0, err
        assert re.search(r"^%s\s" % re.escape(project), out, re.M), by
    code, out, err = fx.run_cli("context", "--root", str(root),
                                "%s=%s" % (schema.PROJECT_DIM, project))
    assert code == 0, err
    assert "\nin view where %s=%s: 2 windows*, " % (schema.PROJECT_DIM, project) in out


def test_each_pin_is_named_beside_the_one_count_it_narrows(tmp_path):
    """A window pin on the kept line, a drill pin on the headline; the read
    line is corpus-wide and names neither, so the population lines are the
    same with the drill and without."""
    root = fx.cli_corpus(tmp_path)
    window, drill = "%s=proj-a" % schema.PROJECT_DIM, "%s=%s" % (CAUSE, schema.TOOL_RESULT)
    code, out, err = fx.run_cli("context", "--root", str(root), window, drill)
    assert code == 0, err
    code, unpinned, err = fx.run_cli("context", "--root", str(root), window)
    assert code == 0, err
    population = [l for l in fx.joined(out).splitlines() if l.startswith(("read: ", "in view"))]
    assert population == [l for l in fx.joined(unpinned).splitlines() if l.startswith(("read: ", "in view"))] == [
        "read: 4 files from the last 7d (default) under %s; 1 with no call" % root,
        "in view where %s: 2 windows*, 22 changes*" % window]
    assert drill not in "".join(population) and schema.TOOL_RESULT not in "".join(population)
    assert fx.headline(out).startswith("%s: 214 of the " % schema.TOOL_RESULT)
    assert fx.headline(out).endswith(", over 14 calls in 2 windows; from 2 changes in 2 windows")
    assert window not in fx.headline(out)  # a window pin narrows no headline count
    assert window in fx.headline(unpinned)  # vacuity guard: the average names it


def test_by_change_lists_leaves_with_their_dimensions_and_evidence(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "by", "change",
                                "%s=%s" % (CAUSE, schema.TOOL_RESULT))
    assert code == 0, err
    assert re.search(r"^\s+%s\s+tokens\s+%s\s+line\s+%s$" % (fx.printed(CONTEXT.metric), leaves_module.HELD,
                                                         leaves_module.DIMENSIONS),
                     out, re.M)  # its part of the average, its raw tokens, the calls that held it, its pins
    leaves = [l for l in out.splitlines() if fx.LEAF.match(l)]
    assert len(leaves) == 3
    assert re.search(r"^proj-a/sess-0001\.jsonl  %s=\S+.*\n\s+[\d,]+\s+250\s+\d+\s+:2  .*%s=" % (schema.WINDOW_DIM, TOOL), out, re.M)

    window = "%s=%s" % (schema.WINDOW_DIM, fx.window_value("proj-a/sess-0001.jsonl"))
    code, out, err = fx.run_cli("context", "--root", str(root), "by", "change",
                                "%s=%s" % (schema.REASON_DIM, schema.SEVERAL), window)
    assert code == 0, err
    assert re.search(r"^\s+%s: %s\n"
                     r"\s+└ :4  [\d,]+ characters  %s=%s\n"
                     r"\s+└ :5  2 characters  %s=%s %s=Read %s=Read:py$"
                     % (schema.CANDIDATES, HEAVIEST, CAUSE, schema.USER_TEXT, CAUSE, schema.TOOL_RESULT,
                        TOOL, HEAD), out, re.M)
    assert out.count("%s:" % schema.CANDIDATES) == 1
    (leaf,) = [l for l in out.splitlines() if fx.LEAF.match(l)]
    assert "%s=" % TOOL not in leaf  # the candidates share no tool

    code, out, err = fx.run_cli("context", "--root", str(root), "by", "change",
                                "%s=%s" % (CAUSE, schema.STARTING_CONTEXT), "%s=agent-fake1" % schema.SUBAGENT_DIM)
    assert code == 0, err
    assert re.search(r"^\s+%s: %s$" % (schema.PARENT_SESSION, fx.FORK_PARENT), out, re.M)

    code, out, err = fx.run_cli("spend", "--root", str(root), "by", grammar.FACTS["spend"],
                                "%s=agent-fake1" % schema.SUBAGENT_DIM)
    assert code == 0, err
    leaves = [l for l in out.splitlines() if fx.LEAF.match(l)]
    assert len(leaves) == 7  # every call, no cap
    name = "proj-a/sess-0001/subagents/agent-fake1.jsonl"  # the header names the file; a file can hold
    window = "%s=%s" % (schema.WINDOW_DIM, fx.window_value(name))  # several windows, so it names the window
    assert fx.listed(out) == ["%s/%s" % (root, name)]  # the shared directory, once; each file under it, openable
    assert "%s  %s\n" % (name.rsplit("/", 1)[1], window) in out or "\n  %s\n" % window in out
    assert query.select(fx.load_facts(root)[1], [tuple(window.split("="))])  # vacuity guard
