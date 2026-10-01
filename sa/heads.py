"""The ``head`` dimension: ``<tool>:<summary>``, a low-cardinality summary of
a tool call's input that carries its tool so a table over heads needs no
second column. Ruled (DECISION_LOG R5, R5-BASENAME, R5-BUILTINS): a head is
never a full command line and never a file path. For Bash the summary is
the basename of the first COMMAND word (a path-shaped word is classed by
its basename, so ``/usr/bin/env`` is a wrapper), the first ``shlex`` token (quotes
resolved; a run of ``();|&`` is a separator of its own; a newline is ``;``;
a ``$(...)`` substitution, however nested, or a ``$((...))`` arithmetic
expansion is one argument) once what can produce no tokens is skipped: a
leading assignment, a separator, a bare ``RESERVED`` word, a ``KEYWORDS``
word through the opener(s) of its body, a ``WRAPPERS`` word with its
options (a ``VALUED`` one with its word) and ``OPERANDS``, a ``TESTS``
bracket through its closer, and a ``BUILTINS`` or ``SILENT`` word with its
arguments up to the next separator. For the tools
whose input carries ``file_path`` the summary is the file extension. A
summary is kept only if it matches ``HEAD_SHAPE`` (no slash, no leading
``-``), else ``other``. A quote shlex cannot close ends the words there:
the head stands when it comes before (an apostrophe in an argument or a
heredoc body), else ``other``. So ``other`` is one bucket, not three: a
rejected shape, a command of skipped words alone (``cd /x``, ``rm -rf x``,
the empty command) and a quote unclosed before any command word. Known
gap: a wrapper option that takes a value but is not in ``VALUED`` leaves
its value as the head; the fix is one more entry, never a looser shape.
Every other tool has no head: Glob and
Grep take a pattern and a directory, and NotebookEdit's extension is always
the same. The cases are ``tests/test_heads.py``.
"""
import re
import shlex
from pathlib import PurePosixPath
from typing import Callable, List, Optional

HEAD_SHAPE = re.compile(r"^[A-Za-z0-9_.+][A-Za-z0-9_.+-]{0,31}$")  # never an option
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_SUBSTITUTION = re.compile(r"\$\(\(.*?\)\)|\$\([^()]*\)")  # ``$((expr))`` to its ``))``, innermost ``$(cmd)``
_PUNCTUATION = set("();|&")  # a word of these alone (``&&``, ``;;``, ``)``…) ends a command
RESERVED = ("if", "elif", "while", "until",  # open a condition: a command list
            "do", "then", "else", "done", "fi", "esac", "}")  # bare, ends a command like ``;``
# The command is in the body a keyword opens, past each opener in turn:
# ``case``'s past ``in`` and then past the first pattern's ``)``.
KEYWORDS = {"for": ("do",), "case": ("in", ")")}
WRAPPERS = ("{", "!", "time", "sudo", "env", "nohup", "xargs", "timeout")  # run the word after them
VALUED = {  # a wrapper's options that take the next word; any other option is skipped alone
    "timeout": ("-s", "--signal", "-k", "--kill-after"),
    "sudo": ("-u", "--user", "-g", "--group", "-h", "--host", "-p", "--prompt", "-C",
             "--close-from", "-D", "--chdir", "-r", "--role", "-t", "--type", "-U", "--other-user"),
    "env": ("-u", "--unset", "-C", "--chdir", "-S", "--split-string"),
    "time": ("-f", "--format", "-o", "--output"),
    "xargs": ("-a", "--arg-file", "-d", "--delimiter", "-E", "--eof", "-I", "-L", "--max-lines",
              "-n", "--max-args", "-P", "--max-procs", "-s", "--max-chars"),
}
OPERANDS = {"timeout": 1}  # positional words a wrapper takes before the command
TESTS = {"[": "]", "[[": "]]"}  # a condition, closed by its bracket; no output
# Negligible output, skipped by ruling R5-BUILTINS (before HEAD_SHAPE could reject ``:``).
BUILTINS = ("cd", "echo", "printf", "read", "true", "false", "test", ":", "set", "export",
            "unset", "shift", "exit", "source", ".")
SILENT = ("mkdir", "touch", "mv", "cp", "rm", "chmod", "sleep", "ln")  # common commands that print nothing
NO_OUTPUT = BUILTINS + SILENT
OTHER = "other"


def _guard(head: str) -> str:
    return head if HEAD_SHAPE.match(head) else OTHER


def _separator(word: str) -> bool:
    return bool(word) and set(word) <= _PUNCTUATION


def _past(words: List[str], stop: Callable[[str], bool]) -> int:
    """The index just past the first word ``stop`` accepts, or past the end."""
    return next((i for i, word in enumerate(words) if stop(word)), len(words)) + 1


def _words(command: str) -> List[str]:
    command = command.replace("\n", ";")
    while _SUBSTITUTION.search(command):
        command = _SUBSTITUTION.sub("$_", command)
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""  # a comment is not modelled: ``#`` is a word
    words: List[str] = []
    try:
        for word in lexer:
            words.append(word)
    except ValueError:  # an unclosed quote: the words before it stand
        pass
    return words


def bash_head(tool_input: dict) -> str:
    words = _words(str(tool_input.get("command", "")))
    while words:
        word = words[0].rpartition("/")[2]  # R5-BASENAME: every class is tested against the basename
        if _ASSIGNMENT.match(words[0]) or word in RESERVED or _separator(word):  # ``A=/x`` is one word
            del words[0]
        elif word in WRAPPERS:
            del words[0]
            while words and words[0].startswith("-"):
                del words[:2 if words[0] in VALUED.get(word, ()) else 1]
            del words[:OPERANDS.get(word, 0)]
        elif word in KEYWORDS:
            for opener in KEYWORDS[word]:
                del words[:_past(words, lambda w: w == opener)]
        elif word in TESTS:
            del words[:_past(words, lambda w: w == TESTS[word])]
        elif word in NO_OUTPUT:
            del words[:_past(words, _separator)]
        else:
            return _guard(word)
    return OTHER


def extension_head(tool_input: dict) -> str:
    suffix = PurePosixPath(str(tool_input.get("file_path", ""))).suffix
    return _guard(suffix[1:]) if suffix else OTHER


EXTRACTORS = {
    "Bash": bash_head,
    "Read": extension_head,
    "Edit": extension_head,
    "Write": extension_head,
}


def head_of(tool: str, tool_input: dict) -> Optional[str]:
    """The head for one tool call, or ``None`` for a tool with no head."""
    extract = EXTRACTORS.get(tool)
    if extract is None or not isinstance(tool_input, dict):
        return None
    return "%s:%s" % (tool, extract(tool_input))
