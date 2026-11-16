"""Table and leaf rendering of a selection, the key under the tables, and
the formats every line shares: numbers, ``~`` for home, and line styles.

A line is a ``str``; one that styles is a ``style.Line`` naming its role,
which ``style`` paints only when the CLI asks for it, so every test
compares plain text."""
import re
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Tuple

from . import glossary, heads, query, schema, style
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
TOTAL_LABEL = "= total"  # the row a whole-window cause table closes with


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


Case = Tuple[str, Callable[[dict], bool]]  # a reading of a residual fact, and the dims it holds for


def _cause(cause: str) -> Callable[[dict], bool]:
    return lambda dims: dims.get(schema.CAUSE_DIM) == cause


# What the residual row of a table by each dimension can hold, printed by
# ``sa explain unassigned``. An ambiguous change is residual when its candidates share no one
# tool (by tool) or no one command (by command); a tool_result, when its
# tool_use did not resolve (by tool) or its tool has no command (by command).
RESIDUAL_NOTES: Dict[str, Tuple[str, List[Case]]] = {
    schema.SUBAGENT_DIM: ("main windows", []),
    schema.TOOL_DIM: ("no tool", [(c, _cause(c)) for c in (
        schema.STARTING_CONTEXT, schema.REPLIES, schema.USER_TEXT, schema.INHERITED,
        schema.AMBIGUOUS)] + [("an unresolved %s" % schema.TOOL_RESULT, _cause(schema.TOOL_RESULT))]),
    schema.COMMAND_DIM: ("no command", [
        ("no tool", lambda dims: schema.TOOL_DIM not in dims),
        ("not %s" % "/".join(sorted(heads.EXTRACTORS)),
         lambda dims: schema.TOOL_DIM in dims and _cause(schema.TOOL_RESULT)(dims)),
        (schema.AMBIGUOUS, lambda dims: schema.TOOL_DIM in dims and _cause(schema.AMBIGUOUS)(dims))]),
    schema.REASON_DIM: ("not %s" % schema.AMBIGUOUS, [  # shrink is the signed row, never residual
        (c, _cause(c)) for c in schema.CAUSES if c not in (schema.AMBIGUOUS, schema.SHRINK)]),
}


def residual_note(dim: str, residual: Sequence[dict]) -> str:
    """What the residual row of a table by ``dim`` holds: the cases some of
    the ``residual`` facts' dimensions satisfy."""
    meaning, cases = RESIDUAL_NOTES[dim]
    held = [text for text, holds in cases if any(holds(dims) for dims in residual)]
    return meaning + (": " + ", ".join(held) if held else "")


def residual_cases(dim: str) -> str:
    """Every case the residual row of a table by ``dim`` can hold: for
    ``sa explain unassigned``."""
    meaning, cases = RESIDUAL_NOTES[dim]
    return meaning + (": " + ", ".join(text for text, _ in cases) if cases else "")


def share_header(grouped: query.Table) -> str:
    """The share column's header, naming its base after the column: the
    total, the tokens added (the signed row's mass taken out), or those with
    a value (the residual row's too; the signed row is never a share)."""
    if not grouped.base:
        return "share"
    kinds = {r.kind for r in grouped.rows}
    if kinds == {query.REGULAR}:
        return "share of total"
    if query.RESIDUAL not in kinds:  # the signed row alone: the tokens added
        return "share of %s added" % num(grouped.base)
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


def table(grouped: query.Table, metric: str, limit: int, whole: bool,
          total: Optional[str] = None, names: Optional[Dict[str, str]] = None) -> List[str]:
    """The top ``limit`` regular rows, one line for the rest so the column
    still adds up, then the residual and signed rows. Those, and every row
    of the cause table, are never hidden.
    A label is cut to ``LABEL_WIDTH`` unless ``whole``, which an asked-for
    (``--by``) table is, so its labels can be copied into ``--where``.
    The mass column is named for the metric as printed (its unit is stated
    once, on the headline), the count column for what it counts, the
    metric's carrier kind. The share column is as wide as a share; its
    header names the base after it (``share_header``), and a table with no
    base prints ``share`` alone. ``total``, when given, closes the table
    with a row of every row's sum and that text in the share column. What
    the rows mean is the key's (``notes``)."""
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
    sums = (num(sum(r.mass for r in grouped.rows)), num(sum(r.count for r in grouped.rows)))
    name, counts = glossary.printed(metric), schema.PLURAL[schema.metric(metric).carrier]
    mw = max([len(name), len(sums[0])] + [len(num(r.mass)) for r in shown])
    cw = max([len(counts), len(sums[1])] + [len(num(r.count)) for r in shown])
    lines = [style.tag("%-*s  %*s  %*s  %s" % (width, heading, mw, name, cw, counts,
                                               share_header(grouped).rjust(6)), style.HEADER)]
    for i, (label, r) in enumerate(zip(labels, shown)):
        share = grouped.share(r.mass) if r.kind == query.REGULAR else None
        mass, cell = width + 2, width + mw + cw + 6  # the figures' spans: mass and share
        free = r.kind == query.REGULAR and grouped.dim not in schema.VOCABULARY  # a data value
        lines.append(style.tag("%-*s  %*s  %*s  %6s" % (
            width, label, mw, num(r.mass), cw, num(r.count), pct(share)),
            style.ROW if i < values else style.OTHER, share, ((mass, mass + mw), (cell, cell + 6)),
            ((0, width),) if free else ()))
    if total is not None:
        lines.append(style.tag("%-*s  %*s  %*s  %s" % (width, TOTAL_LABEL, mw, sums[0], cw, sums[1],
                                                       total), style.TOTAL))
    return lines


def relabelled(grouped: query.Table, labels: Dict[str, str], dim: str,
               names: Optional[Dict[str, str]] = None) -> str:
    """The one line a table that repeats ``grouped`` row for row prints in
    its place, under it: its labels for the regular rows, in their order,
    each cut as a default table's."""
    head = "%s: the rows above, labelled " % title(dim)
    text = head + ", ".join(cut(value(dim, labels[r.value], names)) for r in grouped.rows if r.kind == query.REGULAR)
    return style.tag(text, "", values=((len(head), len(text)),))


def leaves(facts: List[Fact], metric: str, limit: int) -> List[str]:
    """The ``limit`` largest facts, each with its dimensions and, indented
    under it, its evidence: the candidate contributors of an ambiguous
    increment, the parent of a fork's starting context, the parent window and
    branch call of an inherited increment."""
    spec = schema.metric(metric)
    largest = sorted((f for f in facts if f.kind == spec.carrier),
                     key=lambda f: -abs(f.metrics[metric]))[:limit]  # a shrink is as large as its |mass|
    lines = ["%16s  file:line  uuid  dimensions" % glossary.printed(metric)]  # as in the tables
    for f in largest:
        lines.append("%16s  %s  %s  %s" % (num(f.metrics[metric]), at(f.locator),
                                           uuid(f.locator), tags(f.dims)))
        lines += list(_evidence(f.evidence))
    lines[1:] = [style.tag(line, "", values=((0, len(line)),)) for line in lines[1:]]  # values only
    return lines


def _evidence(evidence: dict) -> Iterator[str]:
    """Each key once; the candidates one per line under theirs, each with
    its line, uuid and the dimensions it would have booked."""
    for key, value in evidence.items():
        if key == schema.CANDIDATES:
            yield "%18s%s:%s" % ("", key, "" if value else " none")
            for candidate in value:
                yield "%20s%s %s  %s" % ("", at(candidate.locator), uuid(candidate.locator),
                                         tags(candidate.dims))
        elif isinstance(value, schema.WindowKey):  # a parent window: its --where value
            yield "%18s%s: %s=%s" % ("", key, schema.WINDOW_DIM, schema.window_value(value))
        elif isinstance(value, schema.Locator):
            yield "%18s%s: %s %s" % ("", key, at(value), uuid(value))
        else:
            yield "%18s%s: %s" % ("", key, value)
