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
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import glossary, query, residual, schema, style
from .schema import Fact

WIDTH = 100  # every line's budget (UX_PRINCIPLES)
BASE_LABEL = "= 100%"  # the row every share is of
TOTAL_LABEL = "= average call"  # the row a whole-window cause table closes with: its rows add up to it
OK_MARK, BAD_MARK = "✓", "✗"
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
    a printed label still works in ``--where``."""
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
        return residual.label(dim)
    return value(dim, row.value, names) if row.kind == query.REGULAR else row.value


Counts = Sequence[Tuple[str, Optional[Dict[str, int]]]]  # a count column: its name, a count per value


def parts_text(parts: Sequence[Tuple[str, float]], room: int) -> str:
    """``= a 1 + b 2 + other 3``: the catch-all's parts, largest first, as
    many as ``room`` columns hold, the rest folded into ``other``."""
    terms = ["%s %s" % (what, num(mass)) for what, mass in parts]
    for keep in range(len(terms), 0, -1):
        rest = sum(m for _, m in parts[keep:])
        text = "= " + " + ".join(terms[:keep] + (["other %s" % num(rest)] if keep < len(terms) else []))
        if len(text) <= room or keep == 1:
            return text if len(parts) > 1 else ""  # one part is the row itself
    return ""


def table(grouped: query.Table, metric: str, limit: Optional[int], total: Optional[str] = None,
          names: Optional[Dict[str, str]] = None, counts: Optional[Counts] = None,
          more: str = "", parts: Sequence[Tuple[str, float]] = (),
          glosses: Optional[Dict[str, str]] = None) -> List[str]:
    """The top ``limit`` regular rows (every one when None, and in the
    cause table), the rest as ``+N more`` ending with ``more``, the command
    that prints them all; the ``= 100%`` row, the base every share is of;
    then the catch-all row (``residual.label``) with its ``parts`` and the
    signed shrink row, in no share. ``total``, when given, closes the
    table with every row's sum and that text. The mass column is named for
    the metric as printed, the count column for the carrier kind it
    counts, or ``counts`` names the count columns and counts each value
    (``-`` on a signed row, a mean's never summed). ``glosses`` print
    beside a row's value where the line has room."""
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
            note = parts_text(parts, WIDTH - len(text) - 2)
        elif i == values and hidden:
            note = more
        elif r.kind == BASE_LABEL and any(h.kind == query.RESIDUAL for h in grouped.rows):
            note = BASE_NOTE % residual.label(grouped.dim)
        elif r.kind in (query.REGULAR, query.SIGNED) and glosses and r.value in glosses:
            note = glosses[r.value] if len(text) + 2 + len(glosses[r.value]) <= WIDTH else ""
        role = style.ROW if i < values else (style.TOTAL if r.kind == BASE_LABEL else style.OTHER)
        if note and len(text) + 2 + len(note) > WIDTH:  # a long note: its own line, under its row
            if r.kind == query.RESIDUAL:
                note = parts_text(parts, WIDTH - 4)
            lines.append(style.tag(text, role, share, ((mass, mass + widths[0]), (at, at + 6))))
            lines.append(style.tag("    " + note, style.HINT if i == values else "", values=((4, 4 + len(note)),)))
            continue
        text = text + "  " + note if note else text
        lines.append(style.tag(text, role, share, ((mass, mass + widths[0]), (at, at + 6)),
                               ((0, width),) if free else ((len(text) - len(note), len(text)),) if note else ()))
    if total is not None:
        lines.append(style.tag(line(TOTAL_LABEL, -1, "      " + total), style.TOTAL))
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
    ``--where`` only: the id stays the dimension's value."""
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
    two sessions: those keep their whole id. ``grammar.resolve`` reads
    either back, and any unique prefix."""
    ids = {f.dims[schema.SESSION_DIM] for f in facts if schema.SESSION_DIM in f.dims}
    short = [i[:8] for i in ids if UUID.match(i)]
    return {i: i[:8] for i in ids if UUID.match(i) and short.count(i[:8]) == 1}
