"""Print the screens an audit reads, in one pass: each invocation as
``===== $ python3 -m sa ARGS``, its output (stdout, then stderr) and
``[exit N]``. The list covers the front door, help, both default screens, a
pin, a table, the facts, ``-v`` and three refusals.

    python3 scripts/screens.py                  # ~/.claude/projects, the last 7 days
    python3 scripts/screens.py --root DIR       # any transcripts directory
    python3 scripts/screens.py --since all      # passed through, like --root

Stdlib only; ``tests/test_screens_script.py`` runs it on the fixture."""
import subprocess
import sys
from pathlib import Path
from typing import List, Sequence

REPO = Path(__file__).resolve().parents[1]
# Each screen's words; the front door and help take no --root.
SCREENS = ([], ["-h"])
READS = (["context"], ["spend"], ["context", "tool=Bash"], ["context", "by", "tool"],
         ["context", "by", "change", "cause=ambiguous"], ["context", "-v"], ["spend", "-v"],
         ["contxt"], ["context", "tool=Bsh"], ["context", "by", "tol"])


def screen(words: Sequence[str]) -> List[str]:
    done = subprocess.run([sys.executable, "-m", "sa"] + list(words), cwd=str(REPO),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    out = (done.stdout + done.stderr).rstrip("\n")
    return ["===== $ python3 -m sa " + " ".join(words), out, "[exit %d]" % done.returncode]


def main(argv: Sequence[str]) -> int:
    passed = list(argv)  # --root DIR, --since N: every reading screen gets them
    lines = []
    for words in SCREENS:
        lines += screen(words)
    for words in READS:
        lines += screen(list(words) + passed)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
