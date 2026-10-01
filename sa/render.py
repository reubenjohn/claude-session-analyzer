"""Plain-text rendering of a selection: headline, population, tables, leaves,
footer. The tables are grouped here from the selection's facts; its total
and reconciliation come with it, so nothing here decides the exit status."""
from pathlib import Path
from typing import List, NamedTuple, Optional, Tuple

from . import query, schema
from .corpus import Corpus
from .query import Selection
from .schema import Fact
from .tables import at, count, leaves, num, pct, table


class View(NamedTuple):
    """The shape of one report: which metric, which tables by default, and
    whether the total is the windows' final occupancies, which the footer
    then checks."""
    metric: str
    tables: Tuple[str, ...]  # printed by default
    levers: Tuple[str, ...]  # the headline walks down these, general to specific (``_top``)
    reconciles: bool
    notes: Tuple[str, ...]   # printed under the headline


def _status(holds: bool) -> str:
    return "OK" if holds else "MISMATCH"


def report(view: View, sel: Selection, loaded: Corpus, root: Path, since: Optional[float],
           by: Optional[str], limit: int) -> List[str]:
    """Every line of the view: the headline, the population lines, the
    default tables a pin left open (``--by`` one dimension's table with its
    labels whole, or the leaves for ``fact``) and the footer."""
    spec = schema.metric(view.metric)
    if by == "fact":
        body = leaves(sel.facts, view.metric, limit)
    else:
        dims = [by] if by else _open(sel, view.tables, spec.carrier)
        tables = [query.group(sel.facts, dim, view.metric) for dim in dims]
        body = [line for t in tables if t.rows
                for line in table(t, view.metric, limit, whole=bool(by)) + [""]]
    return (headline(view, sel) + population(view, sel, loaded, root, since) + [""]
            + body + footer(view, sel))


def _open(sel: Selection, dims: Tuple[str, ...], carrier: str) -> List[str]:
    """The dimensions a ``--where`` pin left open: all when nothing is
    pinned, else those whose carrier facts do not all share one value (a
    pinned head implies its tool, a pinned window its agent, session and
    project): a table or lever over one value only repeats the filter."""
    if not sel.where:
        return list(dims)
    return [dim for dim in dims
            if len({f.dims.get(dim) for f in sel.facts if f.kind == carrier}) != 1]


def headline(view: View, sel: Selection) -> List[str]:
    """The total, how it was taken, and the lever walk, whatever ``--by``
    shows: a category (``cause``) or a population row (a window dimension)
    is never the answer (D-HEADLINE-SPECIFIC as amended)."""
    spec = schema.metric(view.metric)
    line = "%s: %s %s" % (view.metric, num(sel.total), spec.unit)
    if view.reconciles and not sel.drill:
        line += " = the " + count(sel.n_windows, "window's final occupancy",
                                   "windows' final occupancies summed")
    else:
        line += " " + _over(sel, spec.carrier)
    levers = _open(sel, view.levers, spec.carrier)
    return [line + _top(sel.facts, levers, view.metric, sel.total)] + _peaks(sel) + list(view.notes)


def _over(sel: Selection, carrier: str) -> str:
    """``over N <carrier> facts [where <drill pins>] in M windows``, M of
    the selection's when a drill shows fewer. The drill pins are named
    here only: this is the one count they narrow."""
    shown, windows = query.window_count(sel.facts), count(sel.n_windows, "window")
    if shown != sel.n_windows:
        windows = "%s of %s" % (num(shown), windows)
    facts = count(sum(f.kind == carrier for f in sel.facts), carrier + " fact")
    return "over %s%s in %s" % (facts, _pins(sel.drill), windows)


def _pins(pairs: List[Tuple[str, str]]) -> str:
    """`` where dim=value ...`` for the pairs, or nothing."""
    return " where " + " ".join("%s=%s" % p for p in pairs) if pairs else ""


def _largest(table: query.Table) -> Optional[query.Row]:
    """The largest regular row: the first, the rows being sorted by mass."""
    return next((r for r in table.rows if r.kind == query.REGULAR), None)


def _top(facts: List[Fact], levers: List[str], metric: str, total: float) -> str:
    """The first lever's largest row with its share of the headline total,
    named as such (a table's share column is over its base, which the
    residual and signed rows make smaller). Each next lever refines the
    row before: the largest row over that row's facts alone, with its share
    of that row and of the total (``within it head=Bash:cat 60 (66.7% of
    Bash, 61.2% of the total)``); when a row of the lever elsewhere is
    strictly larger, it follows with what it lies under (``top head=Read:py
    70 (41.2% of the total) under tool=Read``), never silent. A lever with
    no regular row ends the walk."""
    if not total or not levers:
        return ""
    top = _largest(query.group(facts, levers[0], metric))
    if top is None:
        return ""
    text = "; top %s=%s %s (%s of the %s total)" % (
        levers[0], top.value, num(top.mass), pct(top.mass / total), num(total))
    lead = query.select(facts, [(levers[0], top.value)])
    for above, dim in zip(levers, levers[1:]):
        within = _largest(query.group(lead, dim, metric))
        if within is None:
            break
        text += "; within it %s=%s %s (%s of %s, %s of the total)" % (
            dim, within.value, num(within.mass), pct(within.mass / top.mass if top.mass else None),
            top.value, pct(within.mass / total))
        overall = _largest(query.group(facts, dim, metric))
        if overall.mass > within.mass:
            # Exact: a head implies its tool (walk books it only beside one); a lever
            # spanning several upper values would silently get the largest here.
            under = query.values(query.select(facts, [(dim, overall.value)]), above, metric)[0]
            text += "; top %s=%s %s (%s of the total) under %s=%s" % (
                dim, overall.value, num(overall.mass), pct(overall.mass / total), above, under)
        top, lead = within, query.select(lead, [(dim, within.value)])
    return text


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
                             % (name, count(sel.n_windows, "whole window"),
                                num(top.metrics[name]), spec.unit, at(top.locator)))
    return lines


def population(view: View, sel: Selection, loaded: Corpus, root: Path,
               since: Optional[float]) -> List[str]:
    """Each count beside the population it was taken over: the read (the
    root, the files ``--since`` kept, what the read skipped or excluded,
    corpus-wide) and what the window pins kept: the windows (the files
    with a call, which is why they are fewer than the files read) and the
    facts the view's metric is read from, its carrier's. A drill pin is
    named on the headline, the one line that counts what it narrows."""
    carrier = schema.metric(view.metric).carrier
    return ["read: root %s, %s%s, %s skipped, %s excluded"
            % (root, count(len(loaded.files), "file"),
               "" if since is None else " (modified within %gd)" % since,
               count(loaded.skipped_lines, "line"),
               count(loaded.duplicate_records, "duplicate record")),
            "kept%s: %s, %s"
            % (_pins(sel.window_where),
               count(sel.n_windows, "window (a file with a call)", "windows (files with a call)"),
               count(sum(f.kind == carrier for f in sel.window_facts), carrier + " fact"))]


def _reconciliation(r: query.Reconciliation) -> List[str]:
    terms = " + ".join("%s %s" % (c, num(r.by_cause[c])) for c in schema.CAUSES)
    reasons = ", ".join("%s %s" % (k, num(v)) for k, v in r.by_reason.items() if v)

    def rate(n: int) -> str:
        return "%s (%.1f%%)" % (num(n), 100.0 * n / r.intervals) if r.intervals else "0"
    return [
        "reconciliation over %s: %s = %s; final occupancy %s: %s; holds by construction"
        " (walk.py), so a mismatch is a bug in this tool"
        % (count(r.windows, "window"), terms, num(r.booked), num(r.final_occupancy),
           _status(r.mass_holds)),
        "intervals %s (= %s - %s): exact %s + ambiguous %s [%s] + shrink %s: %s"
        % (num(r.intervals), count(r.calls, "call"), count(r.windows, "window"), rate(r.exact),
           rate(r.ambiguous), reasons or "none", rate(r.shrink), _status(r.count_holds)),
        "exact: the interval's one token-relevant contributor (a tool_result or user"
        " text) after subtracting the previous call's output. Exact given the"
        " feed-forward model; bookkeeping attachments are folded into the single"
        " contributor's remainder.",
    ]


def footer(view: View, sel: Selection) -> List[str]:
    """The closing lines: the reconciliation in full, as a pointer when a
    drill is shown above it, or, for a view that does not reconcile, every
    other additive call total over the population named."""
    if not view.reconciles:
        return ["%s: %s %s %s" % (name, num(query.total(sel.facts, name)), spec.unit,
                                  _over(sel, schema.CALL))
                for name, spec in schema.METRICS.items()
                if spec.carrier == schema.CALL and spec.aggregation == schema.ADDITIVE
                and name != view.metric]
    if sel.drill:
        return ["reconciliation: applies to the %s above, not to this drill: %s"
                % (count(sel.n_windows, "whole window"), _status(sel.reconciliation.holds))]
    return _reconciliation(sel.reconciliation)
