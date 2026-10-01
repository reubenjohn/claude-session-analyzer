"""Select, group and reconcile facts. No rendering here."""
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

from . import schema
from .schema import Fact


def select(facts, where):
    # type: (Iterable[Fact], Iterable[Tuple[str, str]]) -> List[Fact]
    """Facts whose dimensions equal every ``(dim, value)`` pair."""
    pairs = [(schema.check_dimension(dim), value) for dim, value in where]
    return [f for f in facts
            if all(dim in f.dims and str(f.dims[dim]) == value for dim, value in pairs)]


class Row(NamedTuple):
    value: str
    mass: float
    count: int
    share: Optional[float]  # of the non-residual, non-signed mass; None if excluded
    signed: bool            # a shrink row: its mass is negative by definition


def group(facts, dim, metric):
    # type: (Iterable[Fact], str, str) -> List[Row]
    """One row per value of ``dim``, regular rows by descending mass, then
    the residual row for facts that lack ``dim``, then the signed shrink row.

    The metric is read only from facts of its carrier kind. A peak metric
    refuses to be grouped: a summed peak once printed 4,950,327 against a
    true high-water mark of 131,612 (37.6x). Shrink increments always land
    in their own signed row whatever ``dim`` is, so no other row mixes
    signed mass and every share is a share of mass that was added.
    """
    spec = schema.metric(metric)
    if spec.aggregation == schema.PEAK:
        raise ValueError("%s is a peak; it has no sum. Use largest()." % metric)
    schema.check_dimension(dim)
    mass = {}   # type: Dict[Tuple[str, bool], float]
    count = {}  # type: Dict[Tuple[str, bool], int]
    for f in facts:
        if f.kind != spec.carrier:
            continue
        if f.dims.get("cause") == schema.SHRINK:
            key = (schema.SHRINK, True)
        else:
            value = f.dims.get(dim)
            key = (schema.RESIDUAL if value is None else str(value), False)
        mass[key] = mass.get(key, 0) + f.metrics[metric]
        count[key] = count.get(key, 0) + 1
    regular = sorted((k for k in mass if not k[1] and k[0] != schema.RESIDUAL),
                     key=lambda k: -mass[k])
    base = sum(mass[k] for k in regular)
    rows = [Row(k[0], mass[k], count[k], mass[k] / base if base else None, False)
            for k in regular]
    for key in ((schema.RESIDUAL, False), (schema.SHRINK, True)):
        if key in mass:
            rows.append(Row(key[0], mass[key], count[key], None, key[1]))
    return rows


def largest(facts, metric):
    # type: (Iterable[Fact], str) -> Optional[Fact]
    """The fact carrying the largest value of ``metric``: the only honest
    report of a peak is the single window where it happened."""
    spec = schema.metric(metric)
    carried = [f for f in facts if f.kind == spec.carrier]
    return max(carried, key=lambda f: f.metrics[metric]) if carried else None


class Reconciliation(NamedTuple):
    by_cause: Dict[str, float]  # context_delta booked per cause
    windows: int
    final_occupancy: float      # last call's context_tokens, summed over windows
    intervals: int
    exact: int
    ambiguous: int
    by_reason: Dict[str, int]
    shrink: int

    @property
    def booked(self):
        # type: () -> float
        return sum(self.by_cause.values())

    @property
    def holds(self):
        # type: () -> bool
        return self.booked == self.final_occupancy


def reconcile(facts):
    # type: (Iterable[Fact]) -> Reconciliation
    """Chain integrity over whole windows: every booked increment, summed by
    cause, against the occupancy the windows ended at. Each interval closes
    with exactly one of an exact, ambiguous or shrink increment, so those
    three counts partition the intervals and their rates are measured from
    this run, never quoted."""
    by_cause = dict.fromkeys(schema.CAUSES, 0)
    by_reason = dict.fromkeys(schema.REASONS, 0)
    counts = dict.fromkeys(schema.CAUSES, 0)
    final = {}  # type: Dict[str, float]
    for f in facts:
        if f.kind == schema.CALL:
            final[f.locator.file] = f.metrics["context_tokens"]
        else:
            cause = f.dims["cause"]
            by_cause[cause] += f.metrics["context_delta"]
            counts[cause] += 1
            if cause == schema.AMBIGUOUS:
                by_reason[f.dims["reason"]] += 1
    exact = sum(counts[c] for c in schema.EXACT_CAUSES)
    return Reconciliation(
        by_cause, len(final), sum(final.values()),
        exact + counts[schema.AMBIGUOUS] + counts[schema.SHRINK],
        exact, counts[schema.AMBIGUOUS], by_reason, counts[schema.SHRINK])
