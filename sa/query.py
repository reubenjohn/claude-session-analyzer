"""Select, group and reconcile facts. No rendering here."""
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

from . import schema
from .reconciliation import Reconciliation, reconcile
from .schema import Fact

Where = Iterable[Tuple[str, str]]


def select(facts: Iterable[Fact], where: Where) -> List[Fact]:
    """Facts whose dimensions equal every ``(dim, value)`` pair. The plain
    filter; ``narrow`` is the checked one. A value of None selects the
    catch-all row: the facts that lack ``dim``, a shrink aside unless
    ``dim`` keeps whole windows (a shrink is its own row in every table)."""
    pairs = list(where)
    return [f for f in facts if all(_holds(f, dim, value) for dim, value in pairs)]


def _holds(f: Fact, dim: str, value: Optional[str]) -> bool:
    if value is not None:
        return f.dims.get(dim) == value
    return dim not in f.dims and (dim in schema.WINDOW_DIMENSIONS
                                  or f.dims.get(schema.CAUSE_DIM) != schema.SHRINK)


class NoMatch(schema.SchemaError):
    """A pin no fact carries given the pins before it: its dimension, its
    value and the values present (``grammar.no_match`` words it)."""

    def __init__(self, dim: str, value: Optional[str], present: List[str]):
        super().__init__("no fact carries %s=%s given the pins before it" % (dim, value))
        self.dim, self.value, self.present = dim, value, present


def narrow(facts: List[Fact], where: Where, metric: str) -> List[Fact]:
    """Select pair by pair, refusing any pair that would print a confident
    zero: an undeclared dimension or value, a dimension the metric's carrier
    never has, or an open-vocabulary value no fact still carries
    (``NoMatch``, with the values present by descending |mass|: the
    data's own vocabulary, given the pairs before it). A declared value no fact
    carries is a measured zero, not a typo, and is answered."""
    carrier = schema.metric(metric).carrier
    for dim, value in where:
        schema.check_dimension(dim, carrier)
        if value is not None:
            schema.check_value(dim, value)
        kept = select(facts, [(dim, value)])
        if (dim not in schema.VOCABULARY or value is None) and not any(f.kind == carrier for f in kept):
            raise NoMatch(dim, value, values(facts, dim, metric))
        facts = kept
    return facts


def split(where: Where) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """The ``--where`` pairs that keep whole windows, and those that drill
    within them."""
    pairs = list(where)
    return ([p for p in pairs if p[0] in schema.WINDOW_DIMENSIONS],
            [p for p in pairs if p[0] not in schema.WINDOW_DIMENSIONS])


def values(facts: Iterable[Fact], dim: str, metric: str) -> List[str]:
    """Every value of ``dim`` the metric's carrier facts carry, by descending
    |mass|: the data's own vocabulary for a filter. Read from the facts, not
    from a table's rows, so a value every table files as signed (shrink) is
    present like any other."""
    carrier = schema.metric(metric).carrier
    mass: Dict[str, float] = {}
    for f in facts:
        if f.kind == carrier and f.dims.get(dim) is not None:
            value = f.dims[dim]
            mass[value] = mass.get(value, 0) + abs(f.metrics[metric])
    return sorted(mass, key=lambda v: -mass[v])


def per(metric: str, calls: Optional[int]) -> float:
    """What a sum of ``metric`` is divided by: 1, or for a per-call metric
    the ``calls`` of the one population it is read over, which it requires
    and nothing else takes (D-PER-CALL: a per-call figure is never summed or
    merged across populations, their denominators differ). A peak refuses:
    its sum counts a token once per call that re-read it."""
    spec = schema.metric(metric)
    if spec.aggregation == schema.PEAK:
        raise schema.SchemaError("%s is a peak; it has no sum. Use largest() or mean()." % metric)
    if (spec.aggregation == schema.PER_CALL) != (calls is not None):
        raise schema.SchemaError("%s is %s per call: its population's calls are %s" % (
            metric, "read" if calls is None else "not", "required" if calls is None else "not taken"))
    return max(calls, 1) if calls is not None else 1


def total(facts: List[Fact], metric: str, calls: Optional[int] = None) -> float:
    """The metric summed once, in fact order, over its carrier kind (over
    ``calls`` for a per-call metric, ``per``): the one figure a headline and
    every table's base are taken from."""
    divisor = per(metric, calls)
    carrier = schema.metric(metric).carrier
    return sum(f.metrics[metric] for f in facts if f.kind == carrier) / divisor


def mean(facts: Iterable[Fact], metric: str) -> Tuple[float, int]:
    """The metric averaged over its carrier facts, and their count: for
    ``context_tokens``, what a call held, averaged over the calls (the
    average context per call, D-MEAN-CONTEXT). One population's figure,
    printed beside its count: a mean is never summed, nor merged with
    another population's; a combined one is recomputed from its facts."""
    carrier = schema.metric(metric).carrier
    values = [f.metrics[metric] for f in facts if f.kind == carrier]
    return (sum(values) / len(values) if values else 0.0), len(values)


def window_count(facts: Iterable[Fact]) -> int:
    """How many windows the facts come from, by identity (``WindowKey``),
    never by the ``window`` value, whose hash could collide."""
    return len({f.window for f in facts})


def orphan_forks(facts: Iterable[Fact], forest: Iterable[Fact]) -> Tuple[int, int]:
    """The fork windows among ``facts`` with no ``inherited`` increment, as
    (parent missing, branch call not found). A fork's parent session is its
    ``fork-context-ref``'s, else its own; it is missing when no main window
    of that session, other than the fork, is in ``forest`` (deleted, or
    outside ``--since``): the copied records are then live. A parent read
    whose branch call is not found leaves the copy in the fork's starting
    context. Either way its copy counts as its own (D-MISSING-PARENT);
    the copies are not detected, only counted here."""
    forks: Dict[schema.WindowKey, Optional[str]] = {}
    named, inheriting = {}, set()
    for f in facts:
        if f.dims.get(schema.STARTED_BY_DIM) == schema.FORK:
            forks.setdefault(f.window, f.dims.get(schema.SESSION_DIM))
            if f.evidence.get(schema.PARENT_SESSION):
                named[f.window] = f.evidence[schema.PARENT_SESSION]
        if f.dims.get(schema.CAUSE_DIM) == schema.INHERITED:
            inheriting.add(f.window)
    mains = {(f.dims.get(schema.SESSION_DIM), f.window) for f in forest if schema.SUBAGENT_DIM not in f.dims}
    missing = unfound = 0
    for key, session in forks.items():
        if key not in inheriting:
            parent = named.get(key, session)
            if any(s == parent and w != key for s, w in mains):
                unfound += 1
            else:
                missing += 1
    return missing, unfound


def through(facts: List[Fact], key: schema.WindowKey, call: schema.Locator) -> List[Fact]:
    """The facts of window ``key`` up to the call at ``call`` and the
    increments it closes: an inherited increment's breakdown, by reference
    (its evidence names both). Their context_delta sums to that call's
    occupancy, the window telescoping; a list without the call is empty."""
    mine = [f for f in facts if f.window == key]
    at = next((i for i, f in enumerate(mine) if f.kind == schema.CALL and f.locator == call), None)
    if at is None:
        return []
    after = next((i for i in range(at + 1, len(mine)) if mine[i].kind == schema.CALL), len(mine))
    return mine[:after]


# The three kinds of row a table has. Only regular rows take part in shares.
REGULAR = "regular"
RESIDUAL = "residual"  # facts that lack the grouped dimension
SIGNED = "signed"      # shrink: its mass is negative by definition


class Row(NamedTuple):
    value: Optional[str]  # None for the residual row
    mass: float
    count: int
    kind: str


class Table(NamedTuple):
    dim: str
    rows: List[Row]  # regular rows by descending mass, then residual, then signed
    base: float      # the regular rows' mass: the total less the other rows
    residual: Tuple[dict, ...] = ()  # the dimensions of each fact in the residual row

    def share(self, mass: float) -> Optional[float]:
        """Of the regular rows' mass; None when there is none."""
        return mass / self.base if self.base else None


def group(facts: List[Fact], dim: str, metric: str, calls: Optional[int] = None) -> Table:
    """One row per value of ``dim``, then the residual row for facts that
    lack ``dim``, then the signed shrink row.

    The metric is read only from facts of its carrier kind, so a dimension
    that kind never carries is refused. A peak metric refuses to be grouped
    (``usage.usage_context`` has the measurement).
    Shrink increments always land in their own signed row whatever ``dim``
    is, so no other row mixes signed mass and every share is a share of mass
    that was added. The base is the total less the residual and signed rows,
    so it and the headline total never disagree by a rounding. A per-call
    metric's rows are over its population's ``calls`` (``per``), so they
    add up to its total.
    """
    spec, divisor = schema.metric(metric), per(metric, calls)
    schema.check_dimension(dim, spec.carrier)
    mass: Dict[Tuple[Optional[str], str], float] = {}
    count: Dict[Tuple[Optional[str], str], int] = {}
    residual = []
    for f in facts:
        if f.kind != spec.carrier:
            continue
        if f.dims.get(schema.CAUSE_DIM) == schema.SHRINK:
            key = (schema.SHRINK, SIGNED)
        elif f.dims.get(dim) is None:
            key = (None, RESIDUAL)
            residual.append(f.dims)
        else:
            key = (f.dims[dim], REGULAR)
        mass[key] = mass.get(key, 0) + f.metrics[metric]
        count[key] = count.get(key, 0) + 1
    regular = sorted((k for k in mass if k[1] == REGULAR), key=lambda k: -mass[k])
    other = [k for k in ((None, RESIDUAL), (schema.SHRINK, SIGNED)) if k in mass]
    rows = [Row(k[0], mass[k] / divisor, count[k], k[1]) for k in regular + other]
    return Table(dim, rows, total(facts, metric, calls) - sum(mass[k] / divisor for k in other),
                 tuple(residual))


def relabels(facts: List[Fact], a: str, b: str, metric: str) -> Optional[Dict[str, str]]:
    """``b``'s value for each of ``a``'s when the two split the carrier
    facts into the same groups (shrink aside: its own row in both; the
    residual only into the residual), so ``b``'s table would repeat ``a``'s
    row for row under other labels; None when they split them otherwise."""
    carrier = schema.metric(metric).carrier
    pairs = {(f.dims.get(a), f.dims.get(b)) for f in facts
             if f.kind == carrier and f.dims.get(schema.CAUSE_DIM) != schema.SHRINK}
    if (len({x for x, _ in pairs}) != len(pairs) or len({y for _, y in pairs}) != len(pairs)
            or any((x is None) != (y is None) for x, y in pairs)):
        return None
    return {x: y for x, y in pairs if x is not None}


def largest(facts: Iterable[Fact], metric: str) -> Optional[Fact]:
    """The fact carrying the largest value of ``metric``: the only honest
    report of a peak is the single call where it happened."""
    spec = schema.metric(metric)
    carried = [f for f in facts if f.kind == spec.carrier]
    return max(carried, key=lambda f: f.metrics[metric]) if carried else None


class Selection(NamedTuple):
    """What a view is answered over: the whole windows the window-dimension
    filters kept and the facts the drill filters kept within them."""
    window_where: List[Tuple[str, str]]  # the --where pairs that kept whole windows
    drill: List[Tuple[str, str]]     # the --where pairs that selected within them
    window_facts: List[Fact]        # whole windows kept by ``window_where``
    facts: List[Fact]               # the windows' facts kept by ``drill`` too, less ``inherited``
    total: float                    # the view's metric over ``facts``, summed once (per call: over ``calls``)
    reconciliation: Optional[Reconciliation]  # over ``window_facts`` (a drill never changes it), or None
    inherited: Tuple[Fact, ...] = ()  # inherited increments whose parent window is kept: counted there
    calls: Optional[int] = None     # a per-call metric's population: the calls of ``window_facts``

    @property
    def where(self) -> List[Tuple[str, str]]:
        """Every pair, in the order they were applied."""
        return self.window_where + self.drill

    @property
    def n_windows(self) -> int:
        return window_count(self.window_facts)


def counted_in_parent(facts: List[Fact]) -> List[Fact]:
    """The inherited increments whose parent window is among ``facts``'
    windows: its mass is already there (D-INHERITED-ONCE)."""
    kept = {f.window for f in facts}
    return [f for f in facts if f.dims.get(schema.CAUSE_DIM) == schema.INHERITED
            and f.evidence.get(schema.PARENT_WINDOW) in kept]


def selection(facts: List[Fact], where: Where, metric: str, reconciles: bool) -> Selection:
    """The view's population: the window pins narrow first and keep whole
    windows, the drill pins narrow within them; the total is over the
    drilled facts, the reconciliation (for a view that reconciles) over the
    whole windows. Under a summed metric an inherited increment counts
    once: decided here, over the windows kept, it leaves the total and
    every table when its parent window is kept, and counts in full when the
    parent is out of scope; either way its own window's reconciliation
    includes it. Under a per-call metric it stays: the fork's calls held it.
    A per-call metric is over the calls of the whole windows kept, a drill
    included (D-PER-CALL)."""
    window_where, drill = split(where)
    window_facts = narrow(facts, window_where, metric)
    calls = (sum(f.kind == schema.CALL for f in window_facts)
             if schema.metric(metric).aggregation == schema.PER_CALL else None)
    once = counted_in_parent(window_facts) if calls is None else []
    dropped = set(map(id, once))
    kept = narrow([f for f in window_facts if id(f) not in dropped], drill, metric)
    return Selection(window_where, drill, window_facts, kept, total(kept, metric, calls),
                     reconcile(window_facts) if reconciles else None, tuple(once), calls)
