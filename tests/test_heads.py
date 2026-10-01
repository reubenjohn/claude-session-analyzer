"""The ruled head-extraction table (DECISION_LOG R5)."""
import pytest

from sa import heads

CASES = [
    ("Bash", {"command": "pytest -q tests/"}, "pytest"),
    ("Bash", {"command": "FOO=1 cd /x && pytest -q"}, "pytest"),
    ("Bash", {"command": "cd /x && A=1 B=2 git status"}, "git"),
    ("Bash", {"command": "cd /x; ls"}, "ls"),
    ("Bash", {"command": "cd /x || exit 1; make"}, "exit"),
    ("Bash", {"command": "cd /x"}, "cd"),
    ("Bash", {"command": "/usr/bin/python3 -V"}, "other"),
    ("Bash", {"command": "./run.sh"}, "other"),
    ("Bash", {"command": "x" * 33}, "other"),
    ("Bash", {"command": ""}, "other"),
    ("Bash", {}, "other"),
    ("Read", {"file_path": "/x/y/notes.md"}, "md"),
    ("Edit", {"file_path": "/x/archive.tar.gz"}, "gz"),
    ("Write", {"file_path": "/x/Makefile"}, "other"),
    ("Grep", {"pattern": "def ", "path": "/x"}, "other"),
    ("WebFetch", {"url": "https://example.invalid/a.html"}, None),
    ("Agent", {"prompt": "do it"}, None),
    ("Bash", "not-a-dict", None),
]


@pytest.mark.parametrize("tool,tool_input,expected", CASES)
def test_head_of(tool, tool_input, expected):
    assert heads.head_of(tool, tool_input) == expected


def test_every_declared_extractor_yields_a_head():
    sample = {"command": "pytest -q", "file_path": "/x/a.py"}
    assert heads.EXTRACTORS
    assert {heads.head_of(tool, sample) for tool in heads.EXTRACTORS} == {"pytest", "py"}
