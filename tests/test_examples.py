"""The README and SKILL example blocks are the fixture corpus's live output:
``scripts/resync_examples.py --check`` finds no drift. The same corpus's
default output stays within its cap (D-OUTPUT-CAP)."""
import importlib.util
import re
import subprocess
import sys

from fixtures import REPO

SCRIPT = REPO / "scripts" / "resync_examples.py"
# D-OUTPUT-CAP: the default `context --since 7d` output at ux-pass HEAD (decc4fe),
# before A1, on this corpus with the root printed as `~`. No headroom.
CAP_LINES, CAP_CHARS = 46, 3228


def test_every_doc_carries_an_example_marker():
    """Vacuity guard: a doc with no marker would always pass the check."""
    for name in ("README.md", "skills/session-analyzer/SKILL.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert re.search(r"^<!-- example: .+ -->\n```\n", text, re.M), name


def test_the_examples_match_the_fixture_output():
    done = subprocess.run([sys.executable, str(SCRIPT), "--check"], cwd=str(REPO),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    assert done.returncode == 0, done.stdout + done.stderr + " (run scripts/resync_examples.py)"


def test_the_default_output_stays_within_its_baseline(tmp_path):
    """Lines and characters, root pinned: the corpus sits under a temporary
    HOME the output prints as ``~``, so the temp path's length cannot move
    the count."""
    spec = importlib.util.spec_from_file_location("resync_examples", str(SCRIPT))
    resync = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(resync)
    home = tmp_path.resolve()
    resync.build(home)
    out = resync.run(home, "context --since 7d")
    assert out.startswith("read: ") and "\ncontext_delta: " in out  # vacuity guard: the headline
    assert "starting context " in out and "; top tool=" in out       # both of its lines
    assert str(home) not in out and resync.re.sub(r"[^A-Za-z0-9]", "-", str(home)) not in out  # pinned
    assert len(out.splitlines()) <= CAP_LINES, out
    assert len(out) <= CAP_CHARS, out
