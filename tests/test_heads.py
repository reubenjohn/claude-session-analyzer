"""The ruled head-extraction table (DECISION_LOG R5, R5-BASENAME, R5-BUILTINS):
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
    ("Bash", {"command": "cd /x||ls"}, "Bash:ls"),
    ("Bash", {"command": "cd /x || exit 1; make"}, "Bash:make"),
    ("Bash", {"command": "cd /x"}, "Bash:other"),  # a builtin alone, like `echo done`
    ("Bash", {"command": "cd -P /x && make"}, "Bash:make"),
    ("Bash", {"command": "cd && make"}, "Bash:make"),
    # A newline ends a command like `;`; a parenthesis is a separator too.
    ("Bash", {"command": "cd /x\npytest -q"}, "Bash:pytest"),
    ("Bash", {"command": "echo start\n\npytest"}, "Bash:pytest"),
    ("Bash", {"command": "(cd /x && make)"}, "Bash:make"),
    ("Bash", {"command": "(echo hi) && make"}, "Bash:make"),
    ("Bash", {"command": "; make"}, "Bash:make"),
    # A test bracket is a condition with no output, closed by its own bracket.
    ("Bash", {"command": "[ -f x ] && make"}, "Bash:make"),
    ("Bash", {"command": "[[ -f x ]] || make"}, "Bash:make"),
    ("Bash", {"command": "[ -f x ]"}, "Bash:other"),
    # Keywords: the command is in the body they open.
    ("Bash", {"command": "for f in a b; do cmd $f; done"}, "Bash:cmd"),
    ("Bash", {"command": "for f in x; do if [ -f $f ]; then cmd; fi; done"}, "Bash:cmd"),
    ("Bash", {"command": "cd /x && for f in *; do cmd; done"}, "Bash:cmd"),
    ("Bash", {"command": "for f in a b"}, "Bash:other"),  # no body, no command
    # A condition is a command list: its first command is the head.
    ("Bash", {"command": "if pytest; then echo ok; fi"}, "Bash:pytest"),
    ("Bash", {"command": "while ! make; do sleep 1; done"}, "Bash:make"),
    ("Bash", {"command": "if cmd; then cd x; else make; fi"}, "Bash:cmd"),
    ("Bash", {"command": "while read -r x; do cmd; done"}, "Bash:cmd"),
    ("Bash", {"command": "until test -f x; do make; done"}, "Bash:make"),
    ("Bash", {"command": "if [ -f x ]; then cmd; fi"}, "Bash:cmd"),
    ("Bash", {"command": "elif [ -f x ]; then cmd; fi"}, "Bash:cmd"),
    # RESERVED: a word that closes or switches a body, or a bare `&`, ends a
    # command like `;` and is never itself the head.
    ("Bash", {"command": "for f in a; do echo $f; done"}, "Bash:other"),
    ("Bash", {"command": "if [ -f x ]; then echo hi; fi; make"}, "Bash:make"),
    ("Bash", {"command": "{ echo a; }; make"}, "Bash:make"),
    ("Bash", {"command": "cd x & make"}, "Bash:make"),
    ("Bash", {"command": "case $x in a) cd x;; esac; make"}, "Bash:make"),
    # case: past `in`, then past the first pattern's `)`.
    ("Bash", {"command": "case $x in a) make;; esac"}, "Bash:make"),
    ("Bash", {"command": 'case "$1" in\n  start) ./run.sh ;;\n  *) ls ;;\nesac'}, "Bash:run.sh"),
    ("Bash", {"command": "case $(uname) in Linux) make;; esac"}, "Bash:make"),
    ("Bash", {"command": "case $x in"}, "Bash:other"),
    # A command substitution is one argument: its `(` never separates.
    ("Bash", {"command": 'cd "$(git rev-parse --show-toplevel)" && pytest -q'}, "Bash:pytest"),
    ("Bash", {"command": 'export PATH="$(pwd)/bin:$PATH" && make'}, "Bash:make"),
    ("Bash", {"command": "cd x && echo $(pwd) && make"}, "Bash:make"),
    ("Bash", {"command": 'echo "start $(date)"; make'}, "Bash:make"),
    ("Bash", {"command": "$(which make)"}, "Bash:other"),
    ("Bash", {"command": 'cd "$(a $(b))" && pytest'}, "Bash:pytest"),  # nested: innermost first
    ("Bash", {"command": "cd $(a $(b)) && pytest"}, "Bash:pytest"),
    # An arithmetic expansion is one argument too, whatever parentheses it holds.
    ("Bash", {"command": "echo $((1+2)); make"}, "Bash:make"),
    ("Bash", {"command": "sleep $(( (n+1)*2 )) && make"}, "Bash:make"),
    ("Bash", {"command": "echo $(( $(nproc) - 1 )); make"}, "Bash:make"),
    # Quoting is shlex's: a quoted word is one word whatever it holds, and a
    # builtin's arguments run to the next separator, never to a reserved word.
    ("Bash", {"command": "echo if x; make"}, "Bash:make"),
    ("Bash", {"command": 'echo "if x"; make'}, "Bash:make"),
    ("Bash", {"command": 'echo "a; b"; make'}, "Bash:make"),
    # A quote shlex cannot close ends the words there: the head stands if it came before.
    ("Bash", {"command": "echo 'unclosed; make"}, "Bash:other"),
    ("Bash", {"command": "grep -c it's f"}, "Bash:grep"),
    ("Bash", {"command": "python3 - <<'EOF'\n# don't\nx = 1\nEOF"}, "Bash:python3"),
    ("Bash", {"command": "cd x # to x\nmake"}, "Bash:make"),  # a comment is not modelled: a word
    # R5-BUILTINS: an output-less builtin and its arguments, to the next separator.
    ("Bash", {"command": 'for f in a b; do echo "== $f"; cat "$f"; done'}, "Bash:cat"),
    ("Bash", {"command": "echo hi && pytest"}, "Bash:pytest"),
    ("Bash", {"command": "echo done"}, "Bash:other"),
    ("Bash", {"command": "printf '%s' x | sort"}, "Bash:sort"),
    ("Bash", {"command": "read -r x && make"}, "Bash:make"),
    ("Bash", {"command": "true || make"}, "Bash:make"),
    ("Bash", {"command": "false || false"}, "Bash:other"),
    ("Bash", {"command": "set -euo pipefail; pytest -q"}, "Bash:pytest"),
    ("Bash", {"command": "export FOO=1; cmd"}, "Bash:cmd"),
    ("Bash", {"command": "unset FOO && cmd"}, "Bash:cmd"),
    ("Bash", {"command": "shift 2 && cmd"}, "Bash:cmd"),
    ("Bash", {"command": "cd /x && echo start; ./check.sh"}, "Bash:check.sh"),
    ("Bash", {"command": "source .venv/bin/activate && pytest"}, "Bash:pytest"),
    ("Bash", {"command": ". ./env.sh; pytest"}, "Bash:pytest"),
    ("Bash", {"command": ". ./env.sh"}, "Bash:other"),
    ("Bash", {"command": "test -f x && make"}, "Bash:make"),
    ("Bash", {"command": "test -f x"}, "Bash:other"),
    ("Bash", {"command": ": > f; make"}, "Bash:make"),  # `:` is skipped before HEAD_SHAPE could reject it
    ("Bash", {"command": ":"}, "Bash:other"),
    # R5-BUILTINS extended: a common silent command is skipped the same way.
    ("Bash", {"command": "mkdir -p x && cat > f <<EOF\nhello\nEOF"}, "Bash:cat"),
    ("Bash", {"command": "touch f && make"}, "Bash:make"),
    ("Bash", {"command": "mv a b; make"}, "Bash:make"),
    ("Bash", {"command": "cp a b && make"}, "Bash:make"),
    ("Bash", {"command": "rm -rf build && make"}, "Bash:make"),
    ("Bash", {"command": "chmod +x run.sh && ./run.sh"}, "Bash:run.sh"),
    ("Bash", {"command": "sleep 1; make"}, "Bash:make"),
    ("Bash", {"command": "ln -s a b && make"}, "Bash:make"),
    ("Bash", {"command": "until test -f x; do sleep 1; done"}, "Bash:other"),
    ("Bash", {"command": "rm -rf x"}, "Bash:other"),
    # Wrappers: prefixes that run the word after them and their options.
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
    # A wrapper's options are skipped, a VALUED one with its word; timeout's
    # duration follows its options.
    ("Bash", {"command": "timeout -s KILL 30 make"}, "Bash:make"),
    ("Bash", {"command": "timeout --signal=KILL -k 5 30 make"}, "Bash:make"),
    ("Bash", {"command": "timeout --foreground 30 make"}, "Bash:make"),
    ("Bash", {"command": "timeout -s KILL 30"}, "Bash:other"),
    ("Bash", {"command": "xargs -n1 wc -l"}, "Bash:wc"),
    ("Bash", {"command": "xargs -n 1 -P 4 wc -l"}, "Bash:wc"),
    ("Bash", {"command": "xargs -I {} wc -l {}"}, "Bash:wc"),
    ("Bash", {"command": "sudo -u bob make"}, "Bash:make"),
    ("Bash", {"command": "sudo -E -- make"}, "Bash:make"),
    ("Bash", {"command": "env -i make"}, "Bash:make"),
    ("Bash", {"command": "env -u HOME -i FOO=1 make"}, "Bash:make"),
    ("Bash", {"command": "time -p make"}, "Bash:make"),
    ("Bash", {"command": "time -f %e make"}, "Bash:make"),
    ("Bash", {"command": "sudo -u"}, "Bash:other"),
    ("Bash", {"command": "sudo -R jail make"}, "Bash:jail"),  # known gap: an option not in VALUED
    # HEAD_SHAPE: a leading `-` is an option, never a command.
    ("Bash", {"command": "-n1 wc -l"}, "Bash:other"),
    ("Bash", {"command": "--version"}, "Bash:other"),
    ("Bash", {"command": "exit 0"}, "Bash:other"),
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


def test_every_declared_keyword_wrapper_test_builtin_and_silent_word_opens_a_case():
    firsts = {tool_input["command"].split()[0] for tool, tool_input, _ in CASES
              if tool == "Bash" and isinstance(tool_input, dict) and tool_input.get("command")}
    declared = tuple(heads.KEYWORDS) + heads.WRAPPERS + heads.NO_OUTPUT + tuple(heads.TESTS)
    assert set(declared) <= firsts
    assert set(heads.VALUED) | set(heads.OPERANDS) <= set(heads.WRAPPERS)
    for wrapper, options in heads.VALUED.items():  # some valued option of each has a case
        seconds = {tool_input["command"].split()[1] for tool, tool_input, _ in CASES
                   if tool == "Bash" and isinstance(tool_input, dict)
                   and tool_input.get("command", "").startswith(wrapper + " -")}
        assert seconds & set(options), wrapper


def test_no_expected_head_is_a_reserved_word_and_every_reserved_word_has_a_case():
    commands = [tool_input.get("command", "") for tool, tool_input, _ in CASES
                if tool == "Bash" and isinstance(tool_input, dict)]
    assert set(heads.RESERVED) <= {word for command in commands for word in command.split()}
    expected = {head.partition(":")[2] for tool, _, head in CASES if tool == "Bash" and head}
    assert not expected & set(heads.RESERVED) and "make" in expected  # vacuity guard


def test_every_declared_extractor_reads_its_real_input_shape():
    assert set(REAL_INPUTS) == set(heads.EXTRACTORS)
    found = {tool: heads.head_of(tool, tool_input) for tool, tool_input in REAL_INPUTS.items()}
    assert found == {"Bash": "Bash:pytest", "Read": "Read:md", "Edit": "Edit:py",
                     "Write": "Write:py"}
