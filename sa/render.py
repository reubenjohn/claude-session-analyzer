"""Plain-text rendering of a selection, in reading order: scope (the
population), answer (headline, lever walk, peak), tables or leaves, one key,
checks. The tables are grouped here from the selection's facts; its total
and reconciliation come with it, so nothing here decides the exit status."""
from typing import List, NamedTuple, Optional, Tuple

from . import headline, query, schema, tables, windows
from .corpus import Corpus
from .query import Selection
from .headline import INHERITED_LABEL
from .tables import count, leaves, num, table

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
    starts: Optional[str] = None  # the dimension the starting context splits by; None: no such line


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
    totalled = False  # whether a cause table printed its total row
    if by == FACT:
        body = leaves(sel.facts, view.metric, limit) + [""]
    else:
        dims = [by] if by else headline.open_dims(sel, view.tables, spec.carrier)
        body = []
        for dim in dims:
            grouped = query.group(sel.facts, dim, view.metric)
            if grouped.rows:
                total = _total(view, sel) if dim == schema.CAUSE_DIM else None
                totalled = totalled or total is not None
                body += table(grouped, view.metric, limit, whole=bool(by), total=total) + [""]
                notes += tables.notes(grouped)
    keyed = tables.key(notes)
    return (population(view, sel, loaded, since_default) + [""] + headline.headline(view, sel) + [""]
            + body + keyed + ([""] if keyed else []) + footer(view, sel, totalled))


def _total(view: View, sel: Selection) -> Optional[str]:
    """The cause table's closing text: the booked total against the final
    sizes, for a whole-window view that reconciles; no drill has one."""
    if not view.reconciles or sel.drill:
        return None
    if sel.reconciliation.mass_holds:
        return "%s matches the final window sizes%s" % (tables.OK_MARK, headline.less(sel))
    return "%s does not match the final window sizes (below)" % tables.BAD_MARK


def population(view: View, sel: Selection, loaded: Corpus, since_default: bool = False) -> List[str]:
    """The scope, first: the read (the files its ``--since`` kept, named
    with that window and the root, then what the read skipped or excluded,
    corpus-wide) and what the window pins kept: the windows (the files with
    a call; a compaction a call follows starts another) and the facts
    the view's metric is read from, its carrier's. The compactions read
    print as one line when there are any: every one is unpriced. A drill pin
    is named on the headline, the one line that counts what it narrows."""
    carrier, _window = schema.metric(view.metric).carrier, schema.WINDOW_DIM
    since = ("of any age" if loaded.since_days is None else "modified in the last %gd%s"
             % (loaded.since_days, " (default)" if since_default else ""))
    marks = windows.compactions(loaded)
    compacted = ["      %s unpriced: %s started a window, %s ended their file"
                 % (count(sum(marks.values()), "compaction"), num(marks["started"]), num(marks["ended"]))
                 ] if marks else []
    return ["read: %s %s under %s" % (count(len(loaded.files), "file"), since, tables.tilde(loaded.root)),
            "      %s skipped, %s excluded" % (count(loaded.skipped_lines, "line"),
                                              count(loaded.duplicate_records, "duplicate record"))
            ] + compacted + [
            "kept%s: %s, %s"
            % (headline.pins(sel.window_where), count(sel.n_windows, tables.marked(_window), _window + "s"
                                              + schema.MARKER),
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


def _checks(r: query.Reconciliation, totalled: bool, scope: str = "") -> str:
    """The one line a holding reconciliation prints, a drill and ``--by
    fact`` included: the intervals split into exact, ambiguous and shrink,
    each with its rate (R4), and the booked total against the final sizes
    unless a cause table's total row already said it. ``scope`` names the
    whole windows a drill sits in."""
    mass = "" if totalled else "%s booked = the final window sizes; " % num(r.booked)
    return tables.styled("%s checks%s: %s%s intervals (%s - %s) = exact %s + ambiguous %s + shrink %s"
                         % (tables.OK_MARK, scope, mass, num(r.intervals), count(r.calls, "call"),
                            count(r.windows, "window"), _rate(r, r.exact), _rate(r, r.ambiguous),
                            _rate(r, r.shrink)), tables.GOOD)


def footer(view: View, sel: Selection, totalled: bool = False) -> List[str]:
    """The closing lines: for a view that reconciles, one checks line when
    the reconciliation holds (over the whole windows when a drill is shown)
    and the reconciliation in full when it fails; for one that does not,
    every other additive call total over the population named.
    ``totalled``: a cause table above printed its total row, so the checks
    need not repeat the booked total; whatever printed, the mass is stated.
    Inherited mass its parent window counts closes it, one line, never
    hidden and never in a share (D-INHERITED-ONCE)."""
    if not view.reconciles:
        return ["%s: %s %s %s" % (name, num(query.total(sel.facts, name)), spec.unit,
                                  headline.over(sel, schema.CALL))
                for name, spec in schema.METRICS.items()
                if spec.carrier == schema.CALL and spec.aggregation == schema.ADDITIVE
                and name != view.metric]
    r = sel.reconciliation
    if not r.holds:
        return _reconciliation(r)
    scope = (" over the %s (a drill is not reconciled)" % count(sel.n_windows, "whole window")
             if sel.drill else "")
    once = (["%s: %s %s in %s, in their checks, not the total"
             % (INHERITED_LABEL, num(headline.inherited(sel)), schema.metric(view.metric).unit,
                count(len(sel.inherited), "window"))] if sel.inherited else [])
    return [_checks(r, totalled, scope)] + once
