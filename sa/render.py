"""Plain-text rendering of a selection, in reading order: scope (the
population), answer (headline, lever walk, peak), tables or leaves, one key,
checks. The tables are grouped here from the selection's facts; its total
and reconciliation come with it, so nothing here decides the exit status."""
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

from . import glossary, headline, query, schema, style, tables, windows
from .corpus import Corpus
from .query import Selection
from .headline import INHERITED_LABEL
from .schema import Fact
from .tables import count, leaves, num, table

FACT = "fact"  # the ``--by`` that prints the leaves, not a table
KEPT = "in view"  # the population line: the windows the time filter and pins kept


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
           since_default: bool = False, forest: List[Fact] = (),
           names: Optional[Dict[str, str]] = None) -> List[str]:
    """Every line of the view, in reading order: the scope (what was read
    and kept), the answer (the headline and its lever walk, the peak), the
    tables a pin left open (``--by`` one dimension's table with its labels
    whole, or the leaves for ``fact``), one key for every note they call
    for, and the checks. The cause table of a whole-window view closes with
    its total against the windows' final sizes."""
    spec = schema.metric(view.metric)
    notes = {glossary.printed(view.metric): n for n in view.notes}  # a view's own clause for a term
    totalled = False  # whether a cause table printed its total row
    if by == FACT:
        body = leaves(sel.facts, view.metric, limit) + [""]
    else:
        dims = [by] if by else headline.open_dims(sel, view.tables, spec.carrier)
        body, above = [], None
        for dim in dims:
            grouped = query.group(sel.facts, dim, view.metric)
            labels = above and query.relabels(sel.facts, above.dim, dim, view.metric)
            if labels and len(labels) <= limit:  # the table would repeat the one above
                body.insert(-1, tables.relabelled(above, labels, dim, names))
            elif grouped.rows:
                above = grouped
                total = _total(view, sel) if dim == schema.CAUSE_DIM else None
                totalled = totalled or total is not None
                body += table(grouped, view.metric, limit, whole=bool(by), total=total, names=names) + [""]
    scope = [style.tag(line, style.SCOPE, values=getattr(line, "values", ()))
             for line in population(view, sel, loaded, since_default)]
    above = (scope + [""] + headline.headline(view, sel, forest, names) + next_step(view, sel, by, names)
             + [""] + body)
    lines, terms = tables.footnote(above + footer(view, sel, totalled))
    keyed = tables.key([(t, notes.get(t) or glossary.brief(glossary.key_of(t))) for t in terms])
    return lines[:len(above)] + keyed + ([""] if keyed else []) + lines[len(above):]


def subagent_names(loaded_types: Dict[str, str], facts: Iterable[Fact]) -> Dict[str, str]:
    """Each subagent id whose file's type ``loaded_types`` records (by file
    name, ``corpus.agent_type``), as ``<type> <first 8 of its id>``, unless
    that label would name two ids: those keep their whole id. Display and
    ``--where`` only: the id stays the dimension's value."""
    named = {f.dims[schema.SUBAGENT_DIM]: loaded_types[f.locator.file] for f in facts
             if schema.SUBAGENT_DIM in f.dims and f.locator.file in loaded_types}
    named = {i: "%s %s" % (kind, i[:8]) for i, kind in named.items()}
    seen: Dict[str, int] = {}
    for label in named.values():
        seen[label] = seen.get(label, 0) + 1
    return {i: label for i, label in named.items() if seen[label] == 1}


NEXT = "→ next: add "


def next_step(view: View, sel: Selection, by: Optional[str],
              names: Optional[Dict[str, str]] = None) -> List[str]:
    """One line under the headline: the pin that follows its own levers
    (the top value of the first lever a pin left open: the top tool, then
    within a pinned tool its top command), or ``--by fact`` once none is
    open; none when the leaves already print or there is nothing to show."""
    carrier = schema.metric(view.metric).carrier
    if by == FACT or not any(f.kind == carrier for f in sel.facts):
        return []
    for dim in headline.open_dims(sel, view.levers, carrier):
        top = next((r for r in query.group(sel.facts, dim, view.metric).rows if r.kind == query.REGULAR), None)
        if top is not None:
            pin = "%s=%s" % (dim, tables.value(dim, top.value, names))
            text = "%s--where %s" % (NEXT, "'%s'" % pin if " " in pin else pin)
            return [style.tag(text, style.HINT, values=((len(NEXT), len(text)),))]
    return [style.tag("%s--by %s" % (NEXT, FACT), style.HINT)]


def tools(view: View, sel: Selection) -> List[str]:
    """The selection's tools by mass, largest first: the order their hues
    are dealt in (``style.Painter``); none for a view whose carrier has no
    tool."""
    if schema.TOOL_DIM not in schema.KIND_DIMENSIONS[schema.metric(view.metric).carrier]:
        return []
    return [r.value for r in query.group(sel.facts, schema.TOOL_DIM, view.metric).rows
            if r.kind == query.REGULAR]


def _total(view: View, sel: Selection) -> Optional[str]:
    """The cause table's closing text: the booked total against the final
    sizes, for a whole-window view that reconciles; no drill has one."""
    if not view.reconciles or sel.drill:
        return None
    if sel.reconciliation.mass_holds:
        return "%s = final window sizes%s" % (tables.OK_MARK, headline.less(sel))
    return "%s does not match the final window sizes (below)" % tables.BAD_MARK


def population(view: View, sel: Selection, loaded: Corpus, since_default: bool = False) -> List[str]:
    """The scope, first: the read, one line (the files its ``--since``
    kept, named with that window and the root, then what the read skipped
    or excluded, corpus-wide) and what the window pins kept: the windows (the files with
    a call; a compaction a call follows starts another) and the facts
    the view's metric is read from, its carrier's. The compactions read
    print as one line when there are any: every one is unpriced; the forks in
    view whose parent was not read, as one line under the kept, when there
    are any (``query.orphan_forks``). A drill pin is named on the headline,
    the one line that counts what it narrows."""
    carrier, _window = schema.metric(view.metric).carrier, schema.WINDOW_DIM
    since = ("of any age" if loaded.since_days is None else "modified in the last %gd%s"
             % (loaded.since_days, " (default)" if since_default else ""))
    marks = windows.compactions(loaded)
    compacted = ["      %s unpriced: %s started a window, %s ended their file"
                 % (count(sum(marks.values()), "compaction"), num(marks["started"]), num(marks["ended"]))
                 ] if marks else []
    plural = schema.PLURAL[carrier]
    head = "read: %s %s under " % (count(len(loaded.files), "file"), since)
    root = tables.tilde(loaded.root)  # a value: a directory named like a term is not the term
    read = style.tag(head + root + ", %s skipped, %s excluded" % (
        count(loaded.skipped_lines, "line"), count(loaded.duplicate_records, "duplicate")), "",
        values=((len(head), len(head) + len(root)),))
    orphans = query.orphan_forks(sel.window_facts)
    orphaned = [" " * (len(KEPT) + 2) + (
        "%s whose parent is missing: its copy counts as its own" if orphans == 1 else
        "%s whose parents are missing: their copies count as their own") % count(orphans, schema.FORK)
        ] if orphans else []
    return [read] + compacted + [
            "%s%s: %s, %s"
            % (KEPT, headline.pins(sel.window_where), count(sel.n_windows, _window),
               count(sum(f.kind == carrier for f in sel.window_facts), plural[:-1], plural))] + orphaned


def _status(holds: bool) -> str:
    return "OK" if holds else "MISMATCH"


def _reconciliation(r: query.Reconciliation) -> List[str]:
    """The reconciliation in full, printed only when it fails."""
    terms = " + ".join("%s %s" % (c, num(r.by_cause[c])) for c in schema.CAUSES)
    reasons = ", ".join("%s %s" % (k, num(v)) for k, v in r.by_reason.items() if v)
    return [style.tag(line, style.BAD) for line in [
        "%s reconciliation over %s: %s = %s; final occupancy %s: %s"
        % (tables.BAD_MARK, count(r.windows, "window"), terms, num(r.booked),
           num(r.final_occupancy), _status(r.mass_holds)),
        "%s %s (= %s - %s): exact %s + ambiguous %s [%s] + shrink %s: %s"
        % (tables.BAD_MARK, gaps(r.intervals), count(r.calls, "call"), count(r.windows, "window"),
           _rate(r, r.exact), _rate(r, r.ambiguous), reasons or "none", _rate(r, r.shrink),
           _status(r.count_holds)),
        "it holds by construction (walk.py), so a mismatch is a bug in this tool"]]


def gaps(n: int) -> str:
    """The reconciliation's unit: one gap between two calls of a window, so
    a window of N calls has N - 1; a change is one booked part of a gap."""
    return count(n, "gap between calls", "gaps between calls")


def _rate(r: query.Reconciliation, n: int) -> str:
    return "%s (%.1f%%)" % (num(n), 100.0 * n / r.intervals) if r.intervals else "0"


def _checks(r: query.Reconciliation, totalled: bool, scope: str = "") -> str:
    """The one line a holding reconciliation prints, a drill and ``--by
    fact`` included: the tokens added less the shrinks, the booked total
    (against the final sizes unless a cause table's total row already said
    it), then the gaps between calls (one fewer than a window's calls; a
    change is one booked part of a gap) split into those booked to one
    source (``exact``), ambiguous and shrank, each with its rate (R4).
    ``scope`` names the whole windows a drill sits in."""
    shrink = r.by_cause[schema.SHRINK]
    mass = "%s added" % num(r.booked - shrink) + (
        " - %s %s = %s" % (num(-shrink), schema.SHRINK, num(r.booked)) if shrink else "") + (
        "" if totalled else " = the final window sizes")
    split = ", ".join(_part(r, n, name) for n, name in ((r.exact, ONE_SOURCE), (
        r.ambiguous, schema.AMBIGUOUS), (r.shrink, SHRANK)))
    return style.tag("%s checks%s: %s; %s (%s - %s): %s"
                     % (tables.OK_MARK, scope, mass, gaps(r.intervals), count(r.calls, "call"),
                        count(r.windows, "window"), split), style.GOOD)


ONE_SOURCE, SHRANK = "to one source", "shrank"  # the checks' plain words for exact and shrink gaps


def _part(r: query.Reconciliation, n: int, name: str) -> str:
    """``786 exact (92.9%)``: the count first, so it reads as that many gaps."""
    return "%s %s (%.1f%%)" % (num(n), name, 100.0 * n / r.intervals) if r.intervals else "0 " + name


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
