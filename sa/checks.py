"""The checks, last (UX_PRINCIPLES 2, 3): ALWAYS one line, a ``✓`` printed
only over arithmetic that reconciles; ON REQUEST (``-v``) that arithmetic
as a vertical worked equation in the run's own numbers; ON TRIGGER a short
line per material uncertainty, and the reconciliation in full when it
fails (exit 1, decided by the selection, never here).

Context checks the two identities ``walk`` holds by construction, over
whole windows: each change times the calls that held it, over the calls,
is the mean measured call size; the tokens added less the shrinks are the
final window sizes; and the gaps between calls (calls - windows) split
into one source, ambiguous and shrank. The one line names the measured
rate of gaps traced to one source. Material, a line of its own: an
``ambiguous`` share of the average at or above ``AMBIGUOUS_MATERIAL``, or a
``shrink`` at or beyond ``SHRINK_MATERIAL`` (of the average before shrink,
the cause table's ``= 100%`` row, whole windows), each with the command
that lists those changes.

Spend reconciles no window, so it checks what it prints: each table's
rows, its catch-all and signed rows included, sum to the headline."""
from typing import Callable, List, Optional, Sequence, Tuple

from . import glossary, query, reconciliation, residual, schema, style, tables
from .query import Selection
from .tables import count, num

AMBIGUOUS_MATERIAL = 0.10  # of the average before shrink: an ambiguous share worth its own line
SHRINK_MATERIAL = 0.01     # likewise, |shrink|
HOW = "  (-v: how it's checked)"
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
    """The reconciliation's unit: one gap between two calls of a window, so
    a window of N calls has N - 1; a change is one booked part of a gap."""
    return count(n, "gap between calls", glossary.printed(glossary.GAP))


def _rate(r: reconciliation.Reconciliation, n: int) -> str:
    return "%s (%.1f%%)" % (num(n), 100.0 * n / r.intervals) if r.intervals else "0"


def _line(text: str) -> str:
    """The one line, the ``-v`` pointer kept when the line has room: the
    same line with and without ``-v``, which only adds below it."""
    return text + (HOW if len(text) + len(HOW) < tables.WIDTH else "")


def _worked(rows: Sequence[Tuple[str, str, str]]) -> List[str]:
    """A vertical equation: labels left, figures right-aligned in one
    column, each line's verdict after it."""
    width = max(len(label) for label, _, _ in rows)
    figures = max(len(figure) for _, figure, _ in rows)
    return [style.tag(("%s%-*s  %*s  %s" % (INDENT, width, label, figures, figure, after)).rstrip(), style.KEY)
            for label, figure, after in rows]


def context(sel: Selection, more: Optional[Callable[[str], str]] = None) -> Tuple[List[str], List[str]]:
    """The context view's lines (the one line and any trigger lines) and
    its ``-v`` worked equation; a failed reconciliation in full instead."""
    r = sel.reconciliation
    if not r.holds:
        return _reconciliation(r), []
    scope = " over the %s" % count(sel.n_windows, "whole window") if sel.drill else ""
    rate = "%.1f%%" % (100.0 * r.exact / r.intervals) if r.intervals else "-"
    text = _line("%s%s · %s of %s traced to one source" % (OK, scope, rate, glossary.printed(glossary.GAP)))
    lines = [style.tag(text, style.GOOD)] + _material(sel, more)
    shrink = r.by_cause[schema.SHRINK]
    added = ("added %s - %s %s" % (num(r.booked - shrink), schema.SHRINK, num(-shrink)) if shrink
             else "tokens added")
    split = " + ".join("%s %s" % (num(n), name) for n, name in (
        (r.exact, "one source"), (r.ambiguous, schema.AMBIGUOUS), (r.shrink, "shrank")))
    worked = _worked([
        ("each change × the calls that held it", num(r.held), ""),
        ("÷ calls in view", num(r.calls), ""),
        ("= %s" % tables.TOTAL_LABEL[2:], num(r.held / max(r.calls, 1)),
         "%s same as the mean measured call size" % tables.OK_MARK),
        (added, "= " + num(r.booked), "%s same as the final window sizes" % tables.OK_MARK)])
    pad = INDENT + " " * (len(gaps(r.intervals)) + 1)
    worked += [style.tag(line, style.KEY) for line in (
        "%s%s = %s - %s" % (INDENT, gaps(r.intervals), count(r.calls, "call"), count(r.windows, "window")),
        "%s= %s  %s" % (pad, split, tables.OK_MARK))]
    return lines, worked


def _material(sel: Selection, more: Optional[Callable[[str], str]]) -> List[str]:
    """ON TRIGGER: a line for an ambiguous or shrink share of the whole
    windows' average at or beyond its threshold, with the command that
    lists those changes (``more``, given the cause)."""
    held = {}
    for f in sel.window_facts:
        if f.kind == schema.INCREMENT:
            cause = f.dims.get(schema.CAUSE_DIM)
            held[cause] = held.get(cause, 0) + f.metrics.get(schema.CONTEXT_HELD, 0)
    base = sum(m for c, m in held.items() if c != schema.SHRINK)
    lines = []
    for cause, floor in ((schema.AMBIGUOUS, AMBIGUOUS_MATERIAL), (schema.SHRINK, SHRINK_MATERIAL)):
        share = held.get(cause, 0) / base if base else 0
        if abs(share) >= floor:
            text = "%s! %s of the average is %s, %s %s%.0f%%: " % (
                INDENT, tables.pct(share), cause, "over" if share > 0 else "beyond", "" if share > 0 else "-",
                100 * floor)
            command = more(cause) if more else ""
            lines += [text + command] if len(text) + len(command) <= tables.WIDTH else [
                text.rstrip(": ") + ":", INDENT * 2 + command]
    return [style.tag(line, style.HINT) for line in lines]


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
        worked.append(style.tag("%s%s: %s = %s  %s" % (
            INDENT, tables.title(grouped.dim), " + ".join(terms), num(total),
            "%s the headline's" % tables.OK_MARK if ok else "%s not the headline's %s" % (
                tables.BAD_MARK, num(sel.total))), style.KEY))
    if not holds:
        return [style.tag(line.strip(), style.BAD) for line in worked], []
    noun = "table's rows sum" if len(shown) == 1 else "table's rows sum, each,"
    text = _line("%s · the %s to the headline's %s" % (OK, noun, num(sel.total)))
    return [style.tag(text, style.GOOD)], worked
