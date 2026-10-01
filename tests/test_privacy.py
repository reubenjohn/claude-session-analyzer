"""The privacy gate: no tracked file may carry private material.

Transcripts under ~/.claude/projects hold real paths, real session ids and
real conversation text. The tool reads them; the repo must never contain
them. This test is the gate, so it runs in CI, in the pre-push hook, and
in every agent session alike.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERNS = {
    # A real home directory: a username after /home/ or /Users/. The doc
    # placeholders "/home/..." and "/home/<name>" do not match.
    "home path": re.compile(r"/(?:home|Users)/[A-Za-z][A-Za-z0-9_-]*/"),
    # A session or agent id as Claude Code writes them.
    "uuid": re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b"
    ),
}


def tracked_text_files():
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    ).stdout
    own = str(Path(__file__).relative_to(ROOT))
    for name in out.decode().split("\0"):
        # This file's vacuity guard holds the very shapes it hunts for.
        if name and name != own and not name.startswith("LICENSE"):
            path = ROOT / name
            try:
                yield name, path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, FileNotFoundError):
                continue


def test_patterns_catch_their_targets():
    """Vacuity guard: each pattern matches the shape it exists to catch."""
    assert PATTERNS["home path"].search("/home/someone/.claude/x")
    assert PATTERNS["uuid"].search("12345678-1234-4123-8123-123456789abc")
    assert not PATTERNS["home path"].search("/home/<name>/ or /home/...")


def test_no_private_material_in_tracked_files():
    hits = [
        (name, label)
        for name, text in tracked_text_files()
        for label, pattern in PATTERNS.items()
        if pattern.search(text)
    ]
    assert not hits, "private material in tracked files: %r" % hits
