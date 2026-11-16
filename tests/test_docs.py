"""The docs as tested artifacts. Each doc is within the cap AGENTS.md
states, in bytes like the pre-commit size gates (the docs print multi-byte
marks such as ✓ and →, so bytes are the stricter and unambiguous count).
The README and SKILL example blocks are the fixture corpus's live output:
``scripts/resync_examples.py --check`` finds no drift. The same corpus's
default output stays within its cap (D-OUTPUT-CAP)."""
import importlib.util
import os
import re
import shlex
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


# A command the README shows: a code-block line or an inline span (a grammar
# template, with ``[`` or ``|``, is not a command), its ``# comment`` cut.
COMMAND = re.compile(r"^(python3 -m sa\b[^#\n]*)|`(python3 -m sa\b[^`\[|\n]*)`", re.M)


def test_every_readme_command_runs_verbatim_on_the_fixture(tmp_path):
    """Principle 1: what the README names is valid input. Each command runs
    as printed, from outside the repo (the installed package's view), with
    HOME at the fixture corpus: exit 0, some output."""
    spec = importlib.util.spec_from_file_location("resync_examples", str(SCRIPT))
    resync = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(resync)
    home = tmp_path.resolve()
    resync.build(home)
    text = (REPO / "README.md").read_text(encoding="utf-8")
    commands = sorted({(a or b).strip() for a, b in COMMAND.findall(text)})
    assert "python3 -m sa" in commands and len(commands) >= 5, commands  # vacuity guard: the front door too
    env = dict(os.environ, HOME=str(home), PYTHONPATH=str(REPO))
    for command in commands:
        argv = shlex.split(command)[3:]
        done = subprocess.run([sys.executable, "-m", "sa"] + argv, cwd=str(home), env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        assert done.returncode == 0 and done.stdout.strip(), command + "\n" + done.stderr


def test_the_version_lives_in_one_place():
    """``sa.__version__`` is the version: pyproject reads it, the plugin
    manifests match it, ``-h`` prints it, the changelog's latest entry names it."""
    import json
    import sa
    assert re.fullmatch(r"\d+\.\d+\.\d+", sa.__version__)  # vacuity guard: a version is set
    assert 'version = {attr = "sa.__version__"}' in (REPO / "pyproject.toml").read_text(encoding="utf-8")
    plugin = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    market = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert plugin["version"] == sa.__version__ == market["plugins"][0]["version"]
    code, out, _ = fx.run_cli("-h")
    assert code == 0 and out.splitlines()[0].endswith(" v" + sa.__version__)
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(r"^## (\S+)", changelog, re.M).group(1) == sa.__version__
