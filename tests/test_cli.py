"""``python3 -m sa`` end to end against ``fixtures.cli_corpus``: what each
view prints. Metric names, units and dimensions come from ``cli.VIEWS`` and
the schema; what the arguments refuse is ``test_cli_args``, what a drill
prints is ``test_cli_drill``."""
import re

import pytest

import fixtures as fx
from sa import cli, query, render, schema, walk
from sa.schema import CALL, INCREMENT

CONTEXT, SPEND = cli.VIEWS["context"], cli.VIEWS["spend"]
CAUSE, TOOL, HEAD = CONTEXT.tables[:3]


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
        CONTEXT.metric, format(3 * fx.FINAL_OCCUPANCY, ",d"), fx.unit(CONTEXT.metric), HEAD)
    assert peak == "single-call peak %s over the 3 whole windows: %s %s at proj-a/sess-0001.jsonl:14" % (
        fx.PEAK, format(fx.FINAL_OCCUPANCY, ",d"), fx.unit(fx.PEAK))
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
    drillable = set(schema.KIND_DIMENSIONS[INCREMENT]) - set(CONTEXT.tables)
    assert schema.WINDOW_DIM in drillable  # D-WINDOW-DIM: one row per file is never a default table
    for dim in drillable:
        assert "by " + dim not in out
        assert "by " + dim in fx.run_cli("context", "--root", str(root), "--by", dim)[1]
    assert "%s: %s" % (schema.WINDOW_HEAD, render.UNSPLITTABLE[schema.WINDOW_HEAD]) in out
    assert re.search(r"^%s\s" % schema.AMBIGUOUS, out, re.M)
    assert re.search(r"^%s \(signed\)\s+-300\s" % schema.SHRINK, out, re.M)
    assert re.search(r"^by %s\s+%s\s+%s\s+share of [\d,]+$"
                     % (CAUSE, CONTEXT.metric, fx.count_column(CONTEXT.metric)), out, re.M)


def test_spend_prints_totals_over_the_selection_and_the_largest_call(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("spend", "--root", str(root), "--where", "project=proj-a")
    assert code == 0, err
    first, peak, note = out.splitlines()[:3]
    assert first.startswith("%s: " % SPEND.metric) and fx.unit(SPEND.metric) in first
    # project is pinned; agent is the most specific table left, and the fork
    # bills exactly what its parent does, so it is half the total.
    assert re.search(r"over 14 call facts in 2 windows; top %s=agent-fake1 [\d,]+ \(50\.0%% of the [\d,]+ total\)$"
                     % schema.AGENT_DIM, first)
    assert peak.startswith("single-call peak ") and note == cli.SPEND_NOTE
    assert "duplicate records excluded; where project=proj-a" in out
    assert re.search(r"^by %s\s+%s\s+%s\s+share of [\d,]+$"
                     % (SPEND.tables[0], SPEND.metric, fx.count_column(SPEND.metric)), out, re.M)
    assert fx.count_column(SPEND.metric) != fx.count_column(CONTEXT.metric)  # each view names its carrier
    assert re.search(r"^single-call peak %s over the 2 whole windows: %s %s at proj-a/sess-0001\.jsonl:14$"
                     % (fx.PEAK, format(fx.FINAL_OCCUPANCY, ",d"), fx.unit(fx.PEAK)), out, re.M)
    for dim in SPEND.tables:
        assert "by " + dim in out
    assert "by %s" % CAUSE not in out
    assert "by %s" % CAUSE in fx.run_cli("context", "--root", str(root))[1]  # vacuity guard


def _top_of(out):
    return re.search(r"; top (\w+)=", out.splitlines()[0]).group(1)


def test_headline_leads_with_the_largest_lever_row_ties_to_the_more_specific(tmp_path):
    """The default tables print cause first, but cause is no lever (a
    category is not an answer): Bash:pytest carries all of Bash's 750, so
    the head leads, being as large and more specific; pinning a lever hands
    the lead to the other; both pinned, nothing leads; ``--by`` overrides."""
    root = fx.cli_corpus(tmp_path)
    assert CONTEXT.tables[0] == CAUSE and CAUSE not in CONTEXT.levers
    assert set(CONTEXT.levers) == {TOOL, HEAD}
    code, out, err = fx.run_cli("context", "--root", str(root))
    assert code == 0, err
    assert "; top %s=Bash:pytest 750 (16.4%% of the 4,560 total)" % HEAD in out.splitlines()[0]
    assert re.search(r"^Bash\s+750\s", out, re.M)  # the tie: the tool row is as large
    assert re.search(r"^%s\s+750\s" % schema.TOOL_RESULT, out, re.M)  # the top cause, not led with
    where = ["--where", "%s=Bash:pytest" % HEAD]
    assert _top_of(fx.run_cli("context", "--root", str(root), *where)[1]) == TOOL
    where += ["--where", "%s=Bash" % TOOL]
    assert "; top " not in fx.run_cli("context", "--root", str(root), *where)[1].splitlines()[0]
    assert _top_of(fx.run_cli("context", "--root", str(root), "--by", CAUSE)[1]) == CAUSE
    assert _top_of(fx.run_cli("spend", "--root", str(root))[1]) == schema.AGENT_DIM
    assert SPEND.tables[0] != schema.AGENT_DIM  # vacuity guard: not the first table printed


def test_headline_names_the_largest_lever_row_even_from_a_less_specific_table(tmp_path):
    """One interval with two Bash results of different heads (ambiguous,
    sharing tool=Bash and no head) and one exact Read: the top head,
    Read:py 70, is not under the top tool, Bash 100, and is smaller, so the
    tool leads. The window tables' one row is the whole total and never
    leads: they are no lever."""
    uses = [fx.tool_use("toolu_0001", "Bash", command="ls"),
            fx.tool_use("toolu_0002", "Bash", command="make")]
    records = [fx.assistant("uuid-0001", "msg-0001", fx.usage(1000, 0), uses),
               fx.tool_result("uuid-0002", "toolu_0001"), fx.tool_result("uuid-0003", "toolu_0002"),
               fx.assistant("uuid-0004", "msg-0002", fx.usage(1100, 0),
                            [fx.tool_use("toolu_0003", "Read", file_path="/x/a.py")]),
               fx.tool_result("uuid-0005", "toolu_0003"),
               fx.assistant("uuid-0006", "msg-0003", fx.usage(1170, 0))]
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": records})
    facts = fx.load_facts(root)[1]

    def top(dim):
        return next((r.value, r.mass) for r in query.group(facts, dim, fx.DELTA).rows
                    if r.kind == query.REGULAR and r.value not in render.UNSPLITTABLE)
    assert (top(TOOL), top(HEAD)) == (("Bash", 100), ("Read:py", 70))  # guard: the masses
    assert not top(HEAD)[0].startswith(top(TOOL)[0])  # the top head is not under the top tool
    assert top(schema.PROJECT_DIM)[1] == 1170 > 100  # the window row is larger still
    code, out, err = fx.run_cli("context", "--root", str(root))
    assert code == 0, err
    assert "; top %s=Bash 100 (8.5%% of the 1,170 total)" % TOOL in out.splitlines()[0]
    assert re.search(r"^%s\s+100\s" % schema.AMBIGUOUS, out, re.M)  # Bash's mass, by its tool only


def test_the_headline_never_names_ambiguous_as_the_lever(tmp_path):
    """One interval with two Read results: ambiguous is the largest regular
    cause after window_head, and the headline passes over both."""
    uses = [fx.tool_use("toolu_0001", "Read", file_path="/x/a.py"),
            fx.tool_use("toolu_0002", "Read", file_path="/x/b.py")]
    records = [fx.assistant("uuid-0001", "msg-0001", fx.usage(1000, 50), uses),
               fx.tool_result("uuid-0002", "toolu_0001"), fx.tool_result("uuid-0003", "toolu_0002"),
               fx.assistant("uuid-0004", "msg-0002", fx.usage(1300, 0))]
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": records})
    code, out, err = fx.run_cli("context", "--root", str(root), "--by", CAUSE)
    assert code == 0, err
    rows = [l.split() for l in out.splitlines() if l.endswith("%")]
    assert [r[0] for r in rows] == [schema.WINDOW_HEAD, schema.AMBIGUOUS, schema.FEED_FORWARD]
    assert "; top %s=%s 50 (3.8%% of the 1,300 total)" % (CAUSE, schema.FEED_FORWARD) in out.splitlines()[0]
    for value in (schema.WINDOW_HEAD, schema.AMBIGUOUS):
        assert "%s: %s" % (value, render.UNSPLITTABLE[value]) in out
    # Vacuity guard: with one result the interval is exact and leads.
    root = fx.corpus(tmp_path / "exact", {"proj-a/sess-0001.jsonl": records[:2] + records[3:]})
    out = fx.run_cli("context", "--root", str(root), "--by", CAUSE)[1]
    assert "; top %s=%s 250 " % (CAUSE, schema.TOOL_RESULT) in out.splitlines()[0]
    assert "%s: %s" % (schema.AMBIGUOUS, render.UNSPLITTABLE[schema.AMBIGUOUS]) not in out


def test_headline_share_is_of_the_total_while_the_table_share_is_of_its_base(tmp_path):
    """Bash carries 750 of 4,560 tokens: the table's share column is over the
    750 that have a tool at all; the headline says 750 of the 4,560 total."""
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--by", TOOL)
    assert code == 0, err
    assert re.search(r"^%s\s+4,110\s+\d+\s+-$" % re.escape(render.RESIDUAL_LABEL), out, re.M)
    assert re.search(r"^%s \(signed\)\s+-300\s" % schema.SHRINK, out, re.M)
    assert "; top %s=Bash 750 (16.4%% of the 4,560 total)" % TOOL in out.splitlines()[0]
    assert re.search(r"^by %s\s.*\s+%s\s+share of 750$" % (TOOL, fx.count_column(CONTEXT.metric)), out, re.M)
    assert re.search(r"^Bash\s+750\s+3\s+100\.0%$", out, re.M)


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


@pytest.mark.parametrize("drill", [[], ["--where", "%s=%s" % (CAUSE, schema.TOOL_RESULT)]])
def test_a_reconciliation_mismatch_is_exit_status_1(tmp_path, monkeypatch, capsys, drill):
    root = fx.cli_corpus(tmp_path)
    whole = walk.walk
    monkeypatch.setattr(walk, "walk", lambda source, usages: [
        f for f in whole(source, usages) if f.dims.get(CAUSE) != schema.SHRINK])
    assert cli.main(["context", "--root", str(root)] + drill) == 1
    out = capsys.readouterr().out
    assert "MISMATCH" in out and "OK" not in out
    monkeypatch.undo()
    assert cli.main(["context", "--root", str(root)] + drill) == 0  # vacuity guard


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
