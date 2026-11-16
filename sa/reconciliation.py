"""The reconciliation: chain integrity over whole windows, keyed by
identity. Two identities hold by construction (``walk``), so a MISMATCH is
a bug in this tool, exit status 1:

- every booked increment (``inherited`` included), summed, equals the
  occupancy the windows ended at (the final window sizes);
- every increment's ``context_held`` (its delta times the calls that held
  it, ``walk.held``), summed, equals every call's occupancy, summed: per
  window, so the average context per call's rows add up to it (D-PER-CALL).

The exact, ambiguous and shrink increments are checked against the gap
count, calls minus windows, because every call but a window's first closes
one. The rates are measured from this run, never quoted."""
from typing import Dict, Iterable, NamedTuple

from . import schema
from .schema import Fact


class Reconciliation(NamedTuple):
    by_cause: Dict[str, float]  # context_delta booked per cause
    windows: int
    calls: int
    final_occupancy: float      # last call's context_tokens, summed over windows
    exact: int
    ambiguous: int
    by_reason: Dict[str, int]
    shrink: int
    held: float = 0             # context_held, summed over increments
    occupancy: float = 0        # every call's context_tokens, summed
    held_windows: int = 0       # windows whose held sum equals their calls' occupancy

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
    def held_holds(self) -> bool:
        return self.held == self.occupancy and self.held_windows == self.windows

    @property
    def count_holds(self) -> bool:
        return self.exact + self.ambiguous + self.shrink == self.intervals

    @property
    def holds(self) -> bool:
        return self.mass_holds and self.held_holds and self.count_holds


def reconcile(facts: Iterable[Fact]) -> Reconciliation:
    """Both identities and the gap count over ``facts``, whole windows."""
    by_cause = dict.fromkeys(schema.CAUSES, 0)
    by_reason = dict.fromkeys(schema.REASONS, 0)
    counts = dict.fromkeys(schema.CAUSES, 0)
    final: Dict[schema.WindowKey, float] = {}
    held: Dict[schema.WindowKey, float] = {}
    occupancy: Dict[schema.WindowKey, float] = {}
    calls = 0
    for f in facts:
        if f.kind == schema.CALL:
            calls += 1
            final[f.window] = f.metrics[schema.CONTEXT_TOKENS]
            occupancy[f.window] = occupancy.get(f.window, 0) + f.metrics[schema.CONTEXT_TOKENS]
        else:
            cause = f.dims[schema.CAUSE_DIM]
            by_cause[cause] += f.metrics[schema.CONTEXT_DELTA]
            held[f.window] = held.get(f.window, 0) + f.metrics.get(schema.CONTEXT_HELD, 0)
            counts[cause] += 1
            if cause == schema.AMBIGUOUS:
                by_reason[f.dims[schema.REASON_DIM]] += 1
    return Reconciliation(
        by_cause, len(final), calls, sum(final.values()),
        sum(counts[c] for c in schema.EXACT_CAUSES),
        counts[schema.AMBIGUOUS], by_reason, counts[schema.SHRINK],
        sum(held.values()), sum(occupancy.values()),
        sum(held.get(k, 0) == v for k, v in occupancy.items()))
