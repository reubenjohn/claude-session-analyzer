"""Plain-text rendering of a selection: headline, population, tables, leaves,
footer. The tables are grouped here from the selection's facts; its total
and reconciliation come with it, so nothing here decides the exit status."""
from typing import Iterator, List, NamedTuple, Optional, Tuple

from . import heads, query, schema
from .query import Selection
from .schema import Fact


class View(NamedTuple):
    """The shape of one report: which metric, which tables by default, and
    whether the total is the windows' final occupancies, which the footer
    then checks."""
    metric: str
    tables: Tuple[str, ...]  # printed by default
    levers: Tuple[str, ...]  # the dimensions whose rows may lead the headline (``report``)
    reconciles: bool
    notes: Tuple[str, ...]   # printed under the headline


RESIDUAL_LABEL = "∅"  # the row for facts that lack the grouped dimension
LABEL_WIDTH = 40      # a longer label keeps its tail behind a leading "…" (--by fact has it whole)

# Rows whose mass is not splittable by content: each prints its note under
# its table, and the headline never names one as the lever.
UNSPLITTABLE = {schema.WINDOW_HEAD: "first call's context: boot prompt + first message, or"
                                    " inherited parent context for a fork; not splittable by"
                                    " content",
                schema.AMBIGUOUS: "intervals with several candidates: the one residual"
                                  " bucket, never spread over them (--by fact lists them)"}

# Printed under a table that shows the residual row, saying what it holds.
RESIDUAL_NOTES = {
    schema.AGENT_DIM: "%s: main windows (no subagent)" % RESIDUAL_LABEL,
    schema.TOOL_DIM: "%s: no tool: %s, %s, %s, and %s whose candidates share no one tool"
                     % (RESIDUAL_LABEL, schema.WINDOW_HEAD, schema.FEED_FORWARD,
                        schema.USER_TEXT, schema.AMBIGUOUS),
    schema.HEAD_DIM: "%s: no head: no tool, a tool with no head (any but %s), or %s with"
                     " mixed heads"
                     % (RESIDUAL_LABEL, ", ".join(sorted(heads.EXTRACTORS)), schema.AMBIGUOUS),
}


def _count(n: int, singular: str, plural: Optional[str] = None) -> str:
    """A count before its noun: ``1 window``, ``2 windows``."""
    return "%d %s" % (n, singular if n == 1 else plural or singular + "s")


def _num(value: float) -> str:
    return format(int(round(value)), ",d")


def _pct(share: Optional[float]) -> str:
    return "-" if share is None else "%.1f%%" % (100 * share)


def _status(holds: bool) -> str:
    return "OK" if holds else "MISMATCH"


def _at(locator: schema.Locator) -> str:
    return "%s:%d" % (locator.file, locator.line)


def _tags(dims: dict) -> str:
    """Every dimension but ``window``, which the locator beside it names."""
    return " ".join("%s=%s" % (d, dims[d]) for d in schema.DIMENSIONS
                    if d in dims and d != schema.WINDOW_DIM)


def report(view: View, sel: Selection, by: Optional[str], limit: int) -> List[str]:
    """Every line of the view. The headline's lever is the largest row
    across the shown tables of the view's lever dimensions, ties to the
    more specific one; ``--by`` makes its table the lever. Never ``cause``,
    whose rows are categories, nor a window dimension, whose one row on a
    drill is the whole total (D-HEADLINE-SPECIFIC as amended); never a
    table ``--where`` pinned, whose top row would be the filter itself."""
    spec = schema.metric(view.metric)
    if by == "fact":
        levers, body = [], _leaves(sel.facts, view.metric, limit)
    else:
        shown = [query.group(sel.facts, dim, view.metric) for dim in ([by] if by else view.tables)]
        pinned = {dim for dim, _ in sel.where}
        levers = [t for t in shown if t.dim not in pinned and (by or t.dim in view.levers)]
        body = [line for t in shown if t.rows
                for line in _table(t, view.metric, spec.carrier, limit) + [""]]
    return headline(view, sel, levers) + [population(sel), ""] + body + footer(view, sel)


def headline(view: View, sel: Selection, levers: List[query.Table]) -> List[str]:
    spec = schema.metric(view.metric)
    line = "%s: %s %s" % (view.metric, _num(sel.total), spec.unit)
    if view.reconciles and not sel.drill:
        line += " = the " + _count(sel.n_windows, "window's final occupancy",
                                   "windows' final occupancies summed")
    else:
        drilled = query.window_count(sel.facts)  # the windows the facts shown come from
        line += " over %s in %s" % (
            _count(sum(f.kind == spec.carrier for f in sel.facts), spec.carrier + " fact"),
            "%d of %s" % (drilled, _count(sel.n_windows, "window")) if drilled != sel.n_windows
            else _count(drilled, "window"))
    return [line + _top(levers, sel.total)] + _peaks(sel) + list(view.notes)


def _top(tables: List[query.Table], total: float) -> str:
    """The largest splittable row across ``tables``, ties to the more
    specific dimension (later in ``schema.DIMENSIONS``), with its mass and
    its share of the headline total, named as such: a table's own share
    column is over its base, which the residual and signed rows make
    smaller."""
    rows = [(t.dim, r) for t in tables for r in t.rows
            if r.kind == query.REGULAR and r.value not in UNSPLITTABLE]
    if not rows or not total:
        return ""
    dim, top = max(rows, key=lambda pair: (pair[1].mass, schema.DIMENSIONS.index(pair[0])))
    return "; top %s=%s %s (%s of the %s total)" % (
        dim, top.value, _num(top.mass), _pct(top.mass / total), _num(total))


def _peaks(sel: Selection) -> List[str]:
    """Every peak metric as the single call where it happened, over the
    whole windows selected: a drill keeps no call facts, and a peak reports
    no value at a node and is never summed."""
    lines = []
    for name, spec in schema.METRICS.items():
        if spec.aggregation == schema.PEAK:
            top = query.largest(sel.window_facts, name)
            if top is not None:
                lines.append("single-call peak %s over the %s: %s %s at %s"
                             % (name, _count(sel.n_windows, "whole window"),
                                _num(top.metrics[name]), spec.unit, _at(top.locator)))
    return lines


def population(sel: Selection) -> str:
    return ("population: root %s; %s read%s, %s, %s, %s; %s skipped, %s excluded%s"
            % (sel.root, _count(len(sel.loaded.files), "file"),
               "" if sel.since is None else " (modified within %gd)" % sel.since,
               _count(sel.n_windows, "window"),
               _count(sum(f.kind == schema.CALL for f in sel.window_facts), "call fact"),
               _count(sum(f.kind == schema.INCREMENT for f in sel.window_facts), "increment fact"),
               _count(sel.loaded.skipped_lines, "line"),
               _count(sel.loaded.duplicate_records, "duplicate record"),
               "".join("; where %s=%s" % p for p in sel.where)))


def _label(row: query.Row) -> str:
    label = RESIDUAL_LABEL if row.kind == query.RESIDUAL else (
        row.value + (" (signed)" if row.kind == query.SIGNED else ""))
    return label if len(label) <= LABEL_WIDTH else "…" + label[1 - LABEL_WIDTH:]


def _table(table: query.Table, metric: str, carrier: str, limit: int) -> List[str]:
    """The top ``limit`` regular rows, one line for the rest so the column
    still adds up, then the residual and signed rows, which are never hidden.
    The mass column is named for the metric (its unit is stated once, on the
    headline), the count column for what it counts, the metric's carrier
    kind. A table with no base (no regular mass) prints ``share`` alone."""
    title = "by " + table.dim
    regular = [r for r in table.rows if r.kind == query.REGULAR]
    shown = regular[:limit]
    hidden = regular[limit:]
    if hidden:
        shown.append(query.Row("+" + _count(len(hidden), "more row"), sum(r.mass for r in hidden),
                               sum(r.count for r in hidden), query.REGULAR))
    shown += [r for r in table.rows if r.kind != query.REGULAR]
    labels = [_label(r) for r in shown]
    width = max(len(label) for label in labels + [title])
    count = carrier + "s"
    share = "share of %s" % _num(table.base) if table.base else "share"
    lines = ["%-*s  %16s  %s  %s" % (width, title, metric, count, share)]
    for label, r in zip(labels, shown):
        lines.append("%-*s  %16s  %*d  %*s" % (
            width, label, _num(r.mass), len(count), r.count, len(share),
            _pct(table.share(r.mass) if r.kind == query.REGULAR else None)))
    lines += ["%s: %s" % (r.value, UNSPLITTABLE[r.value]) for r in shown if r.value in UNSPLITTABLE]
    if table.dim in RESIDUAL_NOTES and any(r.kind == query.RESIDUAL for r in shown):
        lines.append(RESIDUAL_NOTES[table.dim])
    return lines


def _leaves(facts: List[Fact], metric: str, limit: int) -> List[str]:
    """The ``limit`` largest facts, each with its dimensions and, indented
    under it, its evidence: the candidate contributors of an ambiguous
    increment, the parent of a fork's window head."""
    spec = schema.metric(metric)
    leaves = sorted((f for f in facts if f.kind == spec.carrier),
                    key=lambda f: -abs(f.metrics[metric]))[:limit]  # a shrink is as large as its |mass|
    lines = ["%16s  file:line  uuid  dimensions" % metric]  # the metric, as in the tables
    for f in leaves:
        lines.append("%16s  %s  %s  %s" % (_num(f.metrics[metric]), _at(f.locator),
                                           f.locator.uuid, _tags(f.dims)))
        lines += list(_evidence(f.evidence))
    return lines


def _evidence(evidence: dict) -> Iterator[str]:
    """Each key once; the candidates one per line under theirs, each with
    its line, uuid and the dimensions it would have booked."""
    for key, value in evidence.items():
        if key == schema.CANDIDATES:
            yield "%18s%s:%s" % ("", key, "" if value else " none")
            for candidate in value:
                yield "%20s%s %s  %s" % ("", _at(candidate.locator), candidate.locator.uuid,
                                         _tags(candidate.dims))
        else:
            yield "%18s%s: %s" % ("", key, value)


def _reconciliation(r: query.Reconciliation) -> List[str]:
    terms = " + ".join("%s %s" % (c, _num(r.by_cause[c])) for c in schema.CAUSES)
    reasons = ", ".join("%s %d" % (k, v) for k, v in r.by_reason.items() if v)

    def rate(n: int) -> str:
        return "%d (%.1f%%)" % (n, 100.0 * n / r.intervals) if r.intervals else "0"
    return [
        "reconciliation over %s: %s = %s; final occupancy %s: %s"
        % (_count(r.windows, "window"), terms, _num(r.booked), _num(r.final_occupancy),
           _status(r.mass_holds)),
        "intervals %d (= %s - %s): exact %s + ambiguous %s [%s] + shrink %s: %s"
        % (r.intervals, _count(r.calls, "call"), _count(r.windows, "window"), rate(r.exact),
           rate(r.ambiguous), reasons or "none", rate(r.shrink), _status(r.count_holds)),
        "exact: the interval's one token-relevant contributor (a tool_result or user"
        " text) after subtracting the previous call's output. Exact given the"
        " feed-forward model; bookkeeping attachments are folded into the single"
        " contributor's remainder.",
    ]


def _call_totals(sel: Selection, headline_metric: str) -> List[str]:
    """Every other additive call-carried metric as a total over the selection."""
    return ["%s: %s %s" % (name, _num(query.total(sel.facts, name)), spec.unit)
            for name, spec in schema.METRICS.items()
            if spec.carrier == schema.CALL and spec.aggregation == schema.ADDITIVE
            and name != headline_metric]


def footer(view: View, sel: Selection) -> List[str]:
    """The closing lines: the reconciliation in full, as a pointer when a
    drill is shown above it, or the other call totals for a view that does
    not reconcile."""
    if not view.reconciles:
        return _call_totals(sel, view.metric)
    if sel.drill:
        return ["reconciliation: applies to the %s above, not to this drill: %s"
                % (_count(sel.n_windows, "whole window"), _status(sel.reconciliation.holds))]
    return _reconciliation(sel.reconciliation)
