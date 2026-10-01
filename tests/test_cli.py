"""``python3 -m sa`` end to end against ``fixtures.cli_corpus``: what each
view prints. Metric names, units and dimensions come from ``cli.VIEWS`` and
the schema; what the arguments refuse is ``test_cli_args``, what a drill
prints is ``test_cli_drill``, what the headline walks is ``test_cli_headline``."""
import re

import pytest

import fixtures as fx
from sa import cli, schema, tables, walk
from sa.schema import CALL, INCREMENT

CONTEXT, SPEND = cli.VIEWS["context"], cli.VIEWS["spend"]
CAUSE, TOOL, HEAD = CONTEXT.tables[:3]


def test_context_reconciles_and_counts_its_population(tmp_path):
    root = fx.cli_corpus(tmp_path)
    loaded, facts = fx.load_facts(root)
    code, out, err = fx.run_cli("context", "--root", str(root))
    assert code == 0, err
    first, peak, population = out.splitlines()[:3]
    # window_head is the largest cause (3,000 of 4,560) but cause is no lever:
    # the headline walks down the top tool and its top head, as shares of
    # the total.
    assert re.search(r"^%s\s+3,000\s" % schema.WINDOW_HEAD, out, re.M)
    assert first == ("%s: %s %s = the 3 windows' final occupancies summed; top %s=Bash 750"
                     " (16.4%% of the 4,560 total); within it %s=Bash:pytest 750"
                     " (100.0%% of Bash, 16.4%% of the total)") % (
        CONTEXT.metric, format(3 * fx.FINAL_OCCUPANCY, ",d"), fx.unit(CONTEXT.metric), TOOL, HEAD)
    assert peak == "single-call peak %s over the 3 whole windows: %s %s at proj-a/sess-0001.jsonl:14" % (
        fx.PEAK, format(fx.FINAL_OCCUPANCY, ",d"), fx.unit(fx.PEAK))
    assert population == (
        "population: root %s; %d files read, 3 windows, %d call facts, %d increment facts; "
        "0 lines skipped, 0 duplicate records excluded"
        % (root, len(loaded.files), sum(f.kind == CALL for f in facts),
           sum(f.kind == INCREMENT for f in facts)))
    assert out.count(str(root)) == 1  # locators are root-relative
    assert ("final occupancy %s: OK; holds by construction (walk.py), so a mismatch is a bug"
            " in this tool" % format(3 * fx.FINAL_OCCUPANCY, ",d")) in out
    reasons = ", ".join("%s 3" % r for r in schema.REASONS)
    assert "intervals 18 (= 21 calls - 3 windows): exact 6 (33.3%) + ambiguous 9 (50.0%) " \
           "[" + reasons + "] + shrink 3 (16.7%): OK" in out
    assert "\nexact: " in out and "[OPEN]" not in out
    for dim in CONTEXT.tables:
        assert "by " + dim in out
    drillable = set(schema.KIND_DIMENSIONS[INCREMENT]) - set(CONTEXT.tables)
    assert schema.WINDOW_DIM in drillable  # D-WINDOW-DIM: one row per file is never a default table
    for dim in drillable:
        assert not re.search(r"^by %s\s" % dim, out, re.M)
        assert re.search(r"^by %s\s" % dim, fx.run_cli("context", "--root", str(root), "--by", dim)[1], re.M)
    assert "%s: %s" % (schema.WINDOW_HEAD, tables.UNSPLITTABLE[schema.WINDOW_HEAD]) in out
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
    others = [name for name, spec in schema.METRICS.items()  # footer totals name their population
              if spec.carrier == schema.CALL and spec.aggregation == schema.ADDITIVE
              and name != SPEND.metric]
    assert others  # vacuity guard
    for name in others:
        assert re.search(r"^%s: [\d,]+ %s over 14 call facts in 2 windows$"
                         % (name, fx.unit(name)), out, re.M)
    assert "duplicate records excluded; where project=proj-a" in out
    assert re.search(r"^by %s\s+%s\s+%s\s+share of [\d,]+$"
                     % (schema.AGENT_DIM, SPEND.metric, fx.count_column(SPEND.metric)), out, re.M)
    assert fx.count_column(SPEND.metric) != fx.count_column(CONTEXT.metric)  # each view names its carrier
    assert re.search(r"^single-call peak %s over the 2 whole windows: %s %s at proj-a/sess-0001\.jsonl:14$"
                     % (fx.PEAK, format(fx.FINAL_OCCUPANCY, ",d"), fx.unit(fx.PEAK)), out, re.M)
    assert "by %s" % CAUSE not in out
    assert "by %s" % CAUSE in fx.run_cli("context", "--root", str(root))[1]  # vacuity guard


def test_main_windows_carry_no_agent_and_land_in_the_residual_row(tmp_path):
    """D-AGENT-DIM: nine sessions' main windows are not one agent."""
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("spend", "--root", str(root), "--by", schema.AGENT_DIM)
    assert code == 0, err
    assert re.search(r"; top %s=agent-fake1 [\d,]+ \(33\.3%% of the [\d,]+ total\)$"
                     % schema.AGENT_DIM, out.splitlines()[0])  # one of three like windows
    assert re.search(r"^%s\s+[\d,]+\s+14\s+-$" % re.escape(tables.RESIDUAL_LABEL), out, re.M)
    assert tables.RESIDUAL_NOTES[schema.AGENT_DIM] in out
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
    assert ": MISMATCH" in out and ": OK" not in out
    monkeypatch.undo()
    assert cli.main(["context", "--root", str(root)] + drill) == 0  # vacuity guard
