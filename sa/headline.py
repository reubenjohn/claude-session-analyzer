"""The answer, under the scope: the total and how it was taken, then the
starting context by what started each window and the growth walked down
the view's levers (D-HEADLINE-TWO-LINES), then the single-call peak. A
``--where`` pin omits every lever whose facts all share one value."""
from typing import List, Optional, Tuple

from . import query, schema, tables
from .query import Selection
from .schema import Fact
from .tables import at, count, num, pct


def open_dims(sel: Selection, dims: Tuple[str, ...], carrier: str) -> List[str]:
    """The dimensions a ``--where`` pin left open: all when nothing is
    pinned, else those whose carrier facts do not all share one value (a
    pinned head implies its tool, a pinned window its agent, session and
    project): a table or lever over one value only repeats the filter."""
    if not sel.where:
        return list(dims)
    return [dim for dim in dims
            if len({f.dims.get(dim) for f in sel.facts if f.kind == carrier}) != 1]


def headline(view, sel: Selection, forest: List[Fact] = ()) -> List[str]:
    """The total and how it was taken, then two lines over that one total
    (D-HEADLINE-TWO-LINES): the starting context by what started each
    window, then the growth walked down the view's levers, whatever ``--by``
    shows: a category (``cause``) or a population row is never the answer
    (D-HEADLINE-SPECIFIC as amended). Shares are of the mass added: the
    signed rows stay out of them, as out of every table's. A pinned window
    that inherited shows each copy's breakdown in its parent (``copied``)."""
    spec = schema.metric(view.metric)
    line = "%s: %s %s" % (view.metric, num(sel.total), spec.unit)
    if not view.reconciles or sel.drill:
        line += " " + over(sel, spec.carrier)
    elif sel.reconciliation.mass_holds:
        line += " = the " + count(sel.n_windows, "window's final occupancy",
                                   "windows' final occupancies summed") + less(sel)
    else:
        line += " booked over %s (reconciliation MISMATCH below)" % count(sel.n_windows, "window")
    carried = [f for f in sel.facts if f.kind == spec.carrier]
    added = sel.total - query.total([f for f in carried if f.dims.get(schema.CAUSE_DIM) == schema.SHRINK],
                                    view.metric)
    word = "added" if added != sel.total else "total"
    base, out = "%s %s" % (num(added), word), []  # the base's figure, until a line names it
    starting = [f for f in carried if f.dims.get(schema.CAUSE_DIM) in STARTING] if view.starts else []
    mass = query.total(starting, view.metric)
    if starting and added:
        text = "starting context %s (%s of the %s) entered as windows started, not a window size" % (
            num(mass), pct(mass / added), base)
        if open_dims(sel, (view.starts,), spec.carrier):
            text += ": " + ", ".join("%s %s" % (r.value, num(r.mass)) for r in
                                     query.group(starting, view.starts, view.metric).rows
                                     if r.kind == query.REGULAR)
        out += [text] + copied(sel, forest)
        base = word
    walk = []
    if out and added - mass:  # growth is stated beside a starting context only
        walk, base = ["growth %s (%s of the %s)" % (num(added - mass), pct((added - mass) / added), base)], word
    walk += _top(sel.facts, open_dims(sel, view.levers, spec.carrier), view.metric, added, word,
                 named=base == word)
    return ([tables.styled(line, tables.BOLD)] + ["  " + t for t in out + (["; ".join(walk)] if walk else [])]
            + _peaks(sel))


def copied(sel: Selection, forest: List[Fact]) -> List[str]:
    """Under a ``--where window=`` pin, each inherited increment counted
    here, as its parent window's exact breakdown by tool through the branch
    call, signed rows included, found by reference (D-FORK-INHERITED)."""
    if schema.WINDOW_DIM not in dict(sel.window_where):
        return []
    lines = []
    for f in sel.facts:
        if f.dims.get(schema.CAUSE_DIM) == schema.INHERITED:
            key, call = f.evidence[schema.PARENT_WINDOW], f.evidence[schema.BRANCH_CALL]
            rows = query.group(query.through(forest, key, call), schema.TOOL_DIM, schema.CONTEXT_DELTA).rows
            lines.append("  %s %s copied from %s=%s through %s, by tool: %s" % (
                schema.INHERITED, num(f.metrics[schema.CONTEXT_DELTA]), schema.WINDOW_DIM,
                schema.window_value(key), at(call), ", ".join(
                    "%s %s" % (tables.RESIDUAL_LABEL if r.kind == query.RESIDUAL else r.value, num(r.mass))
                    for r in rows)))
    return lines


STARTING = (schema.WINDOW_HEAD, schema.INHERITED)  # the causes that enter as a window starts


def inherited(sel: Selection) -> float:
    return sum(f.metrics[schema.CONTEXT_DELTA] for f in sel.inherited)


def less(sel: Selection) -> str:
    """What the total leaves out of the final sizes it is stated against:
    the inherited mass its parent windows already count (D-INHERITED-ONCE)."""
    return " less %s %s" % (num(inherited(sel)), INHERITED_LABEL) if sel.inherited else ""


INHERITED_LABEL = "%s (counted in parent)" % schema.INHERITED


def over(sel: Selection, carrier: str) -> str:
    """``over N <carrier> facts [where <drill pins>] in M windows``, M of
    the selection's when a drill shows fewer. The drill pins are named
    here only: this is the one count they narrow."""
    shown, windows = query.window_count(sel.facts), count(sel.n_windows, "window")
    if shown != sel.n_windows:
        windows = "%s of %s" % (num(shown), windows)
    facts = count(sum(f.kind == carrier for f in sel.facts), carrier + " fact")
    return "over %s%s in %s" % (facts, pins(sel.drill), windows)


def pins(pairs: List[Tuple[str, str]]) -> str:
    """`` where dim=value ...`` for the pairs, or nothing."""
    return " where " + " ".join("%s=%s" % (d, tables.home(v)) for d, v in pairs) if pairs else ""


def _largest(table: query.Table) -> Optional[query.Row]:
    """The largest regular row: the first, the rows being sorted by mass."""
    return next((r for r in table.rows if r.kind == query.REGULAR), None)


def _top(facts: List[Fact], levers: List[str], metric: str, total: float, word: str = "total",
         named: bool = False) -> List[str]:
    """The first lever's largest row with its share of the headline total,
    named as such (a table's share column is over its base, which the
    residual and signed rows make smaller). Each next lever refines the
    row before: the largest row over that row's facts alone, with its share
    of that row and of the total (``within it head=Bash:cat 60 (66.7% of
    Bash, 61.2% of the total)``); when a row of the lever elsewhere is
    strictly larger, it follows with what it lies under (``top head=Read:py
    70 (41.2% of the total) under tool=Read``), never silent. A row with
    none of the lever within it (a top tool with no head: Agent, MCP tools)
    still has the largest row elsewhere named, then ends the walk. Each
    clause is one string. ``total`` is the share base, ``word`` names it,
    with its figure unless a line above already ``named`` it."""
    if not total or not levers:
        return []
    top = _largest(query.group(facts, levers[0], metric))
    if top is None:
        return []
    base = word if named else "%s %s" % (num(total), word)
    text = ["top %s=%s %s (%s of the %s)" % (levers[0], top.value, num(top.mass), pct(top.mass / total), base)]
    lead = query.select(facts, [(levers[0], top.value)])
    for above, dim in zip(levers, levers[1:]):
        within = _largest(query.group(lead, dim, metric))
        if within is not None:
            text.append("within it %s=%s %s (%s of %s, %s of the %s)" % (
                dim, within.value, num(within.mass), pct(within.mass / top.mass if top.mass else None),
                top.value, pct(within.mass / total), word))
        overall = _largest(query.group(facts, dim, metric))
        if overall is not None and overall.mass > (within.mass if within else 0):
            # A lever's value implies one value of the lever above (a head its tool,
            # as walk books it); a View whose levers do not nest fails to unpack here.
            (under,) = query.values(query.select(facts, [(dim, overall.value)]), above, metric)
            text.append("top %s=%s %s (%s of the %s) under %s=%s" % (
                dim, overall.value, num(overall.mass), pct(overall.mass / total), word, above, under))
        if within is None:
            break
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
