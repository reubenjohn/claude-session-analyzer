"""Plain-text rendering of a selection, in reading order: scope (the
population), answer (headline, lever walk, peak), tables or leaves, one key,
checks. The tables are grouped here from the selection's facts; its total
and reconciliation come with it, so nothing here decides the exit status."""
from typing import List, NamedTuple, Optional, Tuple

from . import query, schema, tables
from .corpus import Corpus
from .query import Selection
from .schema import Fact
from .tables import at, count, leaves, num, pct, table

FACT = "fact"  # the ``--by`` that prints the leaves, not a table


class View(NamedTuple):
    """The shape of one report: which metric, which tables by default, and
    whether the total is the windows' final occupancies, which the footer
    then checks."""
    metric: str
    tables: Tuple[str, ...]  # printed by default
    levers: Tuple[str, ...]  # the headline walks down these; a value lies under one of the lever above
    reconciles: bool
    notes: Tuple[str, ...]   # printed in the key, under the view's metric


def report(view: View, sel: Selection, loaded: Corpus, by: Optional[str], limit: int,
           since_default: bool = False) -> List[str]:
    """Every line of the view, in reading order: the scope (what was read
    and kept), the answer (the headline and its lever walk, the peak), the
    tables a pin left open (``--by`` one dimension's table with its labels
    whole, or the leaves for ``fact``), one key for every note they call
    for, and the checks. The cause table of a whole-window view closes with
    its total against the windows' final sizes."""
    spec = schema.metric(view.metric)
    notes: List[Tuple[str, str]] = [(view.metric, n) for n in view.notes]
    if by == FACT:
        body = leaves(sel.facts, view.metric, limit) + [""]
    else:
        dims = [by] if by else _open(sel, view.tables, spec.carrier)
        body = []
        for dim in dims:
            grouped = query.group(sel.facts, dim, view.metric)
            if grouped.rows:
                body += table(grouped, view.metric, limit, whole=bool(by),
                              total=_total(view, sel) if dim == schema.CAUSE_DIM else None) + [""]
                notes += tables.notes(grouped)
    keyed = tables.key(notes)
    return (population(view, sel, loaded, since_default) + [""] + headline(view, sel) + [""]
            + body + keyed + ([""] if keyed else []) + footer(view, sel, by))


def _total(view: View, sel: Selection) -> Optional[str]:
    """The cause table's closing text: the booked total against the final
    sizes, for a whole-window view that reconciles; no drill has one."""
    if not view.reconciles or sel.drill:
        return None
    if sel.reconciliation.mass_holds:
        return "%s matches the final window sizes" % tables.OK_MARK
    return "%s does not match the final window sizes (below)" % tables.BAD_MARK


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
    is never the answer (D-HEADLINE-SPECIFIC as amended). Each lever's
    clause is a line of its own, indented under the total."""
    spec = schema.metric(view.metric)
    line = "%s: %s %s" % (view.metric, num(sel.total), spec.unit)
    if not view.reconciles or sel.drill:
        line += " " + _over(sel, spec.carrier)
    elif sel.reconciliation.mass_holds:
        line += " = the " + count(sel.n_windows, "window's final occupancy",
                                   "windows' final occupancies summed")
    else:
        line += " booked over %s (reconciliation MISMATCH below)" % count(sel.n_windows, "window")
    levers = _open(sel, view.levers, spec.carrier)
    return ([tables.styled(line, tables.BOLD)]
            + ["  " + clause for clause in _top(sel.facts, levers, view.metric, sel.total)]
            + _peaks(sel))


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


def _top(facts: List[Fact], levers: List[str], metric: str, total: float) -> List[str]:
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
    clause is one string."""
    if not total or not levers:
        return []
    top = _largest(query.group(facts, levers[0], metric))
    if top is None:
        return []
    text = ["top %s=%s %s (%s of the %s total)" % (
        levers[0], top.value, num(top.mass), pct(top.mass / total), num(total))]
    lead = query.select(facts, [(levers[0], top.value)])
    for above, dim in zip(levers, levers[1:]):
        within = _largest(query.group(lead, dim, metric))
        if within is not None:
            text.append("within it %s=%s %s (%s of %s, %s of the total)" % (
                dim, within.value, num(within.mass), pct(within.mass / top.mass if top.mass else None),
                top.value, pct(within.mass / total)))
        overall = _largest(query.group(facts, dim, metric))
        if overall is not None and overall.mass > (within.mass if within else 0):
            # A lever's value implies one value of the lever above (a head its tool,
            # as walk books it); a View whose levers do not nest fails to unpack here.
            (under,) = query.values(query.select(facts, [(dim, overall.value)]), above, metric)
            text.append("top %s=%s %s (%s of the total) under %s=%s" % (
                dim, overall.value, num(overall.mass), pct(overall.mass / total), above, under))
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


def population(view: View, sel: Selection, loaded: Corpus, since_default: bool = False) -> List[str]:
    """The scope, first: the read (the files its ``--since`` kept, named
    with that window and the root, then what the read skipped or excluded,
    corpus-wide) and what the window pins kept: the windows (the files with
    a call, which is why they are fewer than the files read) and the facts
    the view's metric is read from, its carrier's. A drill pin is named on
    the headline, the one line that counts what it narrows."""
    carrier, _window = schema.metric(view.metric).carrier, schema.WINDOW_DIM
    since = ("of any age" if loaded.since_days is None else "modified in the last %gd%s"
             % (loaded.since_days, " (default)" if since_default else ""))
    return ["read: %s %s under %s" % (count(len(loaded.files), "file"), since, tables.tilde(loaded.root)),
            "      %s skipped, %s excluded" % (count(loaded.skipped_lines, "line"),
                                              count(loaded.duplicate_records, "duplicate record")),
            "kept%s: %s, %s"
            % (_pins(sel.window_where),
               count(sel.n_windows, tables.marked(_window) + " (a file with a call)", _window + "s"
                     + schema.MARKER + " (files with a call)"),
               count(sum(f.kind == carrier for f in sel.window_facts), carrier + " fact"))]


def _status(holds: bool) -> str:
    return "OK" if holds else "MISMATCH"


def _reconciliation(r: query.Reconciliation) -> List[str]:
    """The reconciliation in full, printed only when it fails."""
    terms = " + ".join("%s %s" % (c, num(r.by_cause[c])) for c in schema.CAUSES)
    reasons = ", ".join("%s %s" % (k, num(v)) for k, v in r.by_reason.items() if v)
    return [tables.styled(line, tables.BAD) for line in [
        "%s reconciliation over %s: %s = %s; final occupancy %s: %s"
        % (tables.BAD_MARK, count(r.windows, "window"), terms, num(r.booked),
           num(r.final_occupancy), _status(r.mass_holds)),
        "%s intervals %s (= %s - %s): exact %s + ambiguous %s [%s] + shrink %s: %s"
        % (tables.BAD_MARK, num(r.intervals), count(r.calls, "call"), count(r.windows, "window"),
           _rate(r, r.exact), _rate(r, r.ambiguous), reasons or "none", _rate(r, r.shrink),
           _status(r.count_holds)),
        "it holds by construction (walk.py), so a mismatch is a bug in this tool"]]


def _rate(r: query.Reconciliation, n: int) -> str:
    return "%s (%.1f%%)" % (num(n), 100.0 * n / r.intervals) if r.intervals else "0"


def _checks(r: query.Reconciliation, totalled: bool) -> str:
    """The one line a holding reconciliation prints: the intervals split
    into exact, ambiguous and shrink, each with its rate (R4), and the
    booked total against the final sizes unless the cause table's total
    row already said it."""
    mass = "" if totalled else "%s booked = the final window sizes; " % num(r.booked)
    return tables.styled("%s checks: %s%s intervals (%s - %s) = exact %s + ambiguous %s + shrink %s"
                         % (tables.OK_MARK, mass, num(r.intervals), count(r.calls, "call"),
                            count(r.windows, "window"), _rate(r, r.exact), _rate(r, r.ambiguous),
                            _rate(r, r.shrink)), tables.GOOD)


def footer(view: View, sel: Selection, by: Optional[str] = None) -> List[str]:
    """The closing lines: for a view that reconciles, one checks line when
    the reconciliation holds (a pointer when a drill is shown above it) and
    the reconciliation in full when it fails; for one that does not, every
    other additive call total over the population named."""
    if not view.reconciles:
        return ["%s: %s %s %s" % (name, num(query.total(sel.facts, name)), spec.unit,
                                  _over(sel, schema.CALL))
                for name, spec in schema.METRICS.items()
                if spec.carrier == schema.CALL and spec.aggregation == schema.ADDITIVE
                and name != view.metric]
    r = sel.reconciliation
    if not r.holds:
        return _reconciliation(r)
    if sel.drill:
        return [tables.styled("%s checks: hold over the %s above; a drill is not reconciled"
                              % (tables.OK_MARK, count(sel.n_windows, "whole window")), tables.GOOD)]
    shown = by == schema.CAUSE_DIM or (by is None and schema.CAUSE_DIM in view.tables)
    return [_checks(r, totalled=shown)]
