"""The ruled head-extraction table (DECISION_LOG R5, R5-BASENAME):
``<tool>:<summary>``, the summary of a Bash command its first command word."""
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
    ("Bash", {"command": "pytest -q tests/"}, "Bash:pytest"),
    ("Bash", {"command": "FOO=1 cd /x && pytest -q"}, "Bash:pytest"),
    ("Bash", {"command": "cd /x && A=1 B=2 git status"}, "Bash:git"),
    ("Bash", {"command": "cd /x; ls"}, "Bash:ls"),
    ("Bash", {"command": "cd /x&&ls"}, "Bash:ls"),
    ("Bash", {"command": "cd /x||true"}, "Bash:true"),
    ("Bash", {"command": "cd /x || exit 1; make"}, "Bash:exit"),
    ("Bash", {"command": "cd /x"}, "Bash:cd"),
    # Keywords: the command is in the body they open.
    ("Bash", {"command": "for f in a b; do cmd $f; done"}, "Bash:cmd"),
    ("Bash", {"command": "while read -r x; do cmd; done"}, "Bash:cmd"),
    ("Bash", {"command": "until test -f x; do sleep 1; done"}, "Bash:sleep"),
    ("Bash", {"command": "if [ -f x ]; then cmd; fi"}, "Bash:cmd"),
    ("Bash", {"command": "elif [ -f x ]; then cmd; fi"}, "Bash:cmd"),
    ("Bash", {"command": "for f in x; do if [ -f $f ]; then cmd; fi; done"}, "Bash:cmd"),
    ("Bash", {"command": "cd /x && for f in *; do cmd; done"}, "Bash:cmd"),
    ("Bash", {"command": "for f in a b"}, "Bash:other"),  # no body, no command
    # Wrappers: bare prefixes that run the word after them.
    ("Bash", {"command": "{ cmd; }"}, "Bash:cmd"),
    ("Bash", {"command": "( cmd )"}, "Bash:cmd"),
    ("Bash", {"command": "! cmd"}, "Bash:cmd"),
    ("Bash", {"command": "time cmd"}, "Bash:cmd"),
    ("Bash", {"command": "sudo cmd"}, "Bash:cmd"),
    ("Bash", {"command": "env FOO=1 cmd"}, "Bash:cmd"),
    ("Bash", {"command": "nohup cmd &"}, "Bash:cmd"),
    ("Bash", {"command": "xargs cmd"}, "Bash:cmd"),
    ("Bash", {"command": "timeout 30s cmd"}, "Bash:cmd"),
    ("Bash", {"command": "sudo timeout 30 env cmd"}, "Bash:cmd"),
    ("Bash", {"command": "timeout 30"}, "Bash:other"),
    # R5-BASENAME: a path-shaped command word is its basename, never a directory.
    ("Bash", {"command": "./check.sh"}, "Bash:check.sh"),
    ("Bash", {"command": "/usr/bin/python3 -V"}, "Bash:python3"),
    ("Bash", {"command": "cd /x && ./check.sh"}, "Bash:check.sh"),
    ("Bash", {"command": "scripts/"}, "Bash:other"),
    ("Bash", {"command": "./" + "x" * 33}, "Bash:other"),
    ("Bash", {"command": "x" * 33}, "Bash:other"),
    ("Bash", {"command": ""}, "Bash:other"),
    ("Bash", {}, "Bash:other"),
    ("Read", {"file_path": "/x/y/notes.md"}, "Read:md"),
    ("Edit", {"file_path": "/x/archive.tar.gz"}, "Edit:gz"),
    ("Write", {"file_path": "/x/Makefile"}, "Write:other"),
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


def test_every_declared_keyword_and_wrapper_opens_a_case():
    firsts = {tool_input["command"].split()[0] for tool, tool_input, _ in CASES
              if tool == "Bash" and isinstance(tool_input, dict) and tool_input.get("command")}
    assert set(heads.KEYWORDS + heads.WRAPPERS + ("timeout",)) <= firsts


def test_every_declared_extractor_reads_its_real_input_shape():
    assert set(REAL_INPUTS) == set(heads.EXTRACTORS)
    found = {tool: heads.head_of(tool, tool_input) for tool, tool_input in REAL_INPUTS.items()}
    assert found == {"Bash": "Bash:pytest", "Read": "Read:md", "Edit": "Edit:py",
                     "Write": "Write:py"}
