"""Terminal styling, the one place an escape code is written.

A report line is a ``str``; one that styles is a ``Line``, a str that also
names its ``role`` (and, for a table row, its share and the spans of its
figures). Rendering never sees
an escape code: ``Painter.paint`` adds them only when ``enabled`` says so,
and removing them gives back the plain line byte for byte, so the plain
output is the contract and styling never carries meaning alone.

The palette is the basic 16 ANSI colours and intensities, legible on a
dark and a light background: bold for the answer and a table's total,
underline for a table's header (a rule under it), dim for
the scope and the key (captions), italic for the rows that are no one
value (``unassigned``, ``+N more rows``, a signed row). A regular row's figures
are a heatmap by its share of the table's base: a log-scale gradient,
green to amber to red (``rgb``), in 24-bit or the 256-colour cube as the
terminal allows (``depth``), else red from ``HOT``, yellow from ``WARM``,
green below; brightness repeats it for a colour-blind
reader (bold from ``HOT``, the row dimmed under ``COLD``). Red, yellow and
green mean a share and nothing else: the checks are bold on failure only,
their ``✓``/``✗`` saying the rest. Each of the top two tools gets one
hue outside the heatmap's and the cyan of a command the key names, kept wherever its name prints: a table label,
the ``Bash`` of ``Bash:sed``, the headline's walk."""
import math
import os
import re
from typing import Dict, Optional, Sequence, Tuple

from .glossary import MARKER, PROG

# Roles a line can carry; ROW is a table row with a share.
HEADLINE, HEADER, TOTAL, SCOPE, KEY, GOOD, BAD, ROW, OTHER, HINT = (
    "headline", "header", "total", "scope", "key", "good", "bad", "row", "other", "hint")

# SGR (on, off): the off code ends only that attribute, so styles nest.
BOLD, FAINT, ITALIC, UNDERLINE = ("1", "22"), ("2", "22"), ("3", "23"), ("4", "24")
RED, YELLOW, GREEN = "31", "33", "32"
ROLES = {HEADLINE: BOLD, HEADER: UNDERLINE, TOTAL: BOLD, SCOPE: FAINT, KEY: FAINT, HINT: FAINT, BAD: BOLD,
         OTHER: ITALIC}
# Tool hues, by rank: magenta, bright blue (plain blue is too dark on a dark
# background); never the heatmap's, nor cyan, a runnable command's. A tool
# past the second prints plain.
TOOL_HUES = ("35", "94")
COMMAND = ("36", "39")  # cyan: a runnable command
HOT, WARM, COLD = 0.25, 0.05, 0.01  # share thresholds: red and bold, yellow, the row dimmed
Span = Tuple[int, int]

ALWAYS, NEVER, AUTO = "always", "never", "auto"


class Line(str):
    """A line that prints in its role's style when colour is on."""
    role = ""
    share: Optional[float] = None
    cells: Tuple[Span, ...] = ()  # the figures the heatmap colours
    values: Tuple[Span, ...] = ()  # data values (a project, a tool): never a glossary term


def tag(text: str, role: str, share: Optional[float] = None, cells: Sequence[Span] = (),
        values: Sequence[Span] = ()) -> str:
    line = Line(text)
    line.role, line.share, line.cells, line.values = role, share, tuple(cells), tuple(values)
    return line


def retag(line: str, text: str, values: Sequence[Span] = None) -> str:
    """``text`` in ``line``'s role, share and cells, and its value spans
    unless ``values`` replaces them."""
    return tag(text, getattr(line, "role", ""), getattr(line, "share", None), getattr(line, "cells", ()),
               getattr(line, "values", ()) if values is None else values)


# The gradient: green at FLOOR or less, amber at their geometric middle (about
# 7%), red at CEILING or more, on a log scale, as shares are skewed: 1%, 5%
# and 25% sit at 0, 0.41 and 0.82 of it. Mid-saturation stops read on a
# dark and a light background (a pure yellow on white would not).
FLOOR, CEILING = 0.01, 0.5
STOPS = ((40, 160, 40), (205, 150, 0), (215, 20, 0))
TRUE, CUBE, BASIC = 24, 256, 16  # colour depths


def depth(environ: Dict[str, str] = None) -> int:
    """24-bit when ``COLORTERM`` says so, the 256-colour cube when ``TERM``
    does, else the 16 basic colours."""
    env = os.environ if environ is None else environ
    if env.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
        return TRUE
    return CUBE if "256" in env.get("TERM", "") else BASIC


def rgb(share: float) -> Tuple[int, int, int]:
    """The gradient's colour for a share, on the log scale."""
    span = math.log(CEILING / FLOOR)
    t = min(1.0, max(0.0, math.log(max(share, FLOOR) / FLOOR) / span)) * (len(STOPS) - 1)
    i = min(int(t), len(STOPS) - 2)
    a, b = STOPS[i], STOPS[i + 1]
    return tuple(int(round(x + (y - x) * (t - i))) for x, y in zip(a, b))


def heat(share: float, bits: int = BASIC) -> Tuple[str, str]:
    """A share's SGR (on, off): the gradient in 24-bit or the 256-colour
    cube, or three basic bands (red from ``HOT``, yellow from ``WARM``,
    green below); bold from ``HOT`` at every depth."""
    if bits == TRUE:
        hue = "38;2;%d;%d;%d" % rgb(share)
    elif bits == CUBE:
        hue = "38;5;%d" % (16 + sum(int(round(c / 255 * 5)) * k for c, k in zip(rgb(share), (36, 6, 1))))
    else:
        hue = RED if share >= HOT else YELLOW if share >= WARM else GREEN
    return (hue + ";" + BOLD[0], "39;22") if share >= HOT else (hue, "39")


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

    def __init__(self, tools: Sequence[str] = (), bits: int = BASIC):
        self.hues, self.bits = dict(zip(tools, TOOL_HUES)), bits
        names = "|".join(re.escape(t) for t in sorted(self.hues, key=len, reverse=True))
        # A tool's name standing alone or before ``:``, never inside another word or path.
        self.tool = re.compile(r"(?<![\w./~-])(%s)(?=$|[:\s,)])" % names) if names else None

    def paint(self, line: str) -> str:
        role, share = getattr(line, "role", ""), getattr(line, "share", None)
        text = str(line)
        if role == ROW and share is not None:
            for start, end in sorted(getattr(line, "cells", ()), reverse=True):  # right first: offsets hold
                pad = len(text[start:end]) - len(text[start:end].lstrip())
                text = text[:start + pad] + sgr(text[start + pad:end], heat(share, self.bits)) + text[end:]
        text = re.sub(r"(\w+)(?=%s)" % re.escape(MARKER), lambda m: sgr(m.group(1), UNDERLINE), text)
        if role == KEY:
            text = re.sub(r"%s\b.*$" % re.escape(PROG), lambda m: sgr(m.group(0), COMMAND), text)
        if role == HINT:  # the command to run
            text = re.sub(r"%s\b.*$" % re.escape(PROG), lambda m: sgr(m.group(0), COMMAND), text)
        if self.tool and role != SCOPE:
            text = self.tool.sub(lambda m: sgr(m.group(1), (self.hues[m.group(1)], "39")), text)
        if role == ROW and share is not None:
            if share < COLD:
                text = sgr(text, FAINT)
        elif role in ROLES:
            text = sgr(text, ROLES[role])
        return text
