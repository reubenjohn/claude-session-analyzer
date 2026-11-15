"""Table and leaf rendering of a selection, the key under the tables, and
the formats every line shares: numbers, ``~`` for home, and line styles.

A line is a ``str``; a styled one is a ``Styled`` str that also names its
style, which ``paint`` turns into colour only when the CLI asks for it (a
TTY, ``NO_COLOR`` unset), so every test compares plain text."""
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Tuple

from . import heads, query, schema
from .schema import Fact

RESIDUAL_LABEL = schema.RESIDUAL_LABEL  # the row for facts that lack the grouped dimension
LABEL_WIDTH = 40      # a default table keeps a longer label's tail behind "…"; --by prints it whole

# Cause rows whose mass is not splittable by content: each prints its
# glossary meaning in the key. Neither can lead the headline: ``cause`` is
# no view's lever.
UNSPLITTABLE = {schema.WINDOW_HEAD: schema.GLOSSARY[schema.WINDOW_HEAD].meaning,
                schema.AMBIGUOUS: "%s (by reason: %s)" % (schema.GLOSSARY[schema.AMBIGUOUS].meaning,
                                                          ", ".join(schema.REASONS))}

BOLD, DIM, GOOD, BAD = "1", "2", "32", "31"  # ANSI SGR codes
OK_MARK, BAD_MARK = "✓", "✗"


class Styled(str):
    """A line that prints in ``style`` when colour is on."""
    style = ""


def styled(text: str, style: str) -> str:
    line = Styled(text)
    line.style = style
    return line


def paint(line: str) -> str:
    style = getattr(line, "style", "")
    return "\033[%sm%s\033[0m" % (style, line) if style else line


def tilde(path: Path) -> str:
    """A path under home as ``~/...``: output never prints the home directory."""
    home, text = str(Path.home()), str(path)
    return "~" + text[len(home):] if text == home or text.startswith(home + "/") else text


def marked(term: str) -> str:
    """The term with the explain marker when the glossary marks it."""
    entry = schema.GLOSSARY.get(term)
    return term + schema.MARKER if entry and entry.marked else term


KEY_WIDTH = 14
TOTAL_LABEL = "= total"  # the row a whole-window cause table closes with


def key_entry(label: str, text: str) -> str:
    return "  %-*s %s" % (KEY_WIDTH, label, text)


def key(entries: List[Tuple[str, str]]) -> List[str]:
    """The one key under the tables, dimmed: each note once, by label."""
    if not entries:
        return []
    seen = list(dict.fromkeys(entries))
    return [styled(line, DIM) for line in
            ["key (%s: sa explain TERM)" % schema.MARKER] + [key_entry(*e) for e in seen]]

Case = Tuple[str, Callable[[dict], bool]]  # a reading of a residual fact, and the dims it holds for


def _cause(cause: str) -> Callable[[dict], bool]:
    return lambda dims: dims.get(schema.CAUSE_DIM) == cause


# Printed under a table that shows the residual row: what the row means,
# then the cases that some fact in it satisfies, read from their dimensions
# so a drill (``--where tool=Bash --by head``) names no case it cannot hold.
RESIDUAL_NOTES: Dict[str, Tuple[str, List[Case]]] = {
    schema.AGENT_DIM: ("main windows (no subagent)", []),
    schema.TOOL_DIM: ("no tool", [(c, _cause(c)) for c in (
        schema.WINDOW_HEAD, schema.FEED_FORWARD, schema.USER_TEXT)] + [
        ("%s whose candidates share no one tool" % schema.AMBIGUOUS, _cause(schema.AMBIGUOUS)),
        ("a %s whose tool_use did not resolve" % schema.TOOL_RESULT, _cause(schema.TOOL_RESULT))]),
    schema.HEAD_DIM: ("no head", [
        ("no tool", lambda dims: schema.TOOL_DIM not in dims),
        ("a %s of a tool with no head (any but %s)"
         % (schema.TOOL_RESULT, ", ".join(sorted(heads.EXTRACTORS))),
         lambda dims: schema.TOOL_DIM in dims and _cause(schema.TOOL_RESULT)(dims)),
        ("%s whose candidates share a tool but no head" % schema.AMBIGUOUS,
         lambda dims: schema.TOOL_DIM in dims and _cause(schema.AMBIGUOUS)(dims))]),
    schema.REASON_DIM: ("not %s" % schema.AMBIGUOUS, [  # shrink is the signed row, never residual
        (c, _cause(c)) for c in schema.CAUSES if c not in (schema.AMBIGUOUS, schema.SHRINK)]),
}


def residual_note(dim: str, residual: Sequence[dict]) -> str:
    meaning, cases = RESIDUAL_NOTES[dim]
    held = [text for text, holds in cases if any(holds(dims) for dims in residual)]
    return meaning + (": " + ", ".join(held) if held else "")


def residual_label(dim: str) -> str:
    return "%s by %s" % (marked(RESIDUAL_LABEL), dim)


def notes(grouped: query.Table) -> List[Tuple[str, str]]:
    """The key entries a table's rows call for: an unsplittable cause row's
    meaning, and what its residual row holds."""
    entries = []
    if grouped.dim == schema.CAUSE_DIM:
        entries += [(marked(r.value), UNSPLITTABLE[r.value]) for r in grouped.rows
                    if r.value in UNSPLITTABLE]
    if grouped.dim in RESIDUAL_NOTES and any(r.kind == query.RESIDUAL for r in grouped.rows):
        entries.append((residual_label(grouped.dim), residual_note(grouped.dim, grouped.residual)))
    return entries


def share_header(grouped: query.Table) -> str:
    """The share column names its base: the total, the tokens added (the
    signed row's mass taken out), or those with a value (the residual row's
    too; the signed row is never a share)."""
    if not grouped.base:
        return "share"
    kinds = {r.kind for r in grouped.rows}
    if kinds == {query.REGULAR}:
        return "share of total"
    if query.RESIDUAL not in kinds:  # the signed row alone: the tokens added
        return "share of %s added" % num(grouped.base)
    return "share of %s with %s %s" % (num(grouped.base), "an" if grouped.dim[0] in "aeiou" else "a",
                                       grouped.dim)


def count(n: int, singular: str, plural: Optional[str] = None) -> str:
    """A count before its noun: ``1 window``, ``1,364 windows``."""
    return "%s %s" % (format(n, ",d"), singular if n == 1 else plural or singular + "s")


def num(value: float) -> str:
    return format(int(round(value)), ",d")


def pct(share: Optional[float]) -> str:
    return "-" if share is None else "%.1f%%" % (100 * share)


def at(locator: schema.Locator) -> str:
    return "%s:%d" % (locator.file, locator.line)


def uuid(locator: schema.Locator) -> str:
    return locator.uuid or "-"  # a bookkeeping record has none


def tags(dims: dict) -> str:
    """Every dimension but ``window``, which the locator beside it names."""
    return " ".join("%s=%s" % (d, dims[d]) for d in schema.DIMENSIONS
                    if d in dims and d != schema.WINDOW_DIM)


def _label(row: query.Row, whole: bool) -> str:
    label = RESIDUAL_LABEL if row.kind == query.RESIDUAL else (
        row.value + (" (signed)" if row.kind == query.SIGNED else ""))
    return label if whole or len(label) <= LABEL_WIDTH else "…" + label[1 - LABEL_WIDTH:]


def table(grouped: query.Table, metric: str, limit: int, whole: bool,
          total: Optional[str] = None) -> List[str]:
    """The top ``limit`` regular rows, one line for the rest so the column
    still adds up, then the residual and signed rows. Those, and a regular
    cause row whose note prints under the table (``UNSPLITTABLE``), are never
    hidden.
    A label is cut to ``LABEL_WIDTH`` unless ``whole``, which an asked-for
    (``--by``) table is, so its labels can be copied into ``--where``.
    The mass column is named for the metric (its unit is stated once, on the
    headline), the count column for what it counts, the metric's carrier
    kind. A table with no base (no regular mass) prints ``share`` alone;
    the share column names its base (``share_header``). ``total``, when
    given, closes the table with a row of every row's sum and that text in
    the share column. What the rows mean is the key's (``notes``)."""
    title = "by " + grouped.dim
    noted = UNSPLITTABLE if grouped.dim == schema.CAUSE_DIM else {}
    regular = [r for r in grouped.rows if r.kind == query.REGULAR]
    shown = regular[:limit] + [r for r in regular[limit:] if r.value in noted]
    hidden = [r for r in regular[limit:] if r.value not in noted]
    if hidden:
        shown.append(query.Row("+" + count(len(hidden), "more row"), sum(r.mass for r in hidden),
                               sum(r.count for r in hidden), query.REGULAR))
    shown += [r for r in grouped.rows if r.kind != query.REGULAR]
    labels = [_label(r, whole) for r in shown]
    width = max(len(label) for label in labels + [title])
    counts = schema.metric(metric).carrier + "s"
    share = share_header(grouped)
    lines = [styled("%-*s  %16s  %s  %s" % (width, title, metric, counts, share), BOLD)]
    for label, r in zip(labels, shown):
        lines.append("%-*s  %16s  %*s  %*s" % (
            width, label, num(r.mass), len(counts), num(r.count), len(share),
            pct(grouped.share(r.mass) if r.kind == query.REGULAR else None)))
    if total is not None:
        lines.append(styled("%-*s  %16s  %*s  %s" % (
            width, TOTAL_LABEL, num(sum(r.mass for r in grouped.rows)), len(counts),
            num(sum(r.count for r in grouped.rows)), total), BOLD))
    return lines



def leaves(facts: List[Fact], metric: str, limit: int) -> List[str]:
    """The ``limit`` largest facts, each with its dimensions and, indented
    under it, its evidence: the candidate contributors of an ambiguous
    increment, the parent of a fork's window head."""
    spec = schema.metric(metric)
    largest = sorted((f for f in facts if f.kind == spec.carrier),
                     key=lambda f: -abs(f.metrics[metric]))[:limit]  # a shrink is as large as its |mass|
    lines = ["%16s  file:line  uuid  dimensions" % metric]  # the metric, as in the tables
    for f in largest:
        lines.append("%16s  %s  %s  %s" % (num(f.metrics[metric]), at(f.locator),
                                           uuid(f.locator), tags(f.dims)))
        lines += list(_evidence(f.evidence))
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
        else:
            yield "%18s%s: %s" % ("", key, value)
