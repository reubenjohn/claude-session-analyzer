"""One dated snapshot of the live local corpus: every local figure the
``sa/`` docstrings cite, counted by ``sa.sweep``.

The corpus under ``~/.claude/projects`` changes with every session, so the
figures are a snapshot of one machine on one day, not reproducible
elsewhere; a docstring cites them by date and this script. Prints aggregate
counts only: no transcript text, no ids, no paths.
"""
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sa import corpus, sweep  # noqa: E402


def main() -> None:
    lines = sweep.report(corpus.load(corpus.default_root()))
    print("LOCAL SWEEP %s: %s" % (datetime.date.today(), lines[0]))
    print("\n".join(lines[1:]))


if __name__ == "__main__":
    main()
