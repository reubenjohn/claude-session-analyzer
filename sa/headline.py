"""The answer, under the scope: the total and how it was taken (for
context, the average context per call, D-PER-CALL), then the starting
context by what started each window and the growth walked down the view's
levers (D-HEADLINE-TWO-LINES), each in the total's unit. A ``--where`` pin
omits every lever whose facts all share one value."""
from typing import Dict, List, Optional, Tuple

from . import glossary, query, schema, style, tables
from .query import Selection
from .schema import Fact
from .tables import at, count, num, pct

Names = Optional[Dict[str, str]]  # a subagent id -> its printed label (``render.subagent_names``)


def open_dims(sel: Selection, dims: Tuple[str, ...], carrier: str) -> List[str]:
    """The dimensions left open: those whose carrier facts do not all share
    one value, pinned or not (a pinned command implies its tool, a pinned
    window its subagent, session and project; a corpus of one ``peak``
    band has none to pin): a table or lever over one value only repeats
    the filter, or the scope."""
    return [dim for dim in dims
            if len({f.dims.get(dim) for f in sel.facts if f.kind == carrier}) != 1]


def headline(view, sel: Selection, forest: List[Fact] = (), names: Names = None) -> List[str]:
    """The total and the windows it is over, then one aligned block over it
    (D-HEADLINE-TWO-LINES), each line what, tokens, share, where from: the
    starting context as the sum of what started each window, then the
    growth down the view's levers, whatever ``--by`` shows: a category
    (``cause``) or a population row is never the answer. With no starting
    context, the block is the largest value of the first lever left open.
    Shares are of the mass added: the signed rows stay out of them, as out
    of every table's; the checks line says what was added and what shrank.
    A pinned window that inherited shows each copy's breakdown in its
    parent (``copied``)."""
    spec = schema.metric(view.metric)
    per_call = spec.aggregation == schema.PER_CALL
    line = level(sel, spec) if per_call else _total_line(view, sel, spec)
    carried = [f for f in sel.facts if f.kind == spec.carrier]
    added = sel.total - query.total([f for f in carried if f.dims.get(schema.CAUSE_DIM) == schema.SHRINK],
                                    view.metric, sel.calls)
    levers = open_dims(sel, view.levers, spec.carrier)
    starting = [f for f in carried if f.dims.get(schema.CAUSE_DIM) in STARTING] if view.starts else []
    mass = query.total(starting, view.metric, sel.calls)
    rows, extra = [], []  # the block's (what, tokens, where from), and the lines under its first
    if starting and added:
        rows.append((glossary.printed(schema.STARTING_CONTEXT).replace("_", " "), mass,
                     _sum(view, starting, sel.calls)))
        extra = copied(sel, forest)
        top, path = _path(sel.facts, levers, view.metric, names, sel.calls)
        if added - mass:
            rows.append((glossary.GROWTH, added - mass, "from %s %s" % (_name(top, levers, names), num(top.mass))
                         + path if top else ""))
    else:
        top, path = _path(sel.facts, levers, view.metric, names, sel.calls)
        if top is not None and added:
            rows.append(("largest " + levers[0], top.mass, _name(top, levers, names) + path))
    return [style.tag(line, style.HEADLINE)] + _block(rows, added, extra) + ([] if per_call else _average(sel))


def level(sel: Selection, spec: schema.Metric) -> str:
    """``average context per call* N tokens, over C calls in W windows``:
    the calls of the whole windows in view, a drill's too, whose matching
    changes it then names with the windows they come from (D-PER-CALL)."""
    line = "%s %s %s, over %s in %s" % (
        glossary.printed(glossary.AVERAGE).replace("_", " "), num(sel.total), spec.unit,
        count(sel.calls, "call"), count(sel.n_windows, "window"))
    if sel.drill:
        changes = sum(f.kind == spec.carrier for f in sel.facts)
        line += ", from %s%s in %s of them" % (count(changes, schema.PLURAL[spec.carrier][:-1],
                                                     schema.PLURAL[spec.carrier]),
                                               pins(sel.drill), num(query.window_count(sel.facts)))
    return line + ("" if sel.reconciliation.holds else " (reconciliation MISMATCH below)")


def _total_line(view, sel: Selection, spec: schema.Metric) -> str:
    """A summed view's total and the population it is over."""
    name = glossary.printed(view.metric)
    line = "%s: %s" % (name, num(sel.total)) + ("" if spec.unit == name else " " + spec.unit)
    if not view.reconciles or sel.drill:
        return line + " " + over(sel, spec.carrier)
    return line + " across " + count(sel.n_windows, schema.WINDOW_DIM) + (
        "" if sel.reconciliation.mass_holds else " (reconciliation MISMATCH below)")


def _name(row: query.Row, levers: List[str], names: Names) -> str:
    return tables.value(levers[0], row.value, names)


def _block(rows: List[Tuple[str, float, str]], added: float, extra: List[str]) -> List[str]:
    """The rows aligned in columns, one space reserved after the label for
    a footnote marker; what each comes from is a data value, never a term,
    unless it is a sum of declared starts."""
    if not rows:
        return []
    terms = [glossary.GLOSSARY.get(what.replace(" ", "_")) for what, _, _ in rows]
    width = max(len(what) for what, _, _ in rows) + len(glossary.MARKER) * any(t and t.marked for t in terms)
    figures = max(len(num(mass)) for _, mass, _ in rows)
    shares = max(len(pct(mass / added)) for _, mass, _ in rows)
    lines = []
    for i, (what, mass, source) in enumerate(rows):
        text = "  %-*s  %*s  %*s" % (width, what, figures, num(mass), shares, pct(mass / added))
        start = len(text) + 2
        text += "  " + source if source else ""
        free = not source.startswith(SUM)
        lines.append(style.tag(text.rstrip(), "", values=((start, len(text)),) if free else ()))
        if i == 0:
            lines += ["  " + line for line in extra]
    return lines


SUM = "= "  # a starting context line's sum


def _sum(view, starting: List[Fact], calls: Optional[int] = None) -> str:
    """The starting context as a sum that adds up to it: each start that
    began, largest first, ``+ N more starts`` past ``TERMS``, and
    ``inherited`` on its own, as in the cause table; nothing when there is
    one term."""
    inherited_mass = query.total([f for f in starting if f.dims.get(schema.CAUSE_DIM) == schema.INHERITED],
                                 view.metric, calls)
    own = [f for f in starting if f.dims.get(schema.CAUSE_DIM) != schema.INHERITED]
    terms = [(START_LABELS.get(r.value, r.value), r.mass) for r in
             query.group(own, view.starts, view.metric, calls).rows if r.kind == query.REGULAR]
    if len(terms) > TERMS:
        rest = terms[TERMS - 1:]
        terms = terms[:TERMS - 1] + [("%d more starts" % len(rest), sum(m for _, m in rest))]
    if inherited_mass:
        terms.append((schema.INHERITED, inherited_mass))
    if len(terms) < 2:
        return ""
    return SUM + " + ".join("%s %s" % (what, num(mass)) for what, mass in terms)


TERMS = 3  # a sum's terms of starts, ``+ N more starts`` the last
# A start as a starting context's sum names it: the windows it began.
START_LABELS = {schema.SESSION_START: "session starts", schema.SUBAGENT_START: "subagent starts",
                schema.FORK: "forks", schema.COMPACTION: "compactions"}


def copied(sel: Selection, forest: List[Fact]) -> List[str]:
    """Under a ``--where window=`` pin, each inherited increment counted
    here, as its parent window's exact breakdown by tool through the branch
    call, signed rows included, found by reference (D-FORK-INHERITED); per
    call, each part held by the fork's calls as the copy was."""
    if schema.WINDOW_DIM not in dict(sel.window_where):
        return []
    lines = []
    for f in sel.facts:
        if f.dims.get(schema.CAUSE_DIM) == schema.INHERITED:
            key, call = f.evidence[schema.PARENT_WINDOW], f.evidence[schema.BRANCH_CALL]
            delta = f.metrics[schema.CONTEXT_DELTA]
            scale = f.metrics[schema.CONTEXT_HELD] / delta / max(sel.calls, 1) if (
                sel.calls is not None and delta) else 1
            rows = query.group(query.through(forest, key, call), schema.TOOL_DIM, schema.CONTEXT_DELTA).rows
            lines.append("  %s %s copied from %s=%s through %s, by tool: %s" % (
                schema.INHERITED, num(delta * scale), schema.WINDOW_DIM,
                schema.window_value(key), at(call), ", ".join(
                    "%s %s" % (tables.RESIDUAL_LABEL if r.kind == query.RESIDUAL else r.value,
                               num(r.mass * scale)) for r in rows)))
    return lines


STARTING = (schema.STARTING_CONTEXT, schema.INHERITED)  # the causes that enter as a window starts


def over(sel: Selection, carrier: str) -> str:
    """``over N <carrier>s [where <drill pins>] in M windows``, M of the
    selection's when a drill shows fewer. The drill pins are named here
    only: this is the one count they narrow."""
    shown, windows = query.window_count(sel.facts), count(sel.n_windows, "window")
    if shown != sel.n_windows:
        windows = "%s of %s" % (num(shown), windows)
    n = sum(f.kind == carrier for f in sel.facts)
    facts = count(n, schema.PLURAL[carrier][:-1], schema.PLURAL[carrier])
    return "over %s%s in %s" % (facts, pins(sel.drill), windows)


def pins(pairs: List[Tuple[str, str]]) -> str:
    """`` where dim=value ...`` for the pairs, or nothing."""
    return " where " + " ".join("%s=%s" % (d, tables.home(v)) for d, v in pairs) if pairs else ""


def _largest(table: query.Table) -> Optional[query.Row]:
    """The largest regular row: the first, the rows being sorted by mass."""
    return next((r for r in table.rows if r.kind == query.REGULAR), None)


def _path(facts: List[Fact], levers: List[str], metric: str,
          names: Names = None, calls: Optional[int] = None) -> Tuple[Optional[query.Row], str]:
    """The first lever's largest row, and the walk from it: each next lever
    refines the row before, ``→`` the largest row within it; when a row of
    that lever elsewhere is strictly larger, ``; top <lever>`` names it,
    never silent. A row with none of the lever within it (a top tool with
    no command: Agent, MCP tools) still has the largest elsewhere named,
    then ends the walk. The shares are the tables'."""
    if not levers:
        return None, ""
    top = _largest(query.group(facts, levers[0], metric, calls))
    if top is None:
        return None, ""
    lead, text = query.select(facts, [(levers[0], top.value)]), ""
    for dim in levers[1:]:
        within = _largest(query.group(lead, dim, metric, calls))
        if within is not None:
            text += " → %s %s" % (tables.value(dim, within.value, names), num(within.mass))
        overall = _largest(query.group(facts, dim, metric, calls))
        if overall is not None and overall.mass > (within.mass if within else 0):
            text += "; top %s %s %s" % (dim, tables.value(dim, overall.value, names), num(overall.mass))
        if within is None:
            break
        lead = query.select(lead, [(dim, within.value)])
    return top, text


def _average(sel: Selection) -> List[str]:
    """The average context per call: what a call held (its
    ``context_tokens``), averaged over the calls of the whole windows
    selected (a drill keeps no call facts), printed with that population.
    It is never "added per call", and a mean never sums (``query.mean``)."""
    mean, calls = query.mean(sel.window_facts, schema.CONTEXT_TOKENS)
    if not calls:
        return []
    return ["%s %s %s, over %s in %s" % (
        glossary.printed(glossary.AVERAGE).replace("_", " "), num(mean), schema.metric(schema.CONTEXT_TOKENS).unit,
        count(calls, "call"), count(sel.n_windows, "window"))]

