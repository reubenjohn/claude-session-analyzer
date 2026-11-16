"""The docs as tested artifacts. Each doc is within the cap AGENTS.md
states, in bytes like the pre-commit size gates (the docs print multi-byte
marks such as ✓ and →, so bytes are the stricter and unambiguous count).
The README and SKILL example blocks are the fixture corpus's live output:
``scripts/resync_examples.py --check`` finds no drift. The same corpus's
default output stays within its cap (D-OUTPUT-CAP)."""
import importlib.util
import re
import subprocess
import sys

import pytest

import fixtures as fx
from fixtures import REPO
from sa import glossary, schema


CAPS = {"README.md": 5000, "skills/session-analyzer/SKILL.md": 6000, "AGENTS.md": 7000, "CLAUDE.md": 100}


@pytest.mark.parametrize("name", sorted(CAPS))
def test_each_doc_is_within_its_cap(name):
    path = REPO / name
    assert path.is_file() and path.stat().st_size > 0, name  # vacuity guard: it exists, non-empty
    size = len(path.read_bytes())
    assert size <= CAPS[name], "%s is %d bytes, cap %d" % (name, size, CAPS[name])


SCRIPT = REPO / "scripts" / "resync_examples.py"
# D-OUTPUT-CAP: the default `context --since 7d` output at ux-pass HEAD (decc4fe),
# on this corpus with the root printed as `~`. No headroom.
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
    assert out.startswith("read: ") and "\n" + fx.total_line(fx.HELD) in out  # vacuity guard: the headline
    assert "\n  %s%s " % (schema.STARTING_CONTEXT.replace("_", " "), glossary.MARKER) in out  # its block
    assert "\n  growth " in out and " largest: Bash " in out
    assert str(home) not in out and resync.re.sub(r"[^A-Za-z0-9]", "-", str(home)) not in out  # pinned
    assert len(out.splitlines()) <= CAP_LINES, out
    assert len(out) <= CAP_CHARS, out
