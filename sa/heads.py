"""The ``head`` dimension: ``<tool>:<summary>``, a low-cardinality summary of
a tool call's input that carries its tool so a table over heads needs no
second column.

Ruled (DECISION_LOG R5, R5-BASENAME): a head is never a full command line
and never a file path. For Bash the summary is the first COMMAND word, so
what precedes one is skipped: leading ``VAR=value`` assignments and ``cd
<dir>`` prefixes ended by ``&&``, ``;`` or ``||``; a ``KEYWORDS`` word with
everything through the ``BODY_OPENERS`` word that opens its body (``for f in
x; do cmd`` is ``cmd``, not ``for``); a bare ``WRAPPERS`` word; and
``timeout`` with its duration. A path-shaped command word is its basename
(``./check.sh`` is ``check.sh``, ``/usr/bin/python3`` is ``python3``). For
the tools whose input carries ``file_path`` the summary is the file
extension. A summary is kept only if it matches ``HEAD_SHAPE``, which admits
no slash, so a directory (``scripts/``) degrades to ``other``. Every other
tool has no head: Glob and Grep take a pattern and a directory, and
NotebookEdit's extension is always the same, so none of them would carry
information.
"""
import re
from pathlib import PurePosixPath
from typing import Optional

HEAD_SHAPE = re.compile(r"^[A-Za-z0-9_.+-]{1,32}$")
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_SEPARATORS = ("&&", ";", "||")
KEYWORDS = ("for", "while", "until", "if", "elif")  # the command is in the body they open
BODY_OPENERS = ("do", "then")
WRAPPERS = ("{", "(", "!", "time", "sudo", "env", "nohup", "xargs")  # run the word after them
OTHER = "other"


def _guard(head: str) -> str:
    return head if HEAD_SHAPE.match(head) else OTHER


def bash_head(tool_input: dict) -> str:
    command = str(tool_input.get("command", ""))
    for separator in _SEPARATORS:
        command = command.replace(separator, " %s " % separator)
    words = command.split()
    while words:
        if _ASSIGNMENT.match(words[0]) or words[0] in WRAPPERS:
            del words[0]
        elif words[0] == "timeout":
            del words[:2]
        elif words[0] == "cd" and len(words) > 2 and words[2] in _SEPARATORS:
            del words[:3]
        elif words[0] in KEYWORDS:
            opener = next((i for i, word in enumerate(words) if word in BODY_OPENERS), len(words))
            del words[:opener + 1]
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
