"""``scripts/screens.py``, the audit's capture, runs on the README fixture:
every screen it lists prints under its ``=====`` header with its exit
status, refusals exit 2, and ``--root`` reaches every reading screen."""
import re
import subprocess
import sys

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
