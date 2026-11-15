"""The README and SKILL example blocks are the fixture corpus's live output:
``scripts/resync_examples.py --check`` finds no drift."""
import re
import subprocess
import sys

from fixtures import REPO

SCRIPT = REPO / "scripts" / "resync_examples.py"


def test_every_doc_carries_an_example_marker():
    """Vacuity guard: a doc with no marker would always pass the check."""
    for name in ("README.md", "skills/session-analyzer/SKILL.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert re.search(r"^<!-- example: .+ -->\n```\n", text, re.M), name


def test_the_examples_match_the_fixture_output():
    done = subprocess.run([sys.executable, str(SCRIPT), "--check"], cwd=str(REPO),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    assert done.returncode == 0, done.stdout + done.stderr + " (run scripts/resync_examples.py)"
