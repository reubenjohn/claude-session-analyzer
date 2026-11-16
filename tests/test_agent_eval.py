"""The agent-eval harness's static pieces: task file, personas, templates.

Does not call claude; scripts/agent_eval.py --dry-run is the live check.
"""
import json
import re
from pathlib import Path

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
