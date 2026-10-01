"""The ruled head-extraction table (DECISION_LOG R5)."""
import pytest

from sa import heads

# One input per declared extractor, shaped as Claude Code writes it.
REAL_INPUTS = {
    "Bash": {"command": "pytest -q tests/", "description": "Run tests"},
    "Read": {"file_path": "/x/y/notes.md"},
    "Edit": {"file_path": "/x/a.py", "old_string": "a", "new_string": "b"},
    "Write": {"file_path": "/x/b.py", "content": ""},
}

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
    ("Glob", {"pattern": "**/*.py", "path": "/x"}, None),
    ("Grep", {"pattern": "def ", "path": "/x", "glob": "*.py"}, None),
    ("NotebookEdit", {"notebook_path": "/x/a.ipynb", "new_source": ""}, None),
    ("WebFetch", {"url": "https://example.invalid/a.html"}, None),
    ("Agent", {"prompt": "do it"}, None),
    ("Bash", "not-a-dict", None),
]


@pytest.mark.parametrize("tool,tool_input,expected", CASES)
def test_head_of(tool, tool_input, expected):
    assert heads.head_of(tool, tool_input) == expected


def test_every_declared_extractor_reads_its_real_input_shape():
    assert set(REAL_INPUTS) == set(heads.EXTRACTORS)
    found = {tool: heads.head_of(tool, tool_input) for tool, tool_input in REAL_INPUTS.items()}
    assert found == {"Bash": "pytest", "Read": "md", "Edit": "py", "Write": "py"}
