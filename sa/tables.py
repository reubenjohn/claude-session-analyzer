"""Table rendering of a selection and the formats every line shares:
numbers, ``~`` for home, and line styles.

A table (UX_PRINCIPLES 2, 3) reads top to bottom as its arithmetic: the
regular rows, the rest folded into ``+N more`` with the command that
prints them all, the ``= 100%`` row its shares are of, then the rows in
no share (the catch-all, labelled by what its facts lack and showing its
parts; the signed shrink), and for the cause table the ``= average call``
they all add up to. Every label prints whole: it pins its row as printed.

A line is a ``str``; one that styles is a ``style.Line`` naming its role,
which ``style`` paints only when the CLI asks for it, so every test
compares plain text."""
import re
import shlex
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import glossary, query, schema, style
from .schema import Fact

WIDTH = 100  # every line's budget (UX_PRINCIPLES)
BASE_LABEL = "= 100%"  # the row every share is of
TOTAL_LABEL = "= average call"  # the row a whole-window cause table closes with: its rows add up to it
OK_MARK, BAD_MARK = "✓", "✗"
HOME_NOTE = "~: your home; a project is its directory, every character but a letter or digit as -"
BASE_NOTE = "shares' base: the rows above, not the %s row"  # beside a base its catch-all is out of


def title(dim: str) -> str:
    """A table's header: ``by tool``, as the command that prints it whole."""
    return "by " + dim

def tilde(path: Path) -> str:
    """A path under home as ``~/...``: output never prints the home directory."""
    home, text = str(Path.home()), str(path)
    return "~" + text[len(home):] if text == home or text.startswith(home + "/") else text


def _encoded_home() -> str:
    """Home as Claude Code encodes it in a project directory name: every
    character but a letter or digit as ``-``."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(Path.home()))


def home(value: str) -> str:
    """A project name or root-relative locator that starts with the encoded
    home directory, that prefix printed as ``~``; ``unhome`` reverses it, so
    a printed label still works as a pin."""
    prefix = _encoded_home()
    return "~" + value[len(prefix):] if value == prefix or value.startswith(prefix + "-") else value


def unhome(value: str) -> str:
    return _encoded_home() + value[1:] if value == "~" or value.startswith("~-") else value


def home_text(text: str) -> str:
    """Free text (a refusal naming present values) with the encoded home
    prefix and the home path printed as ``~``."""
    text = re.sub(re.escape(_encoded_home()) + r"(?![A-Za-z0-9])", "~", text)
    return re.sub(re.escape(str(Path.home())) + r"(?![A-Za-z0-9])", "~", text)


AVG_CALL = glossary.printed(glossary.AVG_CALL)  # a count column that is a mean: never summed


def count(n: int, singular: str, plural: Optional[str] = None) -> str:
    """A count before its noun: ``1 window``, ``1,364 windows``."""
    return "%s %s" % (format(n, ",d"), singular if n == 1 else plural or singular + "s")


def num(value: float) -> str:
    return format(int(round(value)), ",d")


def pct(share: Optional[float]) -> str:
    return "-" if share is None else "%.1f%%" % (100 * share)


def at(locator: schema.Locator) -> str:
    return "%s:%d" % (home(locator.file), locator.line)


def uuid(locator: schema.Locator) -> str:
    return locator.uuid or "-"  # a bookkeeping record has none


def tags(dims: dict) -> str:
    """Every dimension the fact has, ``window`` too: a file can hold several."""
    return " ".join("%s=%s" % (d, home(dims[d])) for d in schema.DIMENSIONS if d in dims)


def value(dim: str, text: str, names: Optional[Dict[str, str]] = None) -> str:
    """A value as printed: a subagent or a session by its name when
    ``names`` has one (``subagent_names``, ``session_names``),
    anything else with home as ``~``."""
    return (names or {}).get(text, text) if dim in NAMED else home(text)


NAMED = (schema.SUBAGENT_DIM, schema.SESSION_DIM)  # the dimensions printed by a short name



def _label(row: query.Row, dim: str, names: Optional[Dict[str, str]] = None) -> str:
    if row.kind == query.RESIDUAL:
        return schema.residual_label(dim)
    return value(dim, row.value, names) if row.kind == query.REGULAR else row.value


Counts = Sequence[Tuple[str, Optional[Dict[str, int]]]]  # a count column: its name, a count per value


def parts_text(parts: Sequence[Tuple[str, float]]) -> str:
    """``= a 1 + b 2 + 3 more 4``: the catch-all's two largest parts by
    name, always (D-TWO-PARTS), the rest folded as a table folds its rows
    (``FOLDED`` finds the fold: its row's pin lists them); one part names
    what the whole row is."""
    named, rest = parts[:2], parts[2:]
    return "= " + " + ".join(["%s %s" % (what, num(mass)) for what, mass in named]
                             + (["%d more %s" % (len(rest), num(sum(m for _, m in rest)))] if rest else []))


FOLDED = re.compile(r" \d+ more [-\d,]+$")  # a catch-all's parts that fold: its pin lists them


def command_lines(lead: str, command: str, indent: str = "    ") -> List[str]:
    """``lead`` then ``command`` within the line budget, broken between
    words (a flag kept with its value) with a shell's `` \\`` continuation
    when it must be, so it still pastes and runs."""
    words: List[str] = []
    for word in shlex.split(command, posix=False):  # quotes kept: a quoted word stays whole
        words[-1:] = [words[-1] + " " + word] if words and words[-1].startswith("--") and " " not in words[-1] \
            else words[-1:] + [word]
    lines, line = [], lead
    for word in words:
        if line.strip() and len(line) + 1 + len(word) + 2 > WIDTH:
            lines.append(line + " \\")
            line = indent
        line += ("" if line.endswith(" ") or not line else " ") + word
    return lines + [line]


def table(grouped: query.Table, metric: str, limit: Optional[int], total: Optional[str] = None,
          names: Optional[Dict[str, str]] = None, counts: Optional[Counts] = None,
          more: str = "", parts: Sequence[Tuple[str, float]] = (),
          glosses: Optional[Dict[str, str]] = None, pin: str = "") -> List[str]:
    """The top ``limit`` regular rows (every one when None, and in the
    cause table), the rest as ``+N more`` ending with ``more``, the command
    that prints them all; the ``= 100%`` row, the base every share is of;
    then the catch-all row (``schema.residual_label``) with its ``parts`` and the
    signed shrink row, in no share. ``total``, when given, closes the
    table with every row's sum and that text. The mass column is named for
    the metric as printed, the count column for the carrier kind it
    counts, or ``counts`` names the count columns and counts each value
    (``-`` on a signed row, a mean's never summed). ``glosses`` print
    beside a row's value where the line has room. ``pin``, the command
    that pins the catch-all row, prints under it when its parts fold: that
    screen lists each part (UX_PRINCIPLES 2, 3)."""
    heading = title(grouped.dim)
    regular = [r for r in grouped.rows if r.kind == query.REGULAR]
    if grouped.dim == schema.CAUSE_DIM or limit is None:
        limit = len(regular)
    shown, hidden = regular[:limit], regular[limit:]
    if hidden:
        shown.append(query.Row("+%s more" % format(len(hidden), ",d"), sum(r.mass for r in hidden),
                               sum(r.count for r in hidden), query.REGULAR))
    values = len(shown) - bool(hidden)  # rows of one value each; the rest print italic
    base = [query.Row(BASE_LABEL, grouped.base, sum(r.count for r in regular), BASE_LABEL)] if regular else []
    shown += base + [r for r in grouped.rows if r.kind != query.REGULAR]
    labels = [_label(r, grouped.dim, names) if i < values or r.kind not in (query.REGULAR, BASE_LABEL)
              else r.value for i, r in enumerate(shown)]
    if total is not None:
        labels.append(TOTAL_LABEL)
    width = max(len(label) for label in labels + [heading])
    columns = counts or [(schema.PLURAL[schema.metric(metric).carrier], None)]
    every = sum(r.count for r in grouped.rows)

    def cell(name: str, per: Optional[Dict[str, float]], i: int, r: query.Row) -> str:
        if r.kind == BASE_LABEL:
            return "-" if name == AVG_CALL else num(sum(per.get(h.value, 0) for h in regular) if per else r.count)
        if per is None or r.kind != query.REGULAR:  # the residual's own windows count; a signed row's do not
            return num(per[None]) if per and r.kind == query.RESIDUAL and None in per else (
                "-" if per else num(r.count))
        if i == values:  # the rest: a mean is never summed
            return "-" if name == AVG_CALL else num(sum(per.get(h.value, 0) for h in hidden))
        return num(per.get(r.value, 0))
    cells = [[name] + [cell(name, per, i, r) for i, r in enumerate(shown)]
             + ["-" if name == AVG_CALL else num(sum(per.values()) if per else every)]
             for name, per in columns]
    cells.insert(0, [glossary.printed(metric)] + [num(r.mass) for r in shown]
                 + [num(sum(r.mass for r in grouped.rows))])
    widths = [max(map(len, column)) for column in cells]

    def line(label: str, k: int, last: str) -> str:  # row ``k`` of every figure column
        text = "  ".join(["%-*s" % (width, label)] + ["%*s" % (w, c[k]) for w, c in zip(widths, cells)] + [last])
        return text.rstrip()

    lines = [style.tag(line(heading, 0, "share" if regular else ""), style.HEADER)]
    mass, at = width + 2, width + sum(w + 2 for w in widths) + 2  # the figures' spans: mass and share
    for i, (label, r) in enumerate(zip(labels, shown)):
        share = grouped.share(r.mass) if r.kind == query.REGULAR else None
        free = r.kind == query.REGULAR and i < values and grouped.dim not in schema.VOCABULARY  # a data value
        last = "%6s" % (pct(share) if r.kind != BASE_LABEL else "")
        text = line(label, i + 1, last)
        note = ""
        if r.kind == query.RESIDUAL:
            note = parts_text(parts)
        elif i == values and hidden:
            note = more
        elif r.kind == BASE_LABEL:
            note = BASE_NOTE % schema.residual_label(grouped.dim) if any(
                h.kind == query.RESIDUAL for h in grouped.rows) else BASE_NOTE.split(", not")[0]
        elif r.kind in (query.REGULAR, query.SIGNED) and glosses and r.value in glosses:
            note = glosses[r.value] if len(text) + 2 + len(glosses[r.value]) <= WIDTH else ""
        role = style.ROW if i < values else (style.TOTAL if r.kind == BASE_LABEL else style.OTHER)
        star = r.kind == query.RESIDUAL  # room for a term's first ``*``
        if note and len(text) + 2 + star + len(note) > WIDTH:  # a long note: its own line, under its row
            lines.append(style.tag(text, role, share, ((mass, mass + widths[0]), (at, at + 6))))
            lines += [style.tag(part, style.HINT if i == values else "", values=((4, len(part)),) * (i == values))
                      for part in (command_lines("    ", note) if i == values else ["    " + note])]
        else:
            text = text + "  " + note if note else text
            lines.append(style.tag(text, role, share, ((mass, mass + widths[0]), (at, at + 6)),
                                   ((0, width),) if free else ((len(text) - len(note), len(text)),) * (
                                       r.kind != query.RESIDUAL) if note else ()))  # a part's term takes its *
        if r.kind == query.RESIDUAL and pin and FOLDED.search(note):
            lines += [style.tag(part, style.HINT, values=((4, len(part)),)) for part in command_lines("    ", pin)]
    if total is not None:  # its verdict alone where a long label leaves no room for its words
        text = line(TOTAL_LABEL, -1, "      " + total)
        lines.append(style.tag(text if len(text) <= WIDTH else line(TOTAL_LABEL, -1, "      " + OK_MARK),
                               style.TOTAL))
    if grouped.dim == schema.PROJECT_DIM and any(label.startswith("~") for label in labels):
        lines.append(style.tag(HOME_NOTE, style.KEY))  # the ``~`` read once, where it prints
    return lines


def relabelled(grouped: query.Table, relabels: List[Tuple[str, Dict[str, str]]],
               names: Optional[Dict[str, str]] = None) -> str:
    """The one line that the tables repeating ``grouped`` row for row print
    in their place, under it: each ``(dim, labels)``'s labels for the
    regular rows, in their order; several such tables share the line,
    their labels for a row joined by `` / ``."""
    rows = [r.value for r in grouped.rows if r.kind == query.REGULAR]
    head = "%s: the rows above, labelled " % ", ".join(
        [title(relabels[0][0])] + [dim for dim, _ in relabels[1:]])
    text = head + ", ".join(" / ".join(value(dim, labels[v], names) for dim, labels in relabels)
                            for v in rows)
    return style.tag(text, "", values=((len(head), len(text)),))


def subagent_names(loaded_types: Dict[str, str], facts: Iterable[Fact]) -> Dict[str, str]:
    """Each subagent id whose file's type ``loaded_types`` records (by file
    name, ``corpus.agent_type``), as ``<type> <first 8 of its id>``, unless
    that label would name two ids: those keep their whole id. Display and
    pins only: the id stays the dimension's value."""
    named = {f.dims[schema.SUBAGENT_DIM]: loaded_types[f.locator.file] for f in facts
             if schema.SUBAGENT_DIM in f.dims and f.locator.file in loaded_types}
    named = {i: "%s %s" % (kind, i[:8]) for i, kind in named.items()}
    seen: Dict[str, int] = {}
    for label in named.values():
        seen[label] = seen.get(label, 0) + 1
    return {i: label for i, label in named.items() if seen[label] == 1}


UUID = re.compile(r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$")


def session_names(facts: Iterable[Fact]) -> Dict[str, str]:
    """Each uuid session id as its first 8 hex, like a subagent's and a
    window's (UX_PRINCIPLES 1: one identity style), unless those 8 name
    two sessions: those keep their whole id. ``cli.resolve`` reads
    either back, and any unique prefix."""
    ids = {f.dims[schema.SESSION_DIM] for f in facts if schema.SESSION_DIM in f.dims}
    short = [i[:8] for i in ids if UUID.match(i)]
    return {i: i[:8] for i in ids if UUID.match(i) and short.count(i[:8]) == 1}
