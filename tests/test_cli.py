"""``python3 -m sa`` end to end against a fixture corpus."""
import re
import subprocess
import sys
from pathlib import Path

import fixtures as fx
from sa import schema
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
    assert "final occupancy %s: OK" % format(3 * fx.FINAL_OCCUPANCY, ",d") in out
    assert ("population: %d files read, 3 windows, %d call facts, %d increment facts; "
            "0 lines skipped, 0 duplicate records dropped"
            % (len(loaded.files), sum(f.kind == CALL for f in facts),
               sum(f.kind == INCREMENT for f in facts))) in out
    assert "intervals 15: exact 6 (40.0%), ambiguous 6 (40.0%)" in out
    assert "shrink 3 (20.0%)" in out
    for dim in schema.DIMENSIONS:
        assert "by " + dim in out
    assert re.search(r"^ambiguous\s", out, re.M)
    assert re.search(r"^shrink \(signed\)\s+-300\s", out, re.M)
    assert "top cause=window_head" in out  # the residual never heads a table


def test_spend_prints_totals_and_the_largest_window(tmp_path):
    root = _corpus(tmp_path)
    code, out, err = _run("spend", "--root", str(root), "--where", "agent=main")
    assert code == 0, err
    assert out.startswith("spend: ")
    assert "where: agent=main" in out
    assert "context_tokens: largest single window %s context tokens, in " % format(
        fx.FINAL_OCCUPANCY, ",d") in out
    assert "by cause" not in out  # call facts carry no cause


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
