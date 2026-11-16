"""The scripts' testable pieces. ``scripts/screens.py``, the audit's
capture, runs on the README fixture: every screen it lists prints under its
``=====`` header with its exit status, refusals exit 2, and ``--root``
reaches every reading screen. ``scripts/agent_eval.py``'s static pieces:
task file, personas, templates (claude is not called; ``--dry-run`` is the
live check)."""
import json
import re
import subprocess
import sys
from pathlib import Path

import fixtures as fx
from test_screen_budgets import _load_resync


SCRIPT = fx.REPO / "scripts" / "screens.py"


def test_screens_prints_every_listed_screen_with_its_exit(tmp_path):
    home = tmp_path.resolve()
    _load_resync().build(home)
    done = subprocess.run([sys.executable, str(SCRIPT), "--root", str(home / ".claude" / "projects")],
                          cwd=str(fx.REPO), env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    assert done.returncode == 0, done.stderr
    heads = re.findall(r"^===== \$ python3 -m sa(.*)$", done.stdout, re.M)
    exits = [int(n) for n in re.findall(r"^\[exit (\d+)\]$", done.stdout, re.M)]
    assert len(heads) == len(exits) >= 12  # vacuity guard: the whole list printed
    assert exits.count(2) == 3 and set(exits) == {0, 2}  # three refusals, every other screen runs
    assert sum("--root" in h for h in heads) == len(heads) - 2  # the front door and -h take none
    assert "\n✓ numbers add up" in done.stdout and "by change, files in " in done.stdout


EVALS = Path(__file__).resolve().parents[1] / "evals"
PERSONAS = {p.stem for p in (EVALS / "personas").glob("*.md")}
TASKS = json.loads((EVALS / "tasks.json").read_text())["tasks"]
# A question naming grammar would teach the agent what it must discover.
GRAMMAR = re.compile(r"--\w|\bsa\s+\w")


def test_every_task_names_principles_personas_and_truth():
    assert TASKS and {"hurried", "scientific"} <= PERSONAS  # vacuity guard
    ids = [t["id"] for t in TASKS]
    assert len(ids) == len(set(ids))
    for t in TASKS:
        assert t["principles"] and set(t["principles"]) <= {1, 2, 3}, t["id"]
        assert t["personas"] and set(t["personas"]) <= PERSONAS, t["id"]
        assert t["truth"] and all(c.startswith("sa") for c in t["truth"]), t["id"]


def test_three_held_out_and_questions_stay_grammar_agnostic():
    assert sum(bool(t.get("held_out")) for t in TASKS) == 3
    assert GRAMMAR.search("run `sa contxt --were tol=Bash`")  # vacuity guard
    for t in TASKS:
        assert bool(GRAMMAR.search(t["question"])) == bool(t.get("gives_command")), t["id"]


def test_prompt_templates_fill():
    agent = (EVALS / "agent_prompt.md").read_text()
    agent.format(persona="p", question="q")
    assert not GRAMMAR.search(agent) and "-h" not in agent
    (EVALS / "grader_prompt.md").read_text().format(
        id="i", persona="p", principles=[1], question="q", note="n",
        truth="t", session="s", answer="a")


def _harness():
    import importlib.util
    path = Path(__file__).resolve().parents[1] / "scripts" / "agent_eval.py"
    spec = importlib.util.spec_from_file_location("agent_eval", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_sa_commands_counted_after_a_cd_prefix():
    ae = _harness()
    assert ae.SA_CMD.search("python3 -m sa -h")  # vacuity guard
    assert ae.SA_CMD.search("cd /tmp/x; python3 -m sa context")
    assert ae.SA_CMD.search("cd /tmp/x && python3 -m sa context")
    assert not ae.SA_CMD.search("echo usa context")


def test_measure_tolerates_events_whose_message_is_text(tmp_path):
    ae = _harness()
    events = [{"type": "system", "message": "a plain string"},
              {"type": "result", "result": "ANSWER: x\nFRICTION: none"}]
    m, _ = ae.measure(events, tmp_path, tmp_path / "no.log")
    assert m["friction"] == "none" and m["sa_cmds"] == 0


def test_the_snapshot_skips_temp_dir_projects(tmp_path):
    """Eval runs' own `claude -p` transcripts land in ~/.claude/projects as
    `-tmp-...` projects; a snapshot never grades the tool on them."""
    home, snap = tmp_path / "projects", tmp_path / "snap"
    for project in ("-home-me-work", "-tmp-sa-eval-x"):
        (home / project).mkdir(parents=True)
        (home / project / "s.jsonl").write_text("{}\n")
    _harness().snapshot(home, snap, 7)
    assert [p.name for p in snap.iterdir()] == ["-home-me-work"]  # vacuity guard: one copied


def test_every_truth_command_parses_in_the_current_grammar():
    """Truth commands are the grader's ground truth: none uses a retired flag."""
    import sys
    sys.path.insert(0, str(EVALS.parent))
    from sa import grammar
    for t in TASKS:
        for command in t["truth"]:
            words = command.split()[1:]
            if t.get("gives_command") and command == t["truth"][0]:
                continue  # the typo the journey recovers from
            grammar.parse(words)  # a UsageError fails the test
