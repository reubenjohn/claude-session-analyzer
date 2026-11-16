"""The checks, last: the line that says the reconciliation held (each
change times the calls that held it against the calls' sizes, the tokens
added less the shrinks against the final window sizes, the gaps between
calls split by how each was booked), the reconciliation in full when it
fails; for a view that does not
reconcile, its other call totals. Nothing here decides the exit status:
the selection carries it."""
from typing import List

from . import glossary, headline, query, reconciliation, schema, style, tables
from .query import Selection
from .tables import count, num


def _status(holds: bool) -> str:
    return "OK" if holds else "MISMATCH"


def _reconciliation(r: reconciliation.Reconciliation) -> List[str]:
    """The reconciliation in full, printed only when it fails."""
    terms = " + ".join("%s %s" % (c, num(r.by_cause[c])) for c in schema.CAUSES)
    reasons = ", ".join("%s %s" % (k, num(v)) for k, v in r.by_reason.items() if v)
    return [style.tag(line, style.BAD) for line in [
        "%s reconciliation over %s: %s = %s; final occupancy %s: %s"
        % (tables.BAD_MARK, count(r.windows, "window"), terms, num(r.booked),
           num(r.final_occupancy), _status(r.mass_holds)),
        "%s held by calls %s, calls' sizes summed %s, %d of %d windows equal: %s"
        % (tables.BAD_MARK, num(r.held), num(r.occupancy), r.held_windows, r.windows,
           _status(r.held_holds)),
        "%s %s (= %s - %s): exact %s + ambiguous %s [%s] + shrink %s: %s"
        % (tables.BAD_MARK, gaps(r.intervals), count(r.calls, "call"), count(r.windows, "window"),
           _rate(r, r.exact), _rate(r, r.ambiguous), reasons or "none", _rate(r, r.shrink),
           _status(r.count_holds)),
        "it holds by construction (walk.py), so a mismatch is a bug in this tool"]]


def gaps(n: int) -> str:
    """The reconciliation's unit: one gap between two calls of a window, so
    a window of N calls has N - 1; a change is one booked part of a gap."""
    return count(n, "gap between calls", glossary.printed(glossary.GAP))


def _rate(r: reconciliation.Reconciliation, n: int) -> str:
    return "%s (%.1f%%)" % (num(n), 100.0 * n / r.intervals) if r.intervals else "0"


def _checks(r: reconciliation.Reconciliation, scope: str = "") -> str:
    """The one line a holding reconciliation prints, a drill and ``--by
    fact`` included: each change times the calls that held it, summed,
    against the calls' sizes summed (the average's rows against the mean
    call, D-PER-CALL); the tokens added less the shrinks against the final
    window sizes; then the gaps between calls (one fewer than a window's
    calls; a change is one booked part of a gap) split into those booked to
    one source (``exact``), ambiguous and shrank, each with its rate of the
    gaps (R4). ``scope`` names the whole windows a drill sits in."""
    shrink = r.by_cause[schema.SHRINK]
    held = "%s held by calls (each change x the calls that held it) = the calls' sizes summed" % num(r.held)
    mass = "%s added" % num(r.booked - shrink) + (
        " - %s %s = %s" % (num(-shrink), schema.SHRINK, num(r.booked)) if shrink else "") + (
        " = the final window sizes")
    split = ", ".join(_part(r, n, name) for n, name in ((r.exact, ONE_SOURCE), (
        r.ambiguous, schema.AMBIGUOUS), (r.shrink, SHRANK)))
    return style.tag("%s checks%s: %s; %s; %s (%s - %s): %s"
                     % (tables.OK_MARK, scope, held, mass, gaps(r.intervals), count(r.calls, "call"),
                        count(r.windows, "window"), split), style.GOOD)


ONE_SOURCE, SHRANK = "to one source", "shrank"  # the checks' plain words for exact and shrink gaps


def _part(r: reconciliation.Reconciliation, n: int, name: str) -> str:
    """``786 to one source (92.9% of gaps)``: the count first, so it reads
    as that many gaps, and the rate says its base, not the context's."""
    return "%s %s (%.1f%% of gaps)" % (num(n), name, 100.0 * n / r.intervals) if r.intervals else "0 " + name


def footer(view, sel: Selection) -> List[str]:
    """The closing lines: for a view that reconciles, one checks line when
    the reconciliation holds (over the whole windows when a drill is shown)
    and the reconciliation in full when it fails; for one that does not,
    every other additive call total over the population named."""
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
    return [_checks(r, scope)]
