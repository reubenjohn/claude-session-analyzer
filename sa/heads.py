"""The ``head`` dimension: ``<tool>:<summary>``, a low-cardinality summary of
a tool call's input that carries its tool so a table over heads needs no
second column.

Ruled (DECISION_LOG R5, R5-BASENAME, R5-BUILTINS): a head is never a full
command line and never a file path. For Bash the summary is the first
COMMAND word that can produce the tokens, so what precedes one is skipped:
leading ``VAR=value`` assignments; a ``KEYWORDS`` word with everything
through the word(s) that open its body (``for f in x; do cmd`` is ``cmd``,
not ``for``; ``case $x in a) cmd`` is ``cmd``); a ``WRAPPERS`` word with
its ``-``-prefixed options, each skipped alone unless ``VALUED`` declares
it takes the next word, and its ``OPERANDS`` (``timeout``'s duration); a
``TESTS`` bracket through its closer; a bare separator; and an output-less
``BUILTINS`` word with its arguments up to the next separator (``echo "==
$f"; cat $f`` is ``cat``, ``cd -P /x && make`` is ``make``), so a command
that is only builtins (``cd /x``, ``echo done``) is ``other``. Separators
are ``&&``, ``||``, ``;``, ``|``, a newline and either parenthesis, each
padded into a word of its own, and the bare ``RESERVED`` words that open,
close or switch a body (``done``, ``fi``, ``else``, ``}``) or background a
command (``&``), so ``if [ -f x ]; then echo hi; fi; make`` is ``make``,
never ``fi``.
A path-shaped command word is its basename (``./check.sh`` is ``check.sh``,
``/usr/bin/python3`` is ``python3``). For the tools whose input carries
``file_path`` the summary is the file extension. A summary is kept only if
it matches ``HEAD_SHAPE``, which admits no slash and no leading ``-``, so a
directory (``scripts/``) and a stray option (``-n1``) degrade to ``other``.
Known gap: a wrapper option that takes a value but is not in ``VALUED`` is
skipped alone and its value becomes the head (``sudo -C 3 make`` is ``3``);
the fix is one more entry in ``VALUED``, never a looser shape. Every other
tool has no head: Glob and Grep take a pattern and a directory, and
NotebookEdit's extension is always the same, so none of them would carry
information.
"""
import re
from pathlib import PurePosixPath
from typing import List, Optional, Tuple

HEAD_SHAPE = re.compile(r"^[A-Za-z0-9_.+][A-Za-z0-9_.+-]{0,31}$")  # never an option
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_SEPARATORS = ("&&", "||", ";", "|", "(", ")")  # ``||`` before ``|``: the regex tries them in order
_SEPARATOR = re.compile("(%s)" % "|".join(map(re.escape, _SEPARATORS)))  # padded into its own word
RESERVED = ("do", "then", "else", "done", "fi", "esac", "}", "&")  # bare, ends a command like ``;``
_ENDS = _SEPARATORS + RESERVED
# The command is in the body a keyword opens, past each opener in turn:
# ``case``'s past ``in`` and then past the first pattern's ``)``.
KEYWORDS = {"for": ("do",), "while": ("do",), "until": ("do",), "if": ("then",),
            "elif": ("then",), "case": ("in", ")")}
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
BUILTINS = ("cd", "echo", "printf", "true", "false", "set", "export", "unset", "shift", "exit",
            "source", ".")  # no output
OTHER = "other"


def _guard(head: str) -> str:
    return head if HEAD_SHAPE.match(head) else OTHER


def _past(words: List[str], stop: Tuple[str, ...]) -> int:
    """The index just past the first ``stop`` word, or past the end."""
    return next((i for i, word in enumerate(words) if word in stop), len(words)) + 1


def bash_head(tool_input: dict) -> str:
    command = str(tool_input.get("command", "")).replace("\n", ";")  # a newline ends a command
    words = _SEPARATOR.sub(r" \1 ", command).split()
    while words:
        if _ASSIGNMENT.match(words[0]) or words[0] in _ENDS:
            del words[0]
        elif words[0] in WRAPPERS:
            wrapper = words.pop(0)
            while words and words[0].startswith("-"):
                del words[:2 if words[0] in VALUED.get(wrapper, ()) else 1]
            del words[:OPERANDS.get(wrapper, 0)]
        elif words[0] in KEYWORDS:
            for opener in KEYWORDS[words[0]]:
                del words[:_past(words, (opener,))]
        elif words[0] in TESTS:
            del words[:_past(words, (TESTS[words[0]],))]
        elif words[0] in BUILTINS:
            del words[:_past(words, _ENDS)]
        else:
            break
    return _guard(words[0].rpartition("/")[2]) if words else OTHER  # R5-BASENAME: the basename


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
