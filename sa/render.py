"""Plain-text rendering of a selection: headline, population, tables, leaves, footer."""
from pathlib import Path
from typing import Iterator, List, NamedTuple, Optional, Tuple

from . import corpus, heads, query, schema
from .schema import Fact


class View(NamedTuple):
    metric: str
    tables: Tuple[str, ...]  # printed by default; the first one not pinned by --where leads
    reconciles: bool         # the total is the windows' final occupancies, and the footer checks it
    notes: Tuple[str, ...]   # printed under the headline


SPEND_NOTE = ("spend is paid per call; context shares are not cost shares. What put"
              " the tokens there is answered by `sa context` (--by tool, --by head).")

VIEWS = {"context": View(schema.CONTEXT_DELTA, (schema.CAUSE_DIM, schema.TOOL_DIM, schema.HEAD_DIM)
                         + schema.WINDOW_DIMENSIONS[::-1], True, ()),
         "spend": View(schema.SPEND, schema.WINDOW_DIMENSIONS, False, (SPEND_NOTE,))}


class Selection(NamedTuple):
    root: Path
    since: Optional[float]          # days, when --since narrowed the files read
    where: List[Tuple[str, str]]    # every --where pair
    loaded: corpus.Corpus
    window_facts: List[Fact]        # whole windows kept by the window-dimension filters
    facts: List[Fact]               # the windows' facts kept by the drill filters too
    total: float                    # the view's metric over ``facts``, summed once

    @property
    def drill(self) -> List[Tuple[str, str]]:
        """The ``--where`` pairs that select within a window, not whole windows."""
        return [p for p in self.where if p[0] not in schema.WINDOW_DIMENSIONS]

    @property
    def n_windows(self) -> int:
        return len({f.locator.file for f in self.window_facts})


RESIDUAL_LABEL = "∅"  # the row for facts that lack the grouped dimension

# Rows whose mass is not splittable by content: each prints its note under
# its table, and the headline never names it.
UNSPLITTABLE = {schema.WINDOW_HEAD: "first call's context: boot prompt + first message, or"
                                    " inherited parent context for a fork; not splittable by"
                                    " content"}

# Printed under a table that shows the residual row, saying what it holds.
RESIDUAL_NOTES = {
    schema.AGENT_DIM: "%s: main windows (no subagent)" % RESIDUAL_LABEL,
    schema.TOOL_DIM: "%s: no tool: %s, %s, %s, and %s whose candidates share no one tool"
                     % (RESIDUAL_LABEL, schema.WINDOW_HEAD, schema.FEED_FORWARD,
                        schema.USER_TEXT, schema.AMBIGUOUS),
    schema.HEAD_DIM: "%s: no head: everything %s holds under `by %s`, %s whose candidates share"
                     " a tool but not its head, and every tool without a head (all but %s)"
                     % (RESIDUAL_LABEL, RESIDUAL_LABEL, schema.TOOL_DIM,
                        schema.AMBIGUOUS, ", ".join(sorted(heads.EXTRACTORS))),
}


def _num(value: float) -> str:
    return format(int(round(value)), ",d")


def _pct(share: Optional[float]) -> str:
    return "-" if share is None else "%.1f%%" % (100 * share)


def _status(holds: bool) -> str:
    return "OK" if holds else "MISMATCH"


def _at(locator: schema.Locator) -> str:
    return "%s:%d" % (locator.file, locator.line)


def _tags(dims: dict) -> str:
    return " ".join("%s=%s" % (d, dims[d]) for d in schema.DIMENSIONS if d in dims)


def report(view: View, sel: Selection, by: Optional[str], limit: int) -> Tuple[List[str], bool]:
    """Every line of the view, and whether its reconciliation held. The
    headline names the top row of the first table shown that ``--where``
    did not pin (its top row would be the filter itself)."""
    if by == "fact":
        lead, body = None, _leaves(sel.facts, view.metric, limit)
    else:
        shown = [query.group(sel.facts, dim, view.metric) for dim in ([by] if by else view.tables)]
        pinned = {dim for dim, _ in sel.where}
        lead = next((t for t in shown if t.dim not in pinned), None)
        unit = schema.metric(view.metric).unit
        body = [line for t in shown if t.rows for line in _table(t, unit, limit) + [""]]
    closing, holds = footer(view, sel)
    return headline(view, sel, lead) + [population(sel), ""] + body + closing, holds


def headline(view: View, sel: Selection, lead: Optional[query.Table]) -> List[str]:
    spec = schema.metric(view.metric)
    line = "%s: %s %s" % (view.metric, _num(sel.total), spec.unit)
    if view.reconciles and not sel.drill:
        line += " = the %d windows' final occupancies summed" % sel.n_windows
    else:
        line += " over %d %s facts in %d windows" % (
            sum(f.kind == spec.carrier for f in sel.facts), spec.carrier, sel.n_windows)
    if lead:
        line += _top(lead)
    return [line] + _peaks(sel) + list(view.notes)


def _top(table: query.Table) -> str:
    """The top splittable row with its mass and share; the share's base is
    named by what the other rows lack when it is not the total."""
    top = next((r for r in table.rows
                if r.kind == query.REGULAR and r.value not in UNSPLITTABLE), None)
    if top is None or table.share(top.mass) is None:
        return ""
    share = _pct(table.share(top.mass))
    kinds = {r.kind for r in table.rows}
    base = ["added"] if query.SIGNED in kinds else []
    if query.RESIDUAL in kinds:
        base.append("with a%s %s" % ("n" if table.dim[0] in "aeiou" else "", table.dim))
    if base:
        share += " of %s %s" % (_num(table.base), " ".join(base))
    return "; top %s=%s %s (%s)" % (table.dim, top.value, _num(top.mass), share)


def _peaks(sel: Selection) -> List[str]:
    """Every peak metric as the single call where it happened, over the
    whole windows selected: a drill keeps no call facts, and a peak reports
    no value at a node and is never summed."""
    lines = []
    for name, spec in schema.METRICS.items():
        if spec.aggregation == schema.PEAK:
            top = query.largest(sel.window_facts, name)
            if top is not None:
                lines.append("single-call peak %s over the %d whole windows: %s %s at %s"
                             % (name, sel.n_windows, _num(top.metrics[name]), spec.unit,
                                _at(top.locator)))
    return lines


def population(sel: Selection) -> str:
    return ("population: root %s; %d files read%s, %d windows, %d call facts, %d increment"
            " facts; %d lines skipped, %d duplicate records excluded%s"
            % (sel.root, len(sel.loaded.files),
               "" if sel.since is None else " (modified within %gd)" % sel.since,
               sel.n_windows, sum(f.kind == schema.CALL for f in sel.window_facts),
               sum(f.kind == schema.INCREMENT for f in sel.window_facts),
               sel.loaded.skipped_lines, sel.loaded.duplicate_records,
               "".join("; where %s=%s" % p for p in sel.where)))


def _label(row: query.Row) -> str:
    if row.kind == query.RESIDUAL:
        return RESIDUAL_LABEL
    return row.value + (" (signed)" if row.kind == query.SIGNED else "")


def _table(table: query.Table, unit: str, limit: int) -> List[str]:
    """The top ``limit`` regular rows, one line for the rest so the column
    still adds up, then the residual and signed rows, which are never hidden.
    A table with no base (no regular mass) prints ``share`` alone."""
    title = "by " + table.dim
    regular = [r for r in table.rows if r.kind == query.REGULAR]
    shown = regular[:limit]
    hidden = regular[limit:]
    if hidden:
        shown.append(query.Row("+%d more rows" % len(hidden), sum(r.mass for r in hidden),
                               sum(r.count for r in hidden), query.REGULAR))
    shown += [r for r in table.rows if r.kind != query.REGULAR]
    labels = [_label(r) for r in shown]
    width = max(len(label) for label in labels + [title])
    share = "share of %s" % _num(table.base) if table.base else "share"
    lines = ["%-*s  %16s  %7s  %s" % (width, title, unit, "count", share)]
    for label, r in zip(labels, shown):
        lines.append("%-*s  %16s  %7d  %*s" % (
            width, label, _num(r.mass), r.count, len(share),
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
                    key=lambda f: -f.metrics[metric])[:limit]
    lines = ["%16s  file:line  uuid  dimensions" % spec.unit]
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
        "reconciliation over %d windows: %s = %s; final occupancy %s: %s"
        % (r.windows, terms, _num(r.booked), _num(r.final_occupancy),
           _status(r.mass_holds)),
        "intervals %d (= %d calls - %d windows): exact %s + ambiguous %s [%s] + shrink %s: %s"
        % (r.intervals, r.calls, r.windows, rate(r.exact), rate(r.ambiguous),
           reasons or "none", rate(r.shrink), _status(r.count_holds)),
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


def footer(view: View, sel: Selection) -> Tuple[List[str], bool]:
    """The closing lines and whether the reconciliation held."""
    if not view.reconciles:
        return _call_totals(sel, view.metric), True
    reconciliation = query.reconcile(sel.window_facts)
    if sel.drill:
        return ["reconciliation: applies to the %d whole windows above, not to this"
                " drill: %s" % (sel.n_windows, _status(reconciliation.holds))], \
               reconciliation.holds
    return _reconciliation(reconciliation), reconciliation.holds
