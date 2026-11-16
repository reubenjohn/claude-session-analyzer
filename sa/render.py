"""Plain-text rendering of a selection, in reading order: scope (the
population), answer (headline, lever walk, peak), tables or leaves, one key,
checks. The tables are grouped here from the selection's facts; its total
and reconciliation come with it, so nothing here decides the exit status."""
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

from . import checks, glossary, grammar, headline, leaves, notes, query, residual, schema, style, tables, windows
from .corpus import Corpus
from .query import Selection
from .schema import Fact
from .tables import count, num

KEPT = "in view"  # the population line: the windows the time filter and pins kept
LIMIT = 5  # a default table's rows; ``by DIM`` prints every one


class View(NamedTuple):
    """The shape of one report: which metric, which tables by default, and
    whether the total is the windows' final occupancies, which the checks
    then reconcile."""
    metric: str
    tables: Tuple[str, ...]  # printed by default
    levers: Tuple[str, ...]  # the headline walks down these; a value lies under one of the lever above
    reconciles: bool
    notes: Tuple[str, ...]   # printed under ``-v``, for the view's metric
    starts: Optional[str] = None  # the dimension the starting context splits by; None: no such line
    also: Tuple[str, ...] = ()  # the ``by DIM`` pointer's order, any other open dimension after them


def report(view: View, sel: Selection, loaded: Corpus, by: Optional[str], inv: grammar.Invocation,
           verbose: bool = False, forest: List[Fact] = (),
           names: Optional[Dict[str, str]] = None) -> List[str]:
    """Every line of the view, in reading order: the scope (what was read
    and kept), the answer (the headline and its lever walk, the next
    command), the tables a pin left open (``by DIM`` that one table whole,
    or the facts themselves), the ways deeper as commands (``by DIM`` for
    the tables not shown, ``-v`` and its cost, or its block), and the checks. The cause table of a
    whole-window view closes with its total, the average, against the
    calls' mean size."""
    spec = schema.metric(view.metric)
    facts_by = grammar.FACTS[inv.view]
    shown, body, catch_alls, ways = [], [], [], []
    if by == facts_by:
        body = leaves.leaves(sel.facts, view.metric, sel.calls, sel.total, [d for d, _ in sel.where], names,
                             LIMIT, lambda w: inv.command(by=schema.WINDOW_DIM) if w is None else inv.command(
                                 by=facts_by, add=[(schema.WINDOW_DIM, w)]), tables.tilde(loaded.root)) + [""]
    else:
        dims = [by] if by else headline.open_dims(sel, view.tables, spec.carrier)
        above, repeats, printed = None, [], []
        for dim in dims:
            grouped = query.group(sel.facts, dim, view.metric, sel.calls)
            if dim in schema.ORDERED:  # bands read fullest first, not by mass
                order = schema.ORDERED[dim]
                grouped = grouped._replace(rows=sorted(grouped.rows, key=lambda r: (
                    r.kind != query.REGULAR, order.index(r.value) if r.kind == query.REGULAR else 0)))
            labels = above and query.relabels(sel.facts, above.dim, dim, view.metric)
            printed.append(dim)
            if labels and len(labels) <= LIMIT and not by:  # the table would repeat the one above
                repeats.append((dim, labels))
                line = tables.relabelled(above, repeats, names)
                if len(repeats) > 1:  # the tables repeating one table share its line
                    body[-2] = line
                else:
                    body.insert(-1, line)
            elif grouped.rows:
                above, repeats = grouped, []
                counts = window_counts(sel, dim, view.metric)
                shown.append((grouped, counts))
                if any(r.kind == query.RESIDUAL for r in grouped.rows):
                    catch_alls.append(dim)
                body += tables.table(
                    grouped, view.metric, None if by else LIMIT,
                    total=_total(view, sel) if dim == schema.CAUSE_DIM else None, names=names,
                    counts=counts, more=inv.command(by=dim), parts=_parts(sel, dim, view.metric),
                    glosses=GLOSSES if dim == schema.CAUSE_DIM else None) + (
                    [WHOLE_WINDOWS] if counts and sel.drill else []) + [""]
        ways = notes.also_by(sel, view, spec.carrier, printed, inv)
    pad = max([len(c) for c, _ in ways] + [len(inv.command(by=by, verbose=True))])
    scope = [style.tag(line, style.SCOPE, values=getattr(line, "values", ()))
             for line in population(view, sel, loaded, inv.since_text is None, forest, names)]
    above = (scope + [""] + headline.headline(view, sel, forest, names) + next_step(view, sel, by, inv, names)
             + [""] + body)
    if view.reconciles:  # a trigger's command keeps the pins; none when the cause is pinned already
        closing, worked = checks.context(sel, None if schema.CAUSE_DIM in dict(inv.pins) else (
            lambda c: inv.command(add=[(schema.CAUSE_DIM, c)])))
    else:
        closing, worked = checks.spend(sel, [] if by == facts_by else [t for t, _ in shown])
    lines, terms = notes.footnote(above + closing)
    figures = notes.figures(view, sel, shown, by == facts_by, names)
    block = notes.block(figures, terms, catch_alls, {glossary.printed(view.metric): view.notes})
    catch_alls = [d for d in catch_alls if residual.RESIDUAL_NOTES.get(d, ("", []))[1]]  # a case list to tell
    deeper = []
    for _ in range(2):  # -v's cost, exactly: its lines less the pointer's own, which it replaces
        deeper = notes.pointer(inv.command(by=by, verbose=True), notes.footer(
            bool(terms or catch_alls), len(block) + len(worked) - max(len(deeper), 1)), pad)
    tail = [line for c, gloss in ways for line in notes.pointer(c, gloss, pad)] + (block if verbose else deeper)
    sep = [""] if tail or above[-1] else []  # the ways deeper share a section
    return lines[:len(above)] + tail + sep + lines[len(above):] + (worked if verbose else [])


# A cause's gloss beside its row, where the line has room: never a synonym (UX_PRINCIPLES 2).
GLOSSES = {c: glossary.GLOSSARY[c].gloss for c in schema.CAUSES if glossary.GLOSSARY[c].gloss}


def _parts(sel: Selection, dim: str, metric: str) -> List[Tuple[str, float]]:
    """The catch-all row's parts, largest first: its facts by cause (a
    call, which has none, by what started its window)."""
    carrier = schema.metric(metric).carrier
    if dim not in schema.KIND_DIMENSIONS[carrier]:
        return []
    by = schema.CAUSE_DIM if schema.CAUSE_DIM in schema.KIND_DIMENSIONS[carrier] else schema.STARTED_BY_DIM
    lacking = query.select(sel.facts, [(dim, None)])
    if not lacking or by == dim:
        return []
    return [(r.value, r.mass) for r in query.group(lacking, by, metric, sel.calls).rows
            if r.kind == query.REGULAR]


def window_counts(sel: Selection, dim: str, metric: str) -> Optional[tables.Counts]:
    """A window dimension's count columns, ``peak``'s in every view, every
    one's in a per-call view: per value, the windows the view's facts come
    from and the calls they hold (a window has one value, so each adds up;
    the residual's under ``None``), then those calls' own average size
    (``tables.AVG_CALL``, a mean: never summed), which the row's part of
    the average is not; None for any other table, which counts its
    carrier. A windows column of one window a row prints no column."""
    per_call = schema.metric(metric).aggregation == schema.PER_CALL
    if dim != schema.PEAK_DIM and not (per_call and dim in schema.WINDOW_DIMENSIONS):
        return None
    shown = {f.window for f in sel.facts}
    per: Dict[Optional[str], Tuple[set, List[Fact]]] = {}
    for f in sel.window_facts:
        if f.window in shown:
            keys, calls = per.setdefault(f.dims.get(dim), (set(), []))
            keys.add(f.window)
            calls += [f] if f.kind == schema.CALL else []
    windows = {v: len(k) for v, (k, _) in per.items()}
    return [("windows", windows)] * any(n > 1 for v, n in windows.items() if v is not None) + [  # 1 a row: none
            (schema.PLURAL[schema.CALL], {v: len(c) for v, (_, c) in per.items()}),
            (tables.AVG_CALL, {v: query.mean(c, schema.CONTEXT_TOKENS)[0] for v, (_, c) in per.items()})]


# Under a drill, a window row's counts are of whole windows: those with a change the pins kept.
WHOLE_WINDOWS = "windows, calls, avg call: of whole windows with a matching change; part of avg ÷ all calls"
NEXT = "→ next: "


def next_step(view: View, sel: Selection, by: Optional[str], inv: grammar.Invocation,
              names: Optional[Dict[str, str]] = None) -> List[str]:
    """Under the headline, the path's next step as a command that pastes
    and runs, the current pins kept, motivated by what the screen shows: the
    pin of the headline's own walk (the top value of the first lever left
    open: the top tool, then within a pinned tool its top command), or the
    facts (``by change``) once none is open; on the facts, the window
    printed first, while several print; none when there is nothing to show."""
    carrier = schema.metric(view.metric).carrier
    facts_by = grammar.FACTS[inv.view]
    carried = [f for f in sel.facts if f.kind == carrier]
    if not carried:
        return []
    add: List[Tuple[str, str]] = []
    if by == facts_by:
        if len({f.window for f in carried}) < 2:
            return []
        top = max({f.window for f in carried}, key=lambda k: sum(
            abs(f.metrics[view.metric]) for f in carried if f.window == k))  # as ``leaves`` orders them
        add = [(schema.WINDOW_DIM, schema.window_value(top))]
    for dim in headline.open_dims(sel, view.levers, carrier) if not add else ():
        top = next((r for r in query.group(sel.facts, dim, view.metric, sel.calls).rows
                    if r.kind == query.REGULAR), None)
        if top is not None:
            add = [(dim, tables.value(dim, top.value, names))]
            break
    lines = tables.command_lines(NEXT, inv.command(by=facts_by if by == facts_by or not add else None, add=add))
    return [style.tag(line, style.HINT, values=((line.find(glossary.PROG), len(line)),) if glossary.PROG in line else ())
            for line in lines]


def tools(view: View, sel: Selection) -> List[str]:
    """The selection's tools by mass, largest first: the order their hues
    are dealt in (``style.Painter``); none for a view whose carrier has no
    tool."""
    if schema.TOOL_DIM not in schema.KIND_DIMENSIONS[schema.metric(view.metric).carrier]:
        return []
    return [r.value for r in query.group(sel.facts, schema.TOOL_DIM, view.metric, sel.calls).rows
            if r.kind == query.REGULAR]


def _total(view: View, sel: Selection) -> Optional[str]:
    """The cause table's closing text: its rows, the average, against the
    calls' mean size (the held identity, per window), for a whole-window
    view that reconciles; no drill has one."""
    if not view.reconciles or sel.drill:
        return None
    if sel.reconciliation.held_holds:
        return "%s = mean call size" % tables.OK_MARK
    return "%s does not match the mean call size (below)" % tables.BAD_MARK


# Why a fork in view inherited nothing (``query.orphan_forks``), and what follows; singular, plural.
ORPHANED = (("parent is missing", "parents are missing"),
            ("branch call is not found in its parent", "branch calls are not found in their parents"))
ORPHAN = ("its copy counts as its own", "their copies count as their own")


def population(view: View, sel: Selection, loaded: Corpus, since_default: bool = False,
               forest: Iterable[Fact] = (), names: Optional[Dict[str, str]] = None) -> List[str]:
    """The scope, first: the read, one line (the files its ``--since``
    kept, named with that window and the root, then what the read skipped
    or excluded, corpus-wide) and what the window pins kept: the windows (the files with
    a call; a compaction a call follows starts another) and the facts
    the view's metric is read from, its carrier's. The compactions read
    print as one line when there are any: every one is unpriced; the forks in
    view that inherited nothing, under the kept, a line per reason, when
    there are any (``query.orphan_forks``). A drill pin is named on the headline,
    the one line that counts what it narrows."""
    carrier, _window = schema.metric(view.metric).carrier, schema.WINDOW_DIM
    since = ("of any age" if loaded.since_days is None else "modified in the last %gd%s"
             % (loaded.since_days, " (default)" if since_default else ""))
    marks = windows.compactions(loaded)
    compacted = ["      %s unpriced: %s started a window, %s ended their file"
                 % (count(sum(marks.values()), "compaction"), num(marks["started"]), num(marks["ended"]))
                 ] if marks else []
    plural = schema.PLURAL[carrier]
    head = "read: %s %s under " % (count(len(loaded.files), "file"), since.replace("modified in the", "from the")
                                   if loaded.since_days is not None else since)
    root = tables.tilde(loaded.root)  # a value: a directory named like a term is not the term
    cut = [text for n, text in ((loaded.skipped_lines, count(loaded.skipped_lines, "line") + " skipped"),
                                (loaded.duplicate_records, count(loaded.duplicate_records, "duplicate"))) if n]
    read = style.tag(head + root + ("; " + ", ".join(cut) if cut else ""), "",  # said when there is any
                     values=((len(head), len(head) + len(root)),))
    orphaned = [" " * (len(KEPT) + 2) + "%s whose %s: %s" % (count(n, schema.FORK), why[n > 1], ORPHAN[n > 1])
                for n, why in zip(query.orphan_forks(sel.window_facts, forest), ORPHANED) if n]
    return [read] + compacted + [
            "%s%s: %s, %s"
            % (KEPT, headline.pins(sel.window_where, names), count(sel.n_windows, _window),
               count(sum(f.kind == carrier for f in sel.window_facts), plural[:-1], plural))] + orphaned
