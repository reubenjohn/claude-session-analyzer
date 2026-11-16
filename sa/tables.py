"""Table and leaf rendering of a selection, the key under the tables, and
the formats every line shares: numbers, ``~`` for home, and line styles.

A line is a ``str``; one that styles is a ``style.Line`` naming its role,
which ``style`` paints only when the CLI asks for it, so every test
compares plain text."""
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import glossary, query, residual, schema, style
from .schema import Fact

RESIDUAL_LABEL = glossary.RESIDUAL_LABEL  # the row for facts that lack the grouped dimension
RESIDUAL_ROW = RESIDUAL_LABEL + glossary.MARKER  # as every table labels it
LABEL_WIDTH = 40      # a default table keeps a longer label's tail behind "…"; --by prints it whole

# Cause rows whose mass is not splittable by content: each prints its
# glossary clause in the key, the full text in ``sa explain``. Neither can
# lead the headline: ``cause`` is no view's lever.
UNSPLITTABLE = {c: glossary.brief(c) for c in (schema.STARTING_CONTEXT, schema.AMBIGUOUS)}
# A table's title, where its dimension's name alone does not explain it.
TITLES = {schema.COMMAND_DIM: "command / file type"}


def title(dim: str) -> str:
    return "by " + TITLES.get(dim, dim)

OK_MARK, BAD_MARK = "✓", "✗"


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


marked = glossary.marked
TOTAL_LABEL = "= average"  # the row a whole-window cause table closes with: its rows add up to it
AVG_CALL = glossary.printed(glossary.AVG_CALL)  # a count column that is a mean: never summed


def key(entries: List[Tuple[str, str]]) -> List[str]:
    """The one key under the tables, dimmed: each footnoted term once, as
    marked in the body, one clause each, its header naming the command
    that says more (the full text is ``sa explain``'s)."""
    if not entries:
        return []
    width = max(len(term) for term, _ in entries) + len(glossary.MARKER)
    head = "%s · more on any of them: %s explain %s" % (KEY_TITLE, glossary.PROG, entries[0][0])
    return [style.tag(line, style.KEY) for line in [head] + [
        "  %-*s = %s" % (width, term + glossary.MARKER, text) for term, text in entries]]


KEY_TITLE = glossary.MARKER + " explained below"  # the key's header opens with it


def footnote(lines: List[str]) -> Tuple[List[str], List[str]]:
    """Each marked glossary term, at its first appearance in ``lines`` (a
    table's header aside: its rows carry the mark, the residual's always),
    takes the marker (a padded line gives up one space of its padding, so
    its columns hold); never inside a line's value spans: a project or a
    tool named like a term is a value, not the term. A term spelt with
    ``_`` is found spelt with a space too, and keyed as found. The terms
    marked, in the order they first appear."""
    found = []
    for term in (glossary.printed(t) for t, e in glossary.GLOSSARY.items() if e.marked):
        word = re.compile(r"(?<![\w=*-])%s(s?)(?![\w=-])" % re.escape(term).replace("_", "[_ ]"))
        for i, line in enumerate(lines):
            spans = getattr(line, "values", ())
            m = None if getattr(line, "role", "") == style.HEADER else next(
                (m for m in word.finditer(line) if not any(a <= m.start() < b for a, b in spans)), None)
            if m:
                found.append((i, m.start(), line[m.start():m.end() - len(m.group(1))]))
                if line[m.end():m.end() + 1] != glossary.MARKER:
                    end = m.end()
                    pad = line.find("  ", end)  # padding gives up a space: the columns hold
                    pad = len(line) if pad < 0 else pad
                    text = line[:end] + glossary.MARKER + line[end:pad] + line[pad + 1:]

                    def moved(at: int) -> int:
                        return at + (end <= at <= pad) if pad < len(line) else at + (at >= end)
                    lines[i] = style.retag(line, text, [(moved(a), moved(b)) for a, b in spans])
                break
    return lines, [term for _, _, term in sorted(found)]


def share_header(grouped: query.Table, per_call: bool = False) -> str:
    """The share column's header, naming its base after the column: the
    total (per call, the average), the tokens added (per call, the average
    before shrink: the signed row's mass taken out), or those with a value
    (the residual row's too; the signed row is never a share)."""
    if not grouped.base:
        return "share"
    kinds = {r.kind for r in grouped.rows}
    if kinds == {query.REGULAR}:
        return "share of average" if per_call else "share of total"
    if query.RESIDUAL not in kinds:  # the signed row alone: the tokens added
        return "share of %s %s" % (num(grouped.base), "before shrink" if per_call else "added")
    return "share of %s (all but %s)" % (num(grouped.base), RESIDUAL_LABEL)


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
    """A value as printed: a subagent by its name when ``names`` has one
    (``render.subagent_names``), anything else with home as ``~``."""
    return (names or {}).get(text, text) if dim == schema.SUBAGENT_DIM else home(text)


def _label(row: query.Row, whole: bool, dim: str = "", names: Optional[Dict[str, str]] = None) -> str:
    label = RESIDUAL_ROW if row.kind == query.RESIDUAL else (
        value(dim, row.value, names) if row.kind == query.REGULAR else
        home(row.value) + (" (signed)" if row.kind == query.SIGNED else ""))
    return label if whole else cut(label)


def cut(label: str) -> str:
    """A default table's label: one over ``LABEL_WIDTH`` keeps its tail."""
    return label if len(label) <= LABEL_WIDTH else "…" + label[1 - LABEL_WIDTH:]


Counts = Sequence[Tuple[str, Optional[Dict[str, int]]]]  # a count column: its name, a count per value


def table(grouped: query.Table, metric: str, limit: int, whole: bool,
          total: Optional[str] = None, names: Optional[Dict[str, str]] = None,
          counts: Optional[Counts] = None) -> List[str]:
    """The top ``limit`` regular rows, one line for the rest so the column
    still adds up, then the residual and signed rows. Those, and every row
    of the cause table, are never hidden.
    A label is cut to ``LABEL_WIDTH`` unless ``whole``, which an asked-for
    (``--by``) table is, so its labels can be copied into ``--where``.
    The mass column is named for the metric as printed (its unit is stated
    once, on the headline), the count column for the carrier kind it
    counts, or ``counts`` names the count columns and counts each value
    (on the residual row its windows', ``-`` on a signed row). The share column is as wide as a share; its
    header names the base after it (``share_header``), and a table with no
    base prints ``share`` alone. ``total``, when given, closes the table
    with a row of every row's sum and that text in the share column. The
    residual row ends with what it holds here (``residual.residual_note``);
    what the rows mean is the key's."""
    heading = title(grouped.dim)
    regular = [r for r in grouped.rows if r.kind == query.REGULAR]
    if grouped.dim == schema.CAUSE_DIM:
        limit = len(regular)
    shown, hidden = regular[:limit], regular[limit:]
    if hidden:
        shown.append(query.Row("+" + count(len(hidden), "more row"), sum(r.mass for r in hidden),
                               sum(r.count for r in hidden), query.REGULAR))
    values = len(shown) - bool(hidden)  # rows of one value each; the rest print italic
    shown += [r for r in grouped.rows if r.kind != query.REGULAR]
    labels = [_label(r, whole, grouped.dim, names) for r in shown]
    width = max(len(label) for label in labels + [heading])
    columns = counts or [(schema.PLURAL[schema.metric(metric).carrier], None)]

    def cell(name: str, per: Optional[Dict[str, float]], i: int, r: query.Row) -> str:
        if per is None or r.kind != query.REGULAR:  # the residual's own windows count; a signed row's do not
            return num(per[None]) if per and r.kind == query.RESIDUAL and None in per else (
                "-" if per else num(r.count))
        if i == values:  # the rest: a mean is never summed
            return "-" if name == AVG_CALL else num(sum(per.get(h.value, 0) for h in hidden))
        return num(per.get(r.value, 0))
    cells = [[name] + [cell(name, per, i, r) for i, r in enumerate(shown)]
             + ["-" if name == AVG_CALL else num(sum(per.values()) if per else sum(r.count for r in grouped.rows))]
             for name, per in columns]
    cells.insert(0, [glossary.printed(metric)] + [num(r.mass) for r in shown] + [num(sum(r.mass for r in grouped.rows))])
    widths = [max(map(len, column)) for column in cells]

    def line(label: str, k: int, last: str) -> str:  # row ``k`` of every figure column
        return "  ".join(["%-*s" % (width, label)] + ["%*s" % (w, c[k]) for w, c in zip(widths, cells)] + [last])

    per_call = schema.metric(metric).aggregation == schema.PER_CALL
    lines = [style.tag(line(heading, 0, share_header(grouped, per_call).rjust(6)), style.HEADER)]
    mass, at = width + 2, width + sum(w + 2 for w in widths) + 2  # the figures' spans: mass and share
    held = residual.residual_note(grouped.dim, grouped.residual) if (
        grouped.dim in residual.RESIDUAL_NOTES and grouped.residual) else ""  # what this table's residual holds
    for i, (label, r) in enumerate(zip(labels, shown)):
        share = grouped.share(r.mass) if r.kind == query.REGULAR else None
        free = r.kind == query.REGULAR and grouped.dim not in schema.VOCABULARY  # a data value
        last = "%6s" % pct(share) + ("  " + held if held and r.kind == query.RESIDUAL else "")
        lines.append(style.tag(line(label, i + 1, last), style.ROW if i < values else style.OTHER,
                               share, ((mass, mass + widths[0]), (at, at + 6)), ((0, width),) if free else ()))
    if total is not None:
        lines.append(style.tag(line(TOTAL_LABEL, -1, total), style.TOTAL))
    return lines


def relabelled(grouped: query.Table, relabels: List[Tuple[str, Dict[str, str]]],
               names: Optional[Dict[str, str]] = None) -> str:
    """The one line that the tables repeating ``grouped`` row for row print
    in their place, under it: each ``(dim, labels)``'s labels for the
    regular rows, in their order, each cut as a default table's; several
    such tables share the line, their labels for a row joined by `` / ``."""
    rows = [r.value for r in grouped.rows if r.kind == query.REGULAR]
    head = "%s: the rows above, labelled " % ", ".join(
        [title(relabels[0][0])] + [dim for dim, _ in relabels[1:]])
    text = head + ", ".join(" / ".join(cut(value(dim, labels[v], names)) for dim, labels in relabels)
                            for v in rows)
    return style.tag(text, "", values=((len(head), len(text)),))
