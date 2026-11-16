"""``python3 -m sa`` end to end against ``fixtures.cli_corpus``: what each
view prints. Metric names, units and dimensions come from ``cli.VIEWS`` and
the schema; what the arguments refuse is ``test_cli_args``, what a drill
prints is ``test_cli_drill``, what the headline walks is ``test_cli_headline``."""
import re

import pytest

import fixtures as fx
from sa import cli, glossary, headline, render, residual, schema, tables, walk
from sa.schema import INCREMENT

CONTEXT, SPEND = cli.VIEWS["context"], cli.VIEWS["spend"]
CAUSE, TOOL, HEAD = schema.CAUSE_DIM, schema.TOOL_DIM, schema.COMMAND_DIM


def test_context_reconciles_and_counts_its_population(tmp_path):
    root = fx.cli_corpus(tmp_path)
    loaded, facts = fx.load_facts(root)
    code, out, err = fx.run_cli("context", "--root", str(root))
    assert code == 0, err
    (read, kept, orphan), answer = fx.sections(out)[:2]
    first, (average,) = fx.headline(out), fx.average(out)
    # starting_context is the largest cause (253,000 of 254,560) but cause is no
    # lever: it is the starting context, by started_by; the growth walks down
    # the top tool and its top command. Every share is of the 254,860 added
    # (the shrink row out), as in the cause table, which the checks state.
    assert re.search(r"^%s\s+253,000\s" % schema.STARTING_CONTEXT, out, re.M)
    assert first == ("%s%s across 3 windows; starting context%s 253,000 99.3%% = %s 252,000 + %s 1,000;"
                     " growth 1,860 0.7%% from Bash 750 → Bash:pytest 750") % (
        fx.total_line(CONTEXT.metric), format(3 * fx.FINAL_OCCUPANCY + 250000, ",d"), glossary.MARKER,
        headline.START_LABELS[schema.SESSION_START], headline.START_LABELS[schema.FORK])
    assert out.splitlines()[-1].startswith("%s checks: 254,860 added - 300 %s = 254,560; " % (
        tables.OK_MARK, schema.SHRINK))  # the shares' base, and what shrank
    assert fx.unit(CONTEXT.metric) == fx.printed(CONTEXT.metric)  # so the total line states it once
    assert re.search(r"^%s\s+253,000\s+\d+\s+99\.3%%$" % schema.STARTING_CONTEXT, out, re.M)  # one base
    windows = {f.window for f in facts}
    held = [f.metrics[fx.PEAK] for f in facts if f.kind == schema.CALL]  # what each call held
    assert len(windows) == 3 and average == "%s%s %s, over %d calls in 3 windows" % (
        fx.AVERAGE, tables.num(sum(held) / len(held)), fx.unit(fx.PEAK), len(held))
    assert read == ("read: %d files modified in the last 7d (default) under %s, 0 lines skipped,"
                    " 0 duplicates excluded" % (len(loaded.files), root))
    assert kept == "in view: 3 windows%s, %d %s%s" % (
        glossary.MARKER, sum(f.kind == INCREMENT for f in facts), schema.PLURAL[INCREMENT], glossary.MARKER)
    assert orphan == " " * len("in view: ") + "1 fork whose parent is missing: its copy counts as its own"
    assert out.count(str(root)) == 1  # locators are root-relative
    # The cause table closes with its total against the final sizes; the
    # intervals collapse to one checks line, last.
    assert re.search(r"^%s\s+%s\s+%d\s+%s = final window sizes$" % (
        tables.TOTAL_LABEL, format(3 * fx.FINAL_OCCUPANCY + 250000, ",d"), sum(f.kind == INCREMENT for f in facts),
        tables.OK_MARK), out, re.M)
    assert out.splitlines()[-1] == ("%s checks: 254,860 added - 300 shrink = 254,560; 18 gaps between calls"
                                    " (21 calls - 3 windows): 6 to one source (33.3%%), 9 ambiguous (50.0%%),"
                                    " 3 shrank (16.7%%)" % tables.OK_MARK)
    assert "reconciliation" not in out and "MISMATCH" not in out  # full detail only on failure
    titles = [line.split(":")[0].split("  ")[0] for line in out.splitlines() if line.startswith("by ")]
    for dim in CONTEXT.tables:  # a table, or a line its rows share with the tables repeating it
        assert any(re.search(r"\b%s\b" % dim, t) for t in titles), dim
    drillable = set(schema.KIND_DIMENSIONS[INCREMENT]) - set(CONTEXT.tables)
    assert schema.WINDOW_DIM in drillable  # D-CONTEXT-WINDOW: one row per window is never a default table
    for dim in drillable:
        assert not re.search(r"^by %s\s" % dim, out, re.M)
        assert re.search(r"^by %s\s" % dim, fx.run_cli("context", "--root", str(root), "--by", dim)[1], re.M)
    assert (glossary.printed(schema.STARTING_CONTEXT), tables.UNSPLITTABLE[schema.STARTING_CONTEXT]) in fx.key(out)
    assert re.search(r"^%s\*?\s" % schema.AMBIGUOUS, out, re.M)
    assert re.search(r"^%s \(signed\)\s+-300\s" % schema.SHRINK, out, re.M)
    assert re.search(r"^by %s\s+%s\s+%s\s+share of [\d,]+ added$"
                     % (CAUSE, fx.printed(CONTEXT.metric), fx.count_column(CONTEXT.metric)), out, re.M)


def test_spend_prints_totals_over_the_selection_and_the_largest_call(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("spend", "--root", str(root), "--where", "project=proj-a")
    assert code == 0, err
    first, (average,) = fx.headline(out), fx.average(out)
    assert first.startswith(fx.total_line(SPEND.metric)) and fx.unit(SPEND.metric) in first
    # project is pinned; subagent is spend's lever, and the fork bills exactly
    # what its parent does, so it is half the total.
    assert re.search(r"over 14 calls in 2 windows; largest %s [\d,]+ 50\.0%% agent-fake1$"
                     % schema.SUBAGENT_DIM, first)
    assert average.startswith(fx.AVERAGE) and (SPEND.metric, cli.SPEND_NOTE) in fx.key(out)
    others = [name for name, spec in schema.METRICS.items()  # footer totals name their population
              if spec.carrier == schema.CALL and spec.aggregation == schema.ADDITIVE
              and name != SPEND.metric]
    assert others  # vacuity guard
    for name in others:
        assert re.search(r"^%s: [\d,]+ %s over 14 calls in 2 windows$"
                         % (name, fx.unit(name)), out, re.M)
    assert "\nin view where project=proj-a: 2 windows%s, 14 calls\n" % glossary.MARKER in out  # spend reads calls only
    assert re.search(r"^by %s\s+%s\s+%s\s+share of [\d,]+ \(all but unassigned\)$"
                     % (schema.SUBAGENT_DIM, fx.printed(SPEND.metric), fx.count_column(SPEND.metric)),
                     out, re.M)
    assert fx.count_column(SPEND.metric) != fx.count_column(CONTEXT.metric)  # each view names its carrier
    assert average == "%s%s %s, over 14 calls in 2 windows" % (  # two like windows: one window's mean
        fx.AVERAGE, tables.num(sum(f.metrics[fx.PEAK] for f in fx.load_facts(root)[1]
                                   if f.kind == schema.CALL and f.window.line == 1
                                   and f.dims[schema.SESSION_DIM] == fx.SESSION) / 14), fx.unit(fx.PEAK))
    assert "by %s" % CAUSE not in out
    assert "by %s" % CAUSE in fx.run_cli("context", "--root", str(root))[1]  # vacuity guard


def test_main_windows_carry_no_agent_and_land_in_the_residual_row(tmp_path):
    """D-AGENT-DIM: nine sessions' main windows are not one subagent."""
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("spend", "--root", str(root), "--by", schema.SUBAGENT_DIM)
    assert code == 0, err
    assert re.search(r"; largest %s [\d,]+ 0\.6%% agent-fake1$"
                     % schema.SUBAGENT_DIM, fx.headline(out))  # the one subagent, beside a 200K+ window
    assert re.search(r"^%s\s+[\d,]+\s+14\s+-  %s$" % (re.escape(tables.RESIDUAL_ROW),  # what it holds here
                     residual.RESIDUAL_NOTES[schema.SUBAGENT_DIM][0]), out, re.M)
    assert (tables.RESIDUAL_LABEL, glossary.brief(tables.RESIDUAL_LABEL)) in fx.key(out)
    assert "%s=main" % schema.SUBAGENT_DIM not in out
    facts = fx.load_facts(root)[1]
    by_file = {f.locator.file: f.dims.get(schema.SUBAGENT_DIM) for f in facts}
    assert by_file == {"proj-a/sess-0001.jsonl": None, "proj-b/sess-0002.jsonl": None,
                       "proj-a/sess-0001/subagents/agent-fake1.jsonl": "agent-fake1"}


@pytest.mark.parametrize("drill", [[], ["--where", "%s=%s" % (CAUSE, schema.TOOL_RESULT)]])
def test_a_reconciliation_mismatch_is_exit_status_1(tmp_path, monkeypatch, capsys, drill):
    root = fx.cli_corpus(tmp_path)
    whole = walk.walk
    monkeypatch.setattr(walk, "walk", lambda *args: [
        f for f in whole(*args) if f.dims.get(CAUSE) != schema.SHRINK])
    assert cli.main(["context", "--root", str(root)] + drill) == 1
    out = capsys.readouterr().out
    assert ": MISMATCH" in out and tables.OK_MARK + " checks" not in out  # full detail on failure
    assert out.splitlines()[-1] == "it holds by construction (walk.py), so a mismatch is a bug in this tool"
    first = fx.headline(out)
    assert "final size" not in first  # the headline never claims the sum it failed to match
    if not drill:
        assert " across 3 windows (reconciliation MISMATCH below)" in first
        assert "%s does not match the final window sizes (below)" % tables.BAD_MARK in out
    monkeypatch.undo()
    assert cli.main(["context", "--root", str(root)] + drill) == 0  # vacuity guard
    out = capsys.readouterr().out
    assert ("across 3 windows; " in fx.headline(out)) == (not drill)
    assert ": MISMATCH" not in out and tables.OK_MARK + " checks" in out


def test_a_subagent_prints_by_its_recorded_type_and_pins_by_either_name(tmp_path):
    """A subagent file's ``.meta.json`` sidecar records its type: tables, the
    headline and the hint print ``<type> <first 8 of the id>``, and
    ``--where subagent=`` takes that or the whole id. The id stays the value."""
    root = fx.cli_corpus(tmp_path)
    sub = root / "proj-a/sess-0001/subagents/agent-fake1.jsonl"
    plain = fx.run_cli("spend", "--root", str(root))[1]
    assert "Explore" not in plain and "agent-fake1" in fx.headline(plain)  # vacuity guard: no sidecar
    sub.with_suffix(".meta.json").write_text('{"agentType": "Explore"}')
    label = "Explore agent-fa"
    code, out, err = fx.run_cli("spend", "--root", str(root), "--by", schema.SUBAGENT_DIM)
    assert code == 0, err
    assert fx.headline(out).endswith(" %s" % label)
    assert re.search(r"^%s\s+[\d,]+\s+7\s" % label, out, re.M)
    assert "%s--where '%s=%s'" % (render.NEXT, schema.SUBAGENT_DIM, label) in out
    pinned = [fx.run_cli("spend", "--root", str(root), "--where", "%s=%s" % (schema.SUBAGENT_DIM, v))
              for v in (label, "agent-fake1")]
    assert pinned[0][0] == 0 and pinned[0][1] == pinned[1][1] and "7 calls" in pinned[0][1]


def test_two_subagents_one_label_keep_their_whole_ids():
    def fact(agent, file):
        return schema.Fact(schema.CALL, {schema.SUBAGENT_DIM: agent}, {}, schema.Locator(file, 1, None), {}, None)
    facts = [fact("a1234567aa", "x.jsonl"), fact("a1234567bb", "y.jsonl"), fact("a7654321cc", "z.jsonl")]
    names = render.subagent_names({"x.jsonl": "Plan", "y.jsonl": "Plan", "z.jsonl": "Plan"}, facts)
    assert names == {"a7654321cc": "Plan a7654321"}  # the two that share a label are not renamed
