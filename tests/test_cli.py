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
    # window_head is the largest cause (3,000 of 4,560) but is not splittable,
    # so the headline names the next one, over the base the shrink row leaves.
    assert re.search(r"^%s\s+3,000\s" % schema.WINDOW_HEAD, out, re.M)
    assert first == "%s: %s %s = the 3 windows' final occupancies summed; top %s=%s 750 (15.4%% of 4,860 added)" % (
        CONTEXT.metric, format(3 * fx.FINAL_OCCUPANCY, ",d"), _unit(CONTEXT.metric),
        CAUSE, schema.TOOL_RESULT)
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
                     % (CAUSE, _unit(CONTEXT.metric), _count(CONTEXT.metric)), out, re.M)


def test_spend_prints_totals_over_the_selection_and_the_largest_call(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("spend", "--root", str(root), "--where", "project=proj-a")
    assert code == 0, err
    first, peak, note = out.splitlines()[:3]
    assert first.startswith("%s: " % SPEND.metric) and _unit(SPEND.metric) in first
    assert re.search(r"over 14 call facts in 2 windows; top %s=%s [\d,]+ \(100\.0%%\)$"
                     % (SPEND.tables[1], fx.SESSION), first)
    assert peak.startswith("single-call peak ") and note == cli.SPEND_NOTE
    assert "duplicate records excluded; where project=proj-a" in out
    assert re.search(r"^by %s\s+%s\s+%s\s+share of [\d,]+$"
                     % (SPEND.tables[0], _unit(SPEND.metric), _count(SPEND.metric)), out, re.M)
    assert _count(SPEND.metric) != _count(CONTEXT.metric)  # the two views name their own carrier
    assert re.search(r"^single-call peak %s over the 2 whole windows: %s %s at proj-a/sess-0001\.jsonl:14$"
                     % (fx.PEAK, format(fx.FINAL_OCCUPANCY, ",d"), _unit(fx.PEAK)), out, re.M)
    for dim in SPEND.tables:
        assert "by " + dim in out
    assert "by %s" % CAUSE not in out
    assert "by %s" % CAUSE in fx.run_cli("context", "--root", str(root))[1]  # vacuity guard


def test_headline_names_the_top_row_of_the_dimension_shown(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--where", "%s=%s"
                          % (CAUSE, schema.TOOL_RESULT))
    assert code == 0, err
    assert "; top %s=Bash 750 (100.0%%)" % TOOL in out.splitlines()[0]  # the base is the total
    assert "top %s=" % CAUSE not in out
    assert "top %s=" % CAUSE in fx.run_cli("context", "--root", str(root))[1]  # vacuity guard


def test_headline_share_names_its_base_when_a_table_has_a_residual_row(tmp_path):
    """Bash carries 750 of 4,560 tokens, yet its share is of the 750 that
    have a tool at all, so the headline says so and prints the mass."""
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--by", TOOL)
    assert code == 0, err
    assert re.search(r"^%s\s+4,110\s+\d+\s+-$" % re.escape(render.RESIDUAL_LABEL), out, re.M)
    assert re.search(r"^%s \(signed\)\s+-300\s" % schema.SHRINK, out, re.M)
    assert "; top %s=Bash 750 (100.0%% of 750 added with a %s)" % (TOOL, TOOL) in out.splitlines()[0]
    assert re.search(r"^by %s\s.*\s+%s\s+share of 750$" % (TOOL, _count(CONTEXT.metric)), out, re.M)


def test_main_windows_carry_no_agent_and_land_in_the_residual_row(tmp_path):
    """D-AGENT-DIM: nine sessions' main windows are not one agent."""
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("spend", "--root", str(root), "--by", schema.AGENT_DIM)
    assert code == 0, err
    assert re.search(r"; top %s=agent-fake1 ([\d,]+) \(100\.0%% of \1 with an %s\)$"
                     % (schema.AGENT_DIM, schema.AGENT_DIM), out.splitlines()[0])
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
