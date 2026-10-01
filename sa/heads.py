"""The ``head`` dimension: a low-cardinality summary of a tool call's input.

Ruled (DECISION_LOG R5): a head is never a full command line and never a
file path. For Bash it is the first command word after leading ``VAR=value``
assignments and ``cd <dir>`` prefixes ended by ``&&``, ``;`` or ``||``; for
the file tools it is the file extension. A head is kept only if it matches ``HEAD_SHAPE``, which admits no
slash, so a path-shaped head degrades to ``other``. Every other tool has no
head.
"""
import re
from pathlib import PurePosixPath
from typing import Optional

HEAD_SHAPE = re.compile(r"^[A-Za-z0-9_.+-]{1,32}$")
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_SEPARATORS = ("&&", ";", "||")
OTHER = "other"


def _guard(head):
    # type: (str) -> str
    return head if HEAD_SHAPE.match(head) else OTHER


def bash_head(tool_input):
    # type: (dict) -> str
    words = str(tool_input.get("command", "")).replace(";", " ; ").split()
    while words:
        if _ASSIGNMENT.match(words[0]):
            del words[0]
        elif words[0] == "cd" and len(words) > 2 and words[2] in _SEPARATORS:
            del words[:3]
        else:
            break
    return _guard(words[0]) if words else OTHER


def extension_head(tool_input):
    # type: (dict) -> str
    suffix = PurePosixPath(str(tool_input.get("file_path", ""))).suffix
    return _guard(suffix[1:]) if suffix else OTHER


EXTRACTORS = {
    "Bash": bash_head,
    "Read": extension_head,
    "Edit": extension_head,
    "MultiEdit": extension_head,
    "Write": extension_head,
    "NotebookEdit": extension_head,
    "Glob": extension_head,
    "Grep": extension_head,
}


def head_of(tool, tool_input):
    # type: (str, dict) -> Optional[str]
    """The head for one tool call, or ``None`` for a tool with no head."""
    extract = EXTRACTORS.get(tool)
    if extract is None or not isinstance(tool_input, dict):
        return None
    return extract(tool_input)
