"""Select, group and reconcile facts. No rendering here."""
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

from . import schema
from .schema import Fact

Where = Iterable[Tuple[str, str]]


def select(facts: Iterable[Fact], where: Where) -> List[Fact]:
    """Facts whose dimensions equal every ``(dim, value)`` pair."""
    pairs = [(schema.check_dimension(dim), value) for dim, value in where]
    return [f for f in facts
            if all(dim in f.dims and str(f.dims[dim]) == value for dim, value in pairs)]


# The three kinds of row a table has. Only regular rows take part in shares.
REGULAR = "regular"
RESIDUAL = "residual"  # facts that lack the grouped dimension
SIGNED = "signed"      # shrink: its mass is negative by definition


class Row(NamedTuple):
    value: str
    mass: float
    count: int
    share: Optional[float]  # of the regular rows' mass; None when there is none
    kind: str


def group(facts: Iterable[Fact], dim: str, metric: str) -> List[Row]:
    """One row per value of ``dim``, regular rows by descending mass, then
    the residual row for facts that lack ``dim``, then the signed shrink row.

    The metric is read only from facts of its carrier kind. A peak metric
    refuses to be grouped (``usage.usage_context`` has the measurement).
    Shrink increments always land in their own signed row whatever ``dim``
    is, so no other row mixes signed mass and every share is a share of mass
    that was added.
    """
    spec = schema.metric(metric)
    if spec.aggregation == schema.PEAK:
        raise ValueError("%s is a peak; it has no sum. Use largest()." % metric)
    schema.check_dimension(dim)
    mass: Dict[Tuple[str, str], float] = {}
    count: Dict[Tuple[str, str], int] = {}
    for f in facts:
        if f.kind != spec.carrier:
            continue
        if f.dims.get("cause") == schema.SHRINK:
            key = (schema.SHRINK, SIGNED)
        elif f.dims.get(dim) is None:
            key = (schema.RESIDUAL_LABEL, RESIDUAL)
        else:
            key = (str(f.dims[dim]), REGULAR)
        mass[key] = mass.get(key, 0) + f.metrics[metric]
        count[key] = count.get(key, 0) + 1
    regular = sorted((k for k in mass if k[1] == REGULAR), key=lambda k: -mass[k])
    base = sum(mass[k] for k in regular)
    rows = [Row(k[0], mass[k], count[k], mass[k] / base if base else None, REGULAR)
            for k in regular]
    for key in ((schema.RESIDUAL_LABEL, RESIDUAL), (schema.SHRINK, SIGNED)):
        if key in mass:
            rows.append(Row(key[0], mass[key], count[key], None, key[1]))
    return rows


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
            final[f.locator.file] = f.metrics["context_tokens"]
        else:
            cause = f.dims["cause"]
            by_cause[cause] += f.metrics["context_delta"]
            counts[cause] += 1
            if cause == schema.AMBIGUOUS:
                by_reason[f.dims["reason"]] += 1
    return Reconciliation(
        by_cause, len(final), calls, sum(final.values()),
        sum(counts[c] for c in schema.EXACT_CAUSES),
        counts[schema.AMBIGUOUS], by_reason, counts[schema.SHRINK])
