"""``python3 -m sa`` end to end against a fixture corpus."""
import re
import subprocess
import sys
from pathlib import Path

import pytest

import fixtures as fx
from sa import cli, query, schema
from sa.schema import CALL, INCREMENT

REPO = Path(__file__).resolve().parents[1]


def _run(*args):
    done = subprocess.run([sys.executable, "-m", "sa"] + list(args), cwd=str(REPO),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True)
    return done.returncode, done.stdout, done.stderr


def _corpus(tmp_path):
    return fx.corpus(tmp_path, {
        "proj-a/sess-0001.jsonl": fx.window_records(),
        "proj-a/sess-0001/subagents/agent-fake1.jsonl":
            fx.window_records("fork-", session="sess-0001"),
        "proj-b/sess-0002.jsonl": fx.window_records("b-", session="sess-0002"),
        "proj-b/empty.jsonl": [fx.user_text("uuid-9001", session="sess-0003")],
    })


def test_context_reconciles_and_counts_its_population(tmp_path):
    root = _corpus(tmp_path)
    loaded, facts = fx.load_facts(root)
    code, out, err = _run("context", "--root", str(root))
    assert code == 0, err
    assert out.startswith("context_delta: %s context tokens = the 3 windows' final "
                          "occupancies summed; top cause=window_head"
                          % format(3 * fx.FINAL_OCCUPANCY, ",d"))
    assert "final occupancy %s: OK" % format(3 * fx.FINAL_OCCUPANCY, ",d") in out
    assert ("population: %d files read, 3 windows, %d call facts, %d increment facts; "
            "0 lines skipped, 0 duplicate records excluded\n"
            % (len(loaded.files), sum(f.kind == CALL for f in facts),
               sum(f.kind == INCREMENT for f in facts))) in out
    assert "intervals 18 (= 21 calls - 3 windows): exact 6 (33.3%) + ambiguous 9 (50.0%) " \
           "[multi_contributor 3, negative_remainder 3, no_contributor 3] + " \
           "shrink 3 (16.7%): OK" in out
    assert "\nexact: " in out
    for dim in schema.DIMENSIONS:
        assert "by " + dim in out
    assert re.search(r"^ambiguous\s", out, re.M)
    assert re.search(r"^shrink \(signed\)\s+-300\s", out, re.M)
    assert re.search(r"^by cause\s+context tokens\s+count\s+share of [\d,]+$", out, re.M)


def test_spend_prints_totals_over_the_selection_and_the_largest_call(tmp_path):
    root = _corpus(tmp_path)
    code, out, err = _run("spend", "--root", str(root), "--where", "project=proj-a")
    assert code == 0, err
    assert out.startswith("spend: ")
    assert "input-side" in out.splitlines()[0]
    assert "over 14 call facts in 2 windows" in out
    assert "duplicate records excluded; where project=proj-a" in out
    assert re.search(r"^context_tokens: largest single call %s context tokens, at "
                     r"\S+sess-0001\.jsonl:14$" % format(fx.FINAL_OCCUPANCY, ",d"),
                     out, re.M)
    for dim in schema.KIND_DIMENSIONS[CALL]:
        assert "by " + dim in out
    assert "by cause" not in out
    assert "by cause" in _run("context", "--root", str(root))[1]  # vacuity guard


@pytest.mark.parametrize("flag,value", [("--where", "tool=Bash"), ("--by", "cause")])
def test_spend_refuses_a_dimension_its_carrier_never_has(tmp_path, flag, value):
    root = _corpus(tmp_path)
    code, out, err = _run("spend", "--root", str(root), flag, value)
    assert code == 2 and not out
    assert "'%s' is never carried by call facts" % value.split("=")[0] in err
    code, out, err = _run("context", "--root", str(root), flag, value)  # vacuity guard
    assert code == 0, err
    assert re.search(r"^context_delta: [1-9]", out)


def test_a_drill_prints_the_whole_window_reconciliation_once_as_a_pointer(tmp_path):
    root = _corpus(tmp_path)
    code, out, err = _run("context", "--root", str(root), "--where", "cause=tool_result")
    assert code == 0, err
    assert out.startswith("context_delta: %s context tokens over 3 increment facts in 3 "
                          "windows" % format(3 * fx.EXACT_FIRST_DELTA, ",d"))
    assert "reconciliation: applies to the 3 whole windows above, not to this drill: OK" in out
    assert "reconciliation over" not in out
    assert "reconciliation over 3 windows" in _run("context", "--root", str(root))[1]


def test_since_selects_files_by_mtime_and_zero_days_selects_none(tmp_path):
    root = _corpus(tmp_path)
    code, out, err = _run("context", "--root", str(root), "--since", "0d")
    assert code == 0, err
    assert "population: 0 files read (modified within 0d), 0 windows" in out
    code, out, err = _run("context", "--root", str(root), "--since", "1d")
    assert code == 0, err
    assert "population: 4 files read (modified within 1d), 3 windows" in out


def test_by_fact_lists_evidence_lines(tmp_path):
    root = _corpus(tmp_path)
    code, out, err = _run("context", "--root", str(root), "--by", "fact",
                          "--where", "cause=tool_result", "--limit", "2")
    assert code == 0, err
    leaves = [l for l in out.splitlines() if re.match(r"\s+[\d,]+\s+\S+:\d+\s", l)]
    assert len(leaves) == 2 and all("cause=tool_result" in l for l in leaves)
    assert re.search(r"sess-0001\.jsonl:2\s+uuid-0002\s", out)


def test_unknown_dimension_is_refused(tmp_path):
    code, out, err = _run("context", "--root", str(_corpus(tmp_path)),
                          "--where", "colour=red")
    assert code == 2 and "unknown dimension" in err


def test_table_limit_reports_hidden_rows_and_never_hides_residual_or_shrink():
    rows = [query.Row("a", 60, 2, 0.6, query.REGULAR), query.Row("b", 30, 1, 0.3, query.REGULAR),
            query.Row("c", 10, 1, 0.1, query.REGULAR),
            query.Row(schema.RESIDUAL, 5, 1, None, query.RESIDUAL),
            query.Row(schema.SHRINK, -7, 1, None, query.SIGNED)]
    lines = cli._table("by x", rows, "u", limit=1)
    assert lines[0].endswith("share of 100")
    assert [l.split()[0] for l in lines[1:]] == ["a", "+2", schema.RESIDUAL, schema.SHRINK]
    assert re.match(r"\+2 more rows\s+40\s+2\s+40\.0%", lines[2])
    assert [l.split()[0] for l in cli._table("by x", rows, "u", limit=3)[1:]] == [
        "a", "b", "c", schema.RESIDUAL, schema.SHRINK]
