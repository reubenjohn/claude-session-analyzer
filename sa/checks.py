"""The checks, last (UX_PRINCIPLES 2, 3): ALWAYS a ``✓`` line saying what
is checked, in plain words, printed only over arithmetic that reconciles;
ON REQUEST (``-v``) that arithmetic as a vertical worked equation in the
run's own numbers; ON TRIGGER a short line per material uncertainty, and
the reconciliation in full when it fails (exit 1, decided by the selection, never here).

Context checks the two identities ``walk`` holds by construction, over
whole windows: each change times the calls that held it, over the calls,
is the mean measured call size; the tokens added less the shrinks are the
final window sizes; and the calls after their window's first (calls -
windows) split into one source, ambiguous and shrank, the measured rates
``-v`` prints. ALWAYS too, the ambiguous share of the average: what could
not be traced, with its base. Material, a ``!`` line of its own: an
``ambiguous`` share of the average at or above ``AMBIGUOUS_MATERIAL``, or a
``shrink`` at or beyond ``SHRINK_MATERIAL`` (of the average before shrink,
the cause table's ``= 100%`` row, whole windows), each with the command
that shows those changes, the pins kept; none when the cause is pinned.

Spend reconciles no window, so it checks what it prints, as its one line:
each table's rows, its catch-all and signed rows included, sum to the
headline, in the screen's own numbers."""
from typing import Callable, List, Optional, Sequence, Tuple

from . import glossary, query, reconciliation, residual, schema, style, tables
from .query import Selection
from .tables import count, num

AMBIGUOUS_MATERIAL = 0.10  # of the average before shrink: an ambiguous share worth its own line
SHRINK_MATERIAL = 0.01     # likewise, |shrink|
OK = "%s numbers add up" % tables.OK_MARK
INDENT = "  "


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
    """The reconciliation's unit, in calls: each call after its window's
    first grew (or shrank) from the one before, so a window of N calls has
    N - 1; one such step can book two changes."""
    return count(n, "call") + " after their window's first"


def _rate(r: reconciliation.Reconciliation, n: int) -> str:
    return "%s (%.1f%%)" % (num(n), 100.0 * n / r.intervals) if r.intervals else "0"


def _worked(rows: Sequence[Tuple[str, str, str]]) -> List[str]:
    """A vertical equation: labels left, figures right-aligned in one
    column, each line's verdict after it."""
    width = max(len(label) for label, _, _ in rows)
    figures = max(len(figure) for _, figure, _ in rows)
    return [style.tag(("%s%-*s  %*s  %s" % (INDENT, width, label, figures, figure, after)).rstrip(), style.KEY)
            for label, figure, after in rows]


def context(sel: Selection, more: Optional[Callable[[str], str]] = None) -> Tuple[List[str], List[str]]:
    """The context view's lines (what is checked, in plain words; the
    ambiguous share of the average, with its trigger) and its ``-v``
    worked equation; a failed reconciliation in full instead."""
    r = sel.reconciliation
    if not r.holds:
        return _reconciliation(r), []
    lines = [style.tag("%s over %s in view: rows to the average call, changes to window sizes" % (
        OK, count(sel.n_windows, "window")), style.GOOD)] + _material(sel, more)
    shrink = r.by_cause[schema.SHRINK]
    added = ("context tokens added %s - %s %s" % (num(r.booked - shrink), schema.SHRINK, num(-shrink)) if shrink
             else "context tokens added")
    split = " + ".join("%s %s" % (what, name) for what, name in (
        (_rate(r, r.exact), "one source"), (num(r.ambiguous), schema.AMBIGUOUS), (num(r.shrink), "shrank")))
    worked = _worked([
        ("each change × the calls that held it", num(r.held), ""),
        ("÷ calls in view", num(r.calls), ""),
        ("= %s" % tables.TOTAL_LABEL[2:], num(r.held / max(r.calls, 1)),
         "%s same as the mean measured call size" % tables.OK_MARK),
        (added, "= " + num(r.booked), "%s same as the final window sizes" % tables.OK_MARK)])
    worked += [style.tag(line, style.KEY) for line in (
        "%s%s = %s - %s" % (INDENT, gaps(r.intervals), count(r.calls, "call"), count(r.windows, "window")),
        "%s  = %s  %s" % (INDENT, split, tables.OK_MARK))]
    return lines, worked


def _material(sel: Selection, more: Optional[Callable[[str], str]]) -> List[str]:
    """ALWAYS the ambiguous share of the whole windows' average (the cause
    table's, the answer to "what could not be traced"); ON TRIGGER, it or
    a shrink at or beyond its threshold, ``!`` and the command that shows
    what it holds (``more``, given the cause; none when the cause is pinned)."""
    held = {}
    for f in sel.window_facts:
        if f.kind == schema.INCREMENT:
            cause = f.dims.get(schema.CAUSE_DIM)
            held[cause] = held.get(cause, 0) + f.metrics.get(schema.CONTEXT_HELD, 0)
    base = sum(m for c, m in held.items() if c != schema.SHRINK)
    lines = []
    for cause, floor in ((schema.AMBIGUOUS, AMBIGUOUS_MATERIAL), (schema.SHRINK, SHRINK_MATERIAL)):
        share = held.get(cause, 0) / base if base else 0
        hit = abs(share) >= floor
        if not (hit or cause == schema.AMBIGUOUS and share):
            continue
        lines.append("%s%s: %s of the average call%s" % (INDENT, cause, tables.pct(share), (
            ", not traced to one source" if cause == schema.AMBIGUOUS else "")))
        if hit and more:
            lines += [style.tag(line, style.HINT) for line in tables.command_lines("%s! %s %s%.0f%%: " % (
                INDENT, "over" if share > 0 else "beyond", "" if share > 0 else "-", 100 * floor), more(cause))]
    return lines


def spend(sel: Selection, shown: Sequence[query.Table]) -> Tuple[List[str], List[str]]:
    """The spend view's line, and per table shown, its rows summed against
    the headline: a ``✓`` only where the printed figures add up."""
    if not shown:
        return [], []
    worked, holds = [], True
    for grouped in shown:
        regular = sum(r.mass for r in grouped.rows if r.kind == query.REGULAR)
        others = [(r, r.value) for r in grouped.rows if r.kind != query.REGULAR]
        total = regular + sum(r.mass for r, _ in others)
        ok = num(total) == num(sel.total)
        holds = holds and ok
        terms = ["%s %s" % (tables.BASE_LABEL, num(regular))] + [
            "%s %s" % (residual.label(grouped.dim) if r.kind == query.RESIDUAL else v, num(r.mass)) for r, v in others]
        worked.append(style.tag("%s%s: %s = %s %s  %s" % (
            INDENT, tables.title(grouped.dim), " + ".join(terms), glossary.printed(schema.SPEND), num(total),
            "%s the headline's" % tables.OK_MARK if ok else "%s not the headline's %s" % (
                tables.BAD_MARK, num(sel.total))), style.KEY))
    if not holds:
        return [style.tag(line.strip(), style.BAD) for line in worked], []
    return [style.tag("%s: %s" % (OK, line.strip().split(": ", 1)[1].rsplit("  ", 1)[0]), style.GOOD)
            for line in worked], []
