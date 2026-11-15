"""Terminal styling, the one place an escape code is written.

A report line is a ``str``; one that styles is a ``Line``, a str that also
names its ``role`` (and, for a table row, its share). Rendering never sees
an escape code: ``Painter.paint`` adds them only when ``enabled`` says so,
and removing them gives back the plain line byte for byte, so the plain
output is the contract and styling never carries meaning alone.

The palette is the basic 16 ANSI colours and intensities, legible on a
dark and a light background: bold for the answer and a table's total,
underline for a table's header (a rule under it), dim for
the scope and the key (captions), italic for the rows that are no one
value (``∅``, ``+N more rows``, a signed row), green and red only on the
``✓``/``✗`` checks, which the glyphs already say. A share is a heatmap in
intensity, not hue (colour-blind safe): a row of a quarter or more of its
base has its share bold, one under 1% is dimmed. Each of the top three
tools gets one hue, kept wherever its name prints: a table label, the
``Bash`` of ``Bash:sed``, the headline's walk."""
import os
import re
from typing import Dict, Optional, Sequence

# Roles a line can carry; ROW is a table row with a share.
HEADLINE, HEADER, TOTAL, SCOPE, KEY, GOOD, BAD, ROW, OTHER = (
    "headline", "header", "total", "scope", "key", "good", "bad", "row", "other")

# SGR (on, off): the off code ends only that attribute, so styles nest.
BOLD, FAINT, ITALIC, UNDERLINE = ("1", "22"), ("2", "22"), ("3", "23"), ("4", "24")
GREEN, RED = ("32", "39"), ("31", "39")
ROLES = {HEADLINE: BOLD, HEADER: UNDERLINE, TOTAL: BOLD, SCOPE: FAINT, KEY: FAINT, GOOD: GREEN, BAD: RED,
         OTHER: ITALIC}
# Tool hues, by rank: cyan, magenta, yellow; never green or red (the checks'), nor
# blue, too dark on a dark background. A tool past the third prints plain.
TOOL_HUES = ("36", "35", "33")
MARKS = {"✓": GREEN, "✗": RED}
HOT, COLD = 0.25, 0.01  # a share at or over HOT prints bold, under COLD the row dims

ALWAYS, NEVER, AUTO = "always", "never", "auto"


class Line(str):
    """A line that prints in its role's style when colour is on."""
    role = ""
    share: Optional[float] = None


def tag(text: str, role: str, share: Optional[float] = None) -> str:
    line = Line(text)
    line.role, line.share = role, share
    return line


def enabled(choice: str, isatty: bool, environ: Dict[str, str] = None) -> bool:
    """``--color``: always, never, or auto: off when ``NO_COLOR`` is set
    non-empty, on when ``FORCE_COLOR`` is (other than ``0``), else when
    stdout is a TTY."""
    env = os.environ if environ is None else environ
    if choice != AUTO:
        return choice == ALWAYS
    if env.get("NO_COLOR"):
        return False
    if env.get("FORCE_COLOR", "0") not in ("", "0"):
        return True
    return isatty


def sgr(text: str, style) -> str:
    return "\033[%sm%s\033[%sm" % (style[0], text, style[1])


ESCAPE = re.compile(r"\033\[[0-9;]*m")


def plain(text: str) -> str:
    return ESCAPE.sub("", text)


class Painter:
    """Paints lines: ``tools`` in rank order, the first ``len(TOOL_HUES)``
    each its own hue for the whole report."""

    def __init__(self, tools: Sequence[str] = ()):
        self.hues = dict(zip(tools, TOOL_HUES))
        names = "|".join(re.escape(t) for t in sorted(self.hues, key=len, reverse=True))
        # A tool's name standing alone or before ``:``, never inside another word or path.
        self.tool = re.compile(r"(?<![\w./~-])(%s)(?=$|[:\s,)])" % names) if names else None

    def paint(self, line: str) -> str:
        role, share = getattr(line, "role", ""), getattr(line, "share", None)
        text = str(line)
        if self.tool and role != SCOPE:
            text = self.tool.sub(lambda m: sgr(m.group(1), (self.hues[m.group(1)], "39")), text)
        if role not in (GOOD, BAD):  # a whole line in green or red already marks it
            for mark, style in MARKS.items():
                text = text.replace(mark, sgr(mark, style))
        if role == ROW and share is not None:
            if share >= HOT:
                text = re.sub(r"(\S+%)$", lambda m: sgr(m.group(1), BOLD), text)
            elif share < COLD:
                text = sgr(text, FAINT)
        elif role in ROLES:
            text = sgr(text, ROLES[role])
        return text
