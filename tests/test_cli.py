"""``python3 -m sa`` end to end against ``fixtures.cli_corpus``: what each
view prints. Metric names, units and dimensions come from ``cli.VIEWS`` and
the schema; what the arguments refuse is ``test_cli_args``."""
import re

import pytest

import fixtures as fx
from sa import cli, query, render, schema, walk
from sa.schema import CALL, INCREMENT

CONTEXT, SPEND = cli.VIEWS["context"], cli.VIEWS["spend"]
CAUSE, TOOL, HEAD = CONTEXT.tables[:3]


def _unit(metric):
    return schema.metric(metric).unit


def _count(metric):
    """The count column's name: what the metric's carrier kind is called."""
    return schema.metric(metric).carrier + "s"


def test_context_reconciles_and_counts_its_population(tmp_path):
    root = fx.cli_corpus(tmp_path)
    loaded, facts = fx.load_facts(root)
    code, out, err = fx.run_cli("context", "--root", str(root))
    assert code == 0, err
    first, peak, population = out.splitlines()[:3]
    # window_head is the largest cause (3,000 of 4,560) but is not splittable
    # and cause is the least specific table: the headline leads with the top
    # head, as a share of the total.
    assert re.search(r"^%s\s+3,000\s" % schema.WINDOW_HEAD, out, re.M)
    assert first == "%s: %s %s = the 3 windows' final occupancies summed; top %s=Bash:pytest 750 (16.4%% of the 4,560 total)" % (
        CONTEXT.metric, format(3 * fx.FINAL_OCCUPANCY, ",d"), _unit(CONTEXT.metric), HEAD)
    assert peak == "single-call peak %s over the 3 whole windows: %s %s at proj-a/sess-0001.jsonl:14" % (
        fx.PEAK, format(fx.FINAL_OCCUPANCY, ",d"), _unit(fx.PEAK))
    assert population == (
        "population: root %s; %d files read, 3 windows, %d call facts, %d increment facts; "
        "0 lines skipped, 0 duplicate records excluded"
        % (root, len(loaded.files), sum(f.kind == CALL for f in facts),
           sum(f.kind == INCREMENT for f in facts)))
    assert out.count(str(root)) == 1  # locators are root-relative
    assert "final occupancy %s: OK" % format(3 * fx.FINAL_OCCUPANCY, ",d") in out
    reasons = ", ".join("%s 3" % r for r in schema.REASONS)
    assert "intervals 18 (= 21 calls - 3 windows): exact 6 (33.3%) + ambiguous 9 (50.0%) " \
           "[" + reasons + "] + shrink 3 (16.7%): OK" in out
    assert "\nexact: " in out and "[OPEN]" not in out
    for dim in CONTEXT.tables:
        assert "by " + dim in out
    (drillable,) = set(schema.KIND_DIMENSIONS[INCREMENT]) - set(CONTEXT.tables)
    assert "by " + drillable not in out
    assert "by " + drillable in fx.run_cli("context", "--root", str(root), "--by", drillable)[1]
    assert "%s: %s" % (schema.WINDOW_HEAD, render.UNSPLITTABLE[schema.WINDOW_HEAD]) in out
    assert re.search(r"^%s\s" % schema.AMBIGUOUS, out, re.M)
    assert re.search(r"^%s \(signed\)\s+-300\s" % schema.SHRINK, out, re.M)
    assert re.search(r"^by %s\s+%s\s+%s\s+share of [\d,]+$"
                     % (CAUSE, CONTEXT.metric, _count(CONTEXT.metric)), out, re.M)


def test_spend_prints_totals_over_the_selection_and_the_largest_call(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("spend", "--root", str(root), "--where", "project=proj-a")
    assert code == 0, err
    first, peak, note = out.splitlines()[:3]
    assert first.startswith("%s: " % SPEND.metric) and _unit(SPEND.metric) in first
    # project is pinned; agent is the most specific table left, and the fork
    # bills exactly what its parent does, so it is half the total.
    assert re.search(r"over 14 call facts in 2 windows; top %s=agent-fake1 [\d,]+ \(50\.0%% of the [\d,]+ total\)$"
                     % schema.AGENT_DIM, first)
    assert peak.startswith("single-call peak ") and note == cli.SPEND_NOTE
    assert "duplicate records excluded; where project=proj-a" in out
    assert re.search(r"^by %s\s+%s\s+%s\s+share of [\d,]+$"
                     % (SPEND.tables[0], SPEND.metric, _count(SPEND.metric)), out, re.M)
    assert _count(SPEND.metric) != _count(CONTEXT.metric)  # the two views name their own carrier
    assert re.search(r"^single-call peak %s over the 2 whole windows: %s %s at proj-a/sess-0001\.jsonl:14$"
                     % (fx.PEAK, format(fx.FINAL_OCCUPANCY, ",d"), _unit(fx.PEAK)), out, re.M)
    for dim in SPEND.tables:
        assert "by " + dim in out
    assert "by %s" % CAUSE not in out
    assert "by %s" % CAUSE in fx.run_cli("context", "--root", str(root))[1]  # vacuity guard


def _top_of(out):
    return re.search(r"; top (\w+)=", out.splitlines()[0]).group(1)


def test_headline_leads_with_the_most_specific_unpinned_table(tmp_path):
    """The default tables print cause first, but the headline names the top
    head (tool_result is the top cause, Bash:pytest the top head: a category
    is not an answer); pinning a dimension hands the lead to the next most
    specific; ``--by`` overrides."""
    root = fx.cli_corpus(tmp_path)
    assert CONTEXT.tables[0] == CAUSE and HEAD != CAUSE
    assert schema.DIMENSIONS.index(HEAD) > schema.DIMENSIONS.index(CAUSE)
    code, out, err = fx.run_cli("context", "--root", str(root))
    assert code == 0, err
    assert _top_of(out) == HEAD and out.index("by " + CAUSE) < out.index("by " + HEAD)
    assert re.search(r"^%s\s+750\s" % schema.TOOL_RESULT, out, re.M)  # the top cause, not led with
    where = ["--where", "%s=Bash:pytest" % HEAD]
    assert _top_of(fx.run_cli("context", "--root", str(root), *where)[1]) == TOOL
    where += ["--where", "%s=Bash" % TOOL]
    assert _top_of(fx.run_cli("context", "--root", str(root), *where)[1]) == CAUSE
    assert _top_of(fx.run_cli("context", "--root", str(root), "--by", CAUSE)[1]) == CAUSE
    assert _top_of(fx.run_cli("spend", "--root", str(root))[1]) == schema.AGENT_DIM
    assert SPEND.tables[0] != schema.AGENT_DIM  # vacuity guard: not the first table printed


def test_headline_share_is_of_the_total_while_the_table_share_is_of_its_base(tmp_path):
    """Bash carries 750 of 4,560 tokens: the table's share column is over the
    750 that have a tool at all; the headline says 750 of the 4,560 total."""
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--by", TOOL)
    assert code == 0, err
    assert re.search(r"^%s\s+4,110\s+\d+\s+-$" % re.escape(render.RESIDUAL_LABEL), out, re.M)
    assert re.search(r"^%s \(signed\)\s+-300\s" % schema.SHRINK, out, re.M)
    assert "; top %s=Bash 750 (16.4%% of the 4,560 total)" % TOOL in out.splitlines()[0]
    assert re.search(r"^by %s\s.*\s+%s\s+share of 750$" % (TOOL, _count(CONTEXT.metric)), out, re.M)
    assert re.search(r"^Bash\s+750\s+3\s+100\.0%$", out, re.M)


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
    assert "where %s=%s" % (CAUSE, schema.SHRINK) in out


def test_main_windows_carry_no_agent_and_land_in_the_residual_row(tmp_path):
    """D-AGENT-DIM: nine sessions' main windows are not one agent."""
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("spend", "--root", str(root), "--by", schema.AGENT_DIM)
    assert code == 0, err
    assert re.search(r"; top %s=agent-fake1 [\d,]+ \(33\.3%% of the [\d,]+ total\)$"
                     % schema.AGENT_DIM, out.splitlines()[0])  # one of three like windows
    assert re.search(r"^%s\s+[\d,]+\s+14\s+-$" % re.escape(render.RESIDUAL_LABEL), out, re.M)
    assert render.RESIDUAL_NOTES[schema.AGENT_DIM] in out
    assert "%s=main" % schema.AGENT_DIM not in out
    facts = fx.load_facts(root)[1]
    by_file = {f.locator.file: f.dims.get(schema.AGENT_DIM) for f in facts}
    assert by_file == {"proj-a/sess-0001.jsonl": None, "proj-b/sess-0002.jsonl": None,
                       "proj-a/sess-0001/subagents/agent-fake1.jsonl": "agent-fake1"}


def test_a_drill_prints_a_table_that_has_only_a_residual_row(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--where",
                          "%s=%s" % (CAUSE, schema.WINDOW_HEAD), "--by", TOOL)
    assert code == 0, err
    assert re.search(r"^by %s\s" % TOOL, out, re.M)
    assert re.search(r"^%s\s+%s\s+3\s+-$" % (re.escape(render.RESIDUAL_LABEL), format(3000, ",d")),
                     out, re.M)
    assert "; top" not in out.splitlines()[0]
    assert re.search(r"^by %s\s.*\s+%s\s+share$" % (TOOL, _count(CONTEXT.metric)), out, re.M)
    assert "share of" not in out


def test_a_drill_prints_the_whole_window_reconciliation_once_as_a_pointer(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--where",
                          "%s=%s" % (CAUSE, schema.TOOL_RESULT))
    assert code == 0, err
    assert out.startswith("%s: %s %s over 3 increment facts in 3 windows" % (
        CONTEXT.metric, format(3 * fx.EXACT_FIRST_DELTA, ",d"), _unit(CONTEXT.metric)))
    assert "reconciliation: applies to the 3 whole windows above, not to this drill: OK" in out
    assert "reconciliation over" not in out
    assert "reconciliation over 3 windows" in fx.run_cli("context", "--root", str(root))[1]


@pytest.mark.parametrize("drill", [[], ["--where", "%s=%s" % (CAUSE, schema.TOOL_RESULT)]])
def test_a_reconciliation_mismatch_is_exit_status_1(tmp_path, monkeypatch, capsys, drill):
    root = fx.cli_corpus(tmp_path)
    whole = walk.walk
    monkeypatch.setattr(walk, "walk", lambda source: [
        f for f in whole(source) if f.dims.get(CAUSE) != schema.SHRINK])
    assert cli.main(["context", "--root", str(root)] + drill) == 1
    out = capsys.readouterr().out
    assert "MISMATCH" in out and "OK" not in out
    monkeypatch.undo()
    assert cli.main(["context", "--root", str(root)] + drill) == 0  # vacuity guard


def test_by_fact_lists_leaves_with_their_dimensions_and_evidence(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--by", "fact",
                          "--where", "%s=%s" % (CAUSE, schema.TOOL_RESULT), "--limit", "2")
    assert code == 0, err
    assert re.search(r"^\s+%s  file:line  uuid  dimensions$" % CONTEXT.metric, out, re.M)
    assert _unit(CONTEXT.metric) != CONTEXT.metric  # vacuity guard: the header names the metric
    leaves = [l for l in out.splitlines() if re.match(r"\s+[\d,]+\s+\S+:\d+\s", l)]
    assert len(leaves) == 2 and all("%s=%s" % (CAUSE, schema.TOOL_RESULT) in l for l in leaves)
    assert re.search(r"\sproj-a/sess-0001\.jsonl:2\s+uuid-0002\s", out)

    code, out, err = fx.run_cli("context", "--root", str(root), "--by", "fact", "--where",
                          "%s=%s" % (schema.REASON_DIM, schema.MULTI_CONTRIBUTOR),
                          "--where", "project=proj-a", "--limit", "1")
    assert code == 0, err
    assert re.search(r"^\s+candidates:\n"
                     r"\s+proj-a/sess-0001\.jsonl:4 uuid-0004  %s=%s\n"
                     r"\s+proj-a/sess-0001\.jsonl:5 uuid-0005  %s=%s %s=Read %s=Read:py$"
                     % (CAUSE, schema.USER_TEXT, CAUSE, schema.TOOL_RESULT, TOOL, HEAD),
                     out, re.M)
    assert out.count("candidates:") == 1
    (leaf,) = [l for l in out.splitlines() if re.match(r"\s+[\d,]+\s+\S+:\d+\s", l)]
    assert "%s=" % TOOL not in leaf  # the candidates share no tool

    code, out, err = fx.run_cli("context", "--root", str(root), "--by", "fact", "--where",
                          "%s=%s" % (CAUSE, schema.WINDOW_HEAD), "--where", "agent=agent-fake1")
    assert code == 0, err
    assert re.search(r"^\s+parent_session: %s$" % fx.FORK_PARENT, out, re.M)

    code, out, err = fx.run_cli("spend", "--root", str(root), "--by", "fact", "--limit", "1",
                          "--where", "%s=agent-fake1" % schema.AGENT_DIM)
    assert code == 0, err
    (leaf,) = [l for l in out.splitlines() if re.match(r"\s+[\d,]+\s+\S+:\d+\s", l)]
    assert all("%s=" % dim in leaf for dim in schema.WINDOW_DIMENSIONS)


def test_a_drill_reports_the_peak_over_the_whole_windows_it_names(tmp_path):
    root = fx.cli_corpus(tmp_path)
    facts = fx.load_facts(root)[1]
    drill = [(CAUSE, schema.TOOL_RESULT)]
    assert not [f for f in query.select(facts, drill) if fx.PEAK in f.metrics]  # a drill keeps no call
    code, out, err = fx.run_cli("context", "--root", str(root), "--where", "%s=%s" % drill[0])
    assert code == 0, err
    headline, peak = out.splitlines()[:2]
    assert " over 3 increment facts in 3 windows" in headline
    assert peak == "single-call peak %s over the 3 whole windows: %s %s at proj-a/sess-0001.jsonl:14" % (
        fx.PEAK, format(fx.FINAL_OCCUPANCY, ",d"), _unit(fx.PEAK))


def test_headline_total_and_table_base_are_one_sum(tmp_path):
    """Three calls whose spends sum to a .5 in file order and to just under
    it grouped by session (an agent file shares its parent's session, with
    another session's file between them in owner order)."""
    files = {"proj-a/sess-0001.jsonl": (0, 1, fx.SESSION),
             "proj-b/sess-0002.jsonl": (1, 1, "sess-0002"),
             "proj-a/sess-0001/subagents/agent-fake1.jsonl": (2, 13, fx.SESSION)}
    root = fx.corpus(tmp_path, {
        name: fx.stamped([fx.assistant("uuid-%d" % start, "msg-%d" % start,
                                       fx.usage(4 + cache_read, 0), session=session)], start)
        for name, (start, cache_read, session) in files.items()})
    a, b, c = [f.metrics[SPEND.metric] for f in fx.load_facts(root)[1] if f.kind == CALL]
    assert render._num((a + b) + c) != render._num((a + c) + b)  # the two orders really straddle a .5
    code, out, err = fx.run_cli("spend", "--root", str(root), "--by", SPEND.tables[1])
    assert code == 0, err
    headline = re.match(r"%s: ([\d,]+) " % SPEND.metric, out).group(1)
    assert headline == re.search(r"share of ([\d,]+)$", out, re.M).group(1)
