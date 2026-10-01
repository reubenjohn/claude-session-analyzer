"""Select, group and reconcile facts. No rendering here."""
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

from . import schema
from .schema import Fact

Where = Iterable[Tuple[str, str]]
LISTED = 20  # values a refusal names before counting the rest


def select(facts: Iterable[Fact], where: Where) -> List[Fact]:
    """Facts whose dimensions equal every ``(dim, value)`` pair. The plain
    filter; ``narrow`` is the checked one."""
    pairs = list(where)
    return [f for f in facts if all(f.dims.get(dim) == value for dim, value in pairs)]


def narrow(facts: List[Fact], where: Where, metric: str) -> List[Fact]:
    """Select pair by pair, refusing any pair that would print a confident
    zero: an undeclared dimension or value, a dimension the metric's carrier
    never has, or an open-vocabulary value no fact still carries, named
    with the values present by descending |mass| (the data's own
    vocabulary, given the pairs before it). A declared value no fact
    carries is a measured zero, not a typo, and is answered."""
    carrier = schema.metric(metric).carrier
    for dim, value in where:
        schema.check_value(schema.check_dimension(dim, carrier), value)
        kept = select(facts, [(dim, value)])
        if dim not in schema.VOCABULARY and not any(f.kind == carrier for f in kept):
            present = values(facts, dim, metric)  # built for the refusal only
            listed = ", ".join(present[:LISTED]) or "none"
            if len(present) > LISTED:
                listed += " (+%d more; --by %s lists them all)" % (len(present) - LISTED, dim)
            raise schema.SchemaError("no facts carry %s=%s; present: %s" % (dim, value, listed))
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


def total(facts: List[Fact], metric: str) -> float:
    """The metric summed once, in fact order, over its carrier kind: the one
    figure a headline and every table's base are taken from."""
    carrier = schema.metric(metric).carrier
    return sum(f.metrics[metric] for f in facts if f.kind == carrier)


def window_count(facts: Iterable[Fact]) -> int:
    """How many windows the facts come from: a window is a file."""
    return len({f.locator.file for f in facts})


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


def group(facts: List[Fact], dim: str, metric: str) -> Table:
    """One row per value of ``dim``, then the residual row for facts that
    lack ``dim``, then the signed shrink row.

    The metric is read only from facts of its carrier kind, so a dimension
    that kind never carries is refused. A peak metric refuses to be grouped
    (``usage.usage_context`` has the measurement).
    Shrink increments always land in their own signed row whatever ``dim``
    is, so no other row mixes signed mass and every share is a share of mass
    that was added. The base is the total less the residual and signed rows,
    so it and the headline total never disagree by a rounding.
    """
    spec = schema.metric(metric)
    if spec.aggregation == schema.PEAK:
        raise schema.SchemaError("%s is a peak; it has no sum. Use largest()." % metric)
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
    rows = [Row(k[0], mass[k], count[k], k[1]) for k in regular + other]
    return Table(dim, rows, total(facts, metric) - sum(mass[k] for k in other), tuple(residual))


def largest(facts: Iterable[Fact], metric: str) -> Optional[Fact]:
    """The fact carrying the largest value of ``metric``: the only honest
    report of a peak is the single call where it happened."""
    spec = schema.metric(metric)
    carried = [f for f in facts if f.kind == spec.carrier]
    return max(carried, key=lambda f: f.metrics[metric]) if carried else None


class Reconciliation(NamedTuple):
    by_cause: Dict[str, float]  # context_delta booked per cause
    windows: int
    calls: int
    final_occupancy: float      # last call's context_tokens, summed over windows
    exact: int
    ambiguous: int
    by_reason: Dict[str, int]
    shrink: int

    @property
    def booked(self) -> float:
        return sum(self.by_cause.values())

    @property
    def intervals(self) -> int:
        """Counted from the calls, not from the increments it is checked against."""
        return self.calls - self.windows

    @property
    def mass_holds(self) -> bool:
        return self.booked == self.final_occupancy

    @property
    def count_holds(self) -> bool:
        return self.exact + self.ambiguous + self.shrink == self.intervals

    @property
    def holds(self) -> bool:
        return self.mass_holds and self.count_holds


def reconcile(facts: Iterable[Fact]) -> Reconciliation:
    """Chain integrity over whole windows: every booked increment, summed by
    cause, against the occupancy the windows ended at; and the exact,
    ambiguous and shrink increments against the interval count, which is
    calls minus windows because every call but a window's first closes one.
    The rates are measured from this run, never quoted."""
    by_cause = dict.fromkeys(schema.CAUSES, 0)
    by_reason = dict.fromkeys(schema.REASONS, 0)
    counts = dict.fromkeys(schema.CAUSES, 0)
    final: Dict[str, float] = {}
    calls = 0
    for f in facts:
        if f.kind == schema.CALL:
            calls += 1
            final[f.locator.file] = f.metrics[schema.CONTEXT_TOKENS]
        else:
            cause = f.dims[schema.CAUSE_DIM]
            by_cause[cause] += f.metrics[schema.CONTEXT_DELTA]
            counts[cause] += 1
            if cause == schema.AMBIGUOUS:
                by_reason[f.dims[schema.REASON_DIM]] += 1
    return Reconciliation(
        by_cause, len(final), calls, sum(final.values()),
        sum(counts[c] for c in schema.EXACT_CAUSES),
        counts[schema.AMBIGUOUS], by_reason, counts[schema.SHRINK])


class Selection(NamedTuple):
    """What a view is answered over: the whole windows the window-dimension
    filters kept and the facts the drill filters kept within them."""
    window_where: List[Tuple[str, str]]  # the --where pairs that kept whole windows
    drill: List[Tuple[str, str]]     # the --where pairs that selected within them
    window_facts: List[Fact]        # whole windows kept by ``window_where``
    facts: List[Fact]               # the windows' facts kept by ``drill`` too
    total: float                    # the view's metric over ``facts``, summed once
    reconciliation: Reconciliation  # over ``window_facts``: a drill never changes it

    @property
    def where(self) -> List[Tuple[str, str]]:
        """Every pair, in the order they were applied."""
        return self.window_where + self.drill

    @property
    def n_windows(self) -> int:
        return window_count(self.window_facts)


def selection(facts: List[Fact], where: Where, metric: str) -> Selection:
    """The view's population: the window pins narrow first and keep whole
    windows, the drill pins narrow within them; the total is over the
    drilled facts, the reconciliation over the whole windows."""
    window_where, drill = split(where)
    window_facts = narrow(facts, window_where, metric)
    kept = narrow(window_facts, drill, metric)
    return Selection(window_where, drill, window_facts, kept,
                     total(kept, metric), reconcile(window_facts))
