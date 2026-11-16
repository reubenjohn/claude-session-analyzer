"""Plain-text rendering of a selection, in reading order: scope (the
population), answer (headline, lever walk, peak), tables or leaves, one key,
checks. The tables are grouped here from the selection's facts; its total
and reconciliation come with it, so nothing here decides the exit status."""
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

from . import checks, glossary, headline, query, schema, style, tables, windows
from .corpus import Corpus
from .query import Selection
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
    leads: Tuple[str, ...] = ()  # ``schema.ORDERED`` dimensions the hint pins, at their first value, before the levers


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
        body, above, repeats = [], None, []
        for dim in dims:
            grouped = query.group(sel.facts, dim, view.metric)
            if dim in schema.ORDERED:  # bands read fullest first, not by mass
                order = schema.ORDERED[dim]
                grouped = grouped._replace(rows=sorted(grouped.rows, key=lambda r: (
                    r.kind != query.REGULAR, order.index(r.value) if r.kind == query.REGULAR else 0)))
            labels = above and query.relabels(sel.facts, above.dim, dim, view.metric)
            if labels and len(labels) <= limit:  # the table would repeat the one above
                repeats.append((dim, labels))
                line = tables.relabelled(above, repeats, names)
                if len(repeats) > 1:  # the tables repeating one table share its line
                    body[-2] = line
                else:
                    body.insert(-1, line)
            elif grouped.rows:
                above, repeats = grouped, []
                total = _total(view, sel) if dim == schema.CAUSE_DIM else None
                totalled = totalled or total is not None
                counts = window_counts(sel, dim)
                body += table(grouped, view.metric, limit, whole=bool(by), total=total, names=names,
                              counts=counts) + ([WHOLE_WINDOWS] if counts and sel.drill else []) + [""]
    scope = [style.tag(line, style.SCOPE, values=getattr(line, "values", ()))
             for line in population(view, sel, loaded, since_default)]
    above = (scope + [""] + headline.headline(view, sel, forest, names) + next_step(view, sel, by, names)
             + [""] + body)
    lines, terms = tables.footnote(above + checks.footer(view, sel, totalled))
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


def window_counts(sel: Selection, dim: str) -> Optional[tables.Counts]:
    """A ``peak`` table's count columns: per band, the windows the view's
    facts come from and the calls they hold (a window has one band, so
    each adds up); None for any other table, which counts its carrier."""
    if dim != schema.PEAK_DIM:
        return None
    shown = {f.window for f in sel.facts}
    per: Dict[str, Tuple[set, int]] = {}
    for f in sel.window_facts:
        if f.window in shown:
            keys, calls = per.get(f.dims[dim], (set(), 0))
            keys.add(f.window)
            per[f.dims[dim]] = (keys, calls + (f.kind == schema.CALL))
    return [("windows", {v: len(k) for v, (k, _) in per.items()}),
            (schema.PLURAL[schema.CALL], {v: n for v, (_, n) in per.items()})]


# Under a drill, a band's counts are still of whole windows: those with a change the pins kept.
WHOLE_WINDOWS = "windows, calls: whole windows with a matching change, and all their calls"
NEXT = "→ next: add "


def next_step(view: View, sel: Selection, by: Optional[str],
              names: Optional[Dict[str, str]] = None) -> List[str]:
    """One line under the headline, the path's next step: the fullest
    ``peak`` band while the windows in view span several and no drill is
    pinned (the view's ``leads``), then the pin that follows its own levers
    (the top value of the first lever left open: the top tool, then within
    a pinned tool its top command), or ``--by fact`` once none is open;
    none when the leaves already print or there is nothing to show."""
    carrier = schema.metric(view.metric).carrier
    if by == FACT or not any(f.kind == carrier for f in sel.facts):
        return []
    for dim in headline.open_dims(sel, () if sel.drill else view.leads, carrier):
        present = {f.dims.get(dim) for f in sel.facts if f.kind == carrier}
        top = next(v for v in schema.ORDERED[dim] if v in present)  # the fullest band
        return [style.tag("%s--where %s=%s" % (NEXT, dim, top), style.HINT)]
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
