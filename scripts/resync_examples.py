"""Regenerate the example output in README.md and SKILL.md from live runs
of ``python3 -m sa`` against the fixture corpus, so examples never drift.

A marker line ``<!-- example: ARGS -->`` or ``<!-- example: ARGS | PREFIX -->``
sits right above a fenced block; the block becomes the output of
``python3 -m sa ARGS`` (from the first line starting with PREFIX through the
next blank line, when PREFIX is given). The corpus is
``tests/fixtures.cli_corpus`` under a fixed throwaway HOME at the default root,
its projects named as Claude Code encodes a directory under home, so the
output shows ``~`` as a real run does and holds nothing private.

    python3 scripts/resync_examples.py           # rewrite the docs
    python3 scripts/resync_examples.py --check   # exit 1 if any drifted
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(REPO))
import fixtures  # noqa: E402

# A fixed throwaway HOME, removed before and after: a window's value hashes
# its root-relative file, whose project name encodes HOME, so a random temp
# directory would print a different `window=` on every run.
HOME = Path("/tmp/sa-resync-examples")
DOCS = ("README.md", "skills/session-analyzer/SKILL.md")
MARKER = re.compile(r"^(?P<marker><!-- example: (?P<args>[^|]+?)(?: \| (?P<prefix>.+?))? -->\n)"
                    r"```\n.*?^```\n", re.M | re.S)


def run(home: Path, args: str) -> str:
    env = dict(os.environ, HOME=str(home))
    done = subprocess.run([sys.executable, "-m", "sa"] + args.split(), cwd=str(REPO), env=env,
                          stdout=subprocess.PIPE, universal_newlines=True)
    return done.stdout


def excerpt(out: str, prefix: str) -> str:
    lines = out.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(prefix))
    end = next((i for i in range(start, len(lines)) if not lines[i]), len(lines))
    return "\n".join(lines[start:end]) + "\n"


def resynced(text: str, home: Path) -> str:
    def block(match):
        out = run(home, match.group("args"))
        if match.group("prefix"):
            out = excerpt(out, match.group("prefix"))
        return "%s```\n%s```\n" % (match.group("marker"), out)
    return MARKER.sub(block, text)


def build(home: Path) -> Path:
    """The fixture corpus under ``home`` at the default root, its projects
    named as Claude Code encodes ``~/work/app`` and ``~/work/lib``: output
    run with HOME=home prints ``~`` for both, whatever ``home`` is."""
    encoded = re.sub(r"[^A-Za-z0-9]", "-", str(home))
    return fixtures.cli_corpus(home / ".claude", (encoded + "-work-app", encoded + "-work-lib"))


def main(argv) -> int:
    check = "--check" in argv
    shutil.rmtree(str(HOME), ignore_errors=True)
    try:
        home = HOME
        build(home)
        drifted = []
        for name in DOCS:
            path = REPO / name
            text = path.read_text(encoding="utf-8")
            new = resynced(text, home)
            if new != text:
                drifted.append(name)
                if not check:
                    path.write_text(new, encoding="utf-8")
    finally:
        shutil.rmtree(str(HOME), ignore_errors=True)
    for name in drifted:
        print("%s %s" % ("drifted:" if check else "resynced:", name))
    return 1 if check and drifted else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
