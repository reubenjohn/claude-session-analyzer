"""Table and leaf rendering of a selection, and the number formats every line shares."""
from typing import Iterator, List, Optional

from . import heads, query, schema
from .schema import Fact

RESIDUAL_LABEL = "∅"  # the row for facts that lack the grouped dimension
LABEL_WIDTH = 40      # a default table keeps a longer label's tail behind "…"; --by prints it whole

# Rows whose mass is not splittable by content: each prints its note under
# its table. Neither can lead the headline: ``cause`` is no view's lever.
UNSPLITTABLE = {schema.WINDOW_HEAD: "first call's context: boot prompt + first message, or"
                                    " inherited parent context for a fork; not splittable by"
                                    " content",
                schema.AMBIGUOUS: "intervals not attributable to one contributor (by reason: %s);"
                                  " never spread; --by fact lists them" % ", ".join(schema.REASONS)}

# Printed under a table that shows the residual row, saying what it holds.
RESIDUAL_NOTES = {
    schema.AGENT_DIM: "%s: main windows (no subagent)" % RESIDUAL_LABEL,
    schema.TOOL_DIM: "%s: no tool: %s, %s, %s, %s whose candidates share no one tool, or a"
                     " %s whose tool_use did not resolve"
                     % (RESIDUAL_LABEL, schema.WINDOW_HEAD, schema.FEED_FORWARD,
                        schema.USER_TEXT, schema.AMBIGUOUS, schema.TOOL_RESULT),
    schema.HEAD_DIM: "%s: no head: no tool, a tool with no head (any but %s), or %s with"
                     " mixed heads"
                     % (RESIDUAL_LABEL, ", ".join(sorted(heads.EXTRACTORS)), schema.AMBIGUOUS),
    schema.REASON_DIM: "%s: not %s: %s" % (RESIDUAL_LABEL, schema.AMBIGUOUS, ", ".join(
        c for c in schema.CAUSES if c not in (schema.AMBIGUOUS, schema.SHRINK))),  # shrink is signed
}


def count(n: int, singular: str, plural: Optional[str] = None) -> str:
    """A count before its noun: ``1 window``, ``1,364 windows``."""
    return "%s %s" % (format(n, ",d"), singular if n == 1 else plural or singular + "s")


def num(value: float) -> str:
    return format(int(round(value)), ",d")


def pct(share: Optional[float]) -> str:
    return "-" if share is None else "%.1f%%" % (100 * share)


def at(locator: schema.Locator) -> str:
    return "%s:%d" % (locator.file, locator.line)


def tags(dims: dict) -> str:
    """Every dimension but ``window``, which the locator beside it names."""
    return " ".join("%s=%s" % (d, dims[d]) for d in schema.DIMENSIONS
                    if d in dims and d != schema.WINDOW_DIM)


def _label(row: query.Row, whole: bool) -> str:
    label = RESIDUAL_LABEL if row.kind == query.RESIDUAL else (
        row.value + (" (signed)" if row.kind == query.SIGNED else ""))
    return label if whole or len(label) <= LABEL_WIDTH else "…" + label[1 - LABEL_WIDTH:]


def table(grouped: query.Table, metric: str, limit: int, whole: bool) -> List[str]:
    """The top ``limit`` regular rows, one line for the rest so the column
    still adds up, then the residual and signed rows, which are never hidden.
    A label is cut to ``LABEL_WIDTH`` unless ``whole``, which an asked-for
    (``--by``) table is, so its labels can be copied into ``--where``.
    The mass column is named for the metric (its unit is stated once, on the
    headline), the count column for what it counts, the metric's carrier
    kind. A table with no base (no regular mass) prints ``share`` alone."""
    title = "by " + grouped.dim
    regular = [r for r in grouped.rows if r.kind == query.REGULAR]
    shown = regular[:limit]
    hidden = regular[limit:]
    if hidden:
        shown.append(query.Row("+" + count(len(hidden), "more row"), sum(r.mass for r in hidden),
                               sum(r.count for r in hidden), query.REGULAR))
    shown += [r for r in grouped.rows if r.kind != query.REGULAR]
    labels = [_label(r, whole) for r in shown]
    width = max(len(label) for label in labels + [title])
    counts = schema.metric(metric).carrier + "s"
    share = "share of %s" % num(grouped.base) if grouped.base else "share"
    lines = ["%-*s  %16s  %s  %s" % (width, title, metric, counts, share)]
    for label, r in zip(labels, shown):
        lines.append("%-*s  %16s  %*s  %*s" % (
            width, label, num(r.mass), len(counts), num(r.count), len(share),
            pct(grouped.share(r.mass) if r.kind == query.REGULAR else None)))
    lines += ["%s: %s" % (r.value, UNSPLITTABLE[r.value]) for r in shown if r.value in UNSPLITTABLE]
    if grouped.dim in RESIDUAL_NOTES and any(r.kind == query.RESIDUAL for r in shown):
        lines.append(RESIDUAL_NOTES[grouped.dim])
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
                                           f.locator.uuid, tags(f.dims)))
        lines += list(_evidence(f.evidence))
    return lines


def _evidence(evidence: dict) -> Iterator[str]:
    """Each key once; the candidates one per line under theirs, each with
    its line, uuid and the dimensions it would have booked."""
    for key, value in evidence.items():
        if key == schema.CANDIDATES:
            yield "%18s%s:%s" % ("", key, "" if value else " none")
            for candidate in value:
                yield "%20s%s %s  %s" % ("", at(candidate.locator), candidate.locator.uuid,
                                         tags(candidate.dims))
        else:
            yield "%18s%s: %s" % ("", key, value)
