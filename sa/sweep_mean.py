"""The sweep's average-context figures (``references/PROPOSAL_MEAN_CONTEXT.md``):
a measuring module, not engine. Nothing here mints a fact or changes
``python3 -m sa``; ``sweep.report`` prints these lines under its stamp.

A call holds every increment of its window booked at or before it: its
occupancy telescopes to their sum. So an increment is HELD by the calls of
its window from the one it is booked at through the window's last, and
``sum(delta x held) == sum(call occupancy)`` over any set of whole windows,
signed shrink rows included. Divided by the population's calls it is the
average context per call; it is not additive across populations (the
denominator changes), so it is reported per population, never summed.
LOCAL SWEEP 2026-11-16T01:14Z: the identity holds in 610 of 610 windows;
inherited is 0.60% of the held sum and expands exactly by reference in
10 of 10 windows.
"""
from collections import Counter
from typing import Dict, List, NamedTuple, Optional, Tuple

from . import query, schema, windows
from .schema import Fact

CALL, INCREMENT, DELTA = schema.CALL, schema.INCREMENT, schema.CONTEXT_DELTA


def held(facts: List[Fact]) -> List[Tuple[Fact, int]]:
    """Each increment with the number of its window's calls that hold it.
    ``facts`` are whole windows in walk order (a call is followed by the
    increments it closes), as ``walk.forest`` and ``query.select`` on
    window dimensions leave them; a drill drops calls, so weigh first."""
    calls = Counter(f.window for f in facts if f.kind == CALL)
    seen: Counter = Counter()
    out = []
    for f in facts:
        if f.kind == CALL:
            seen[f.window] += 1
        else:
            out.append((f, calls[f.window] - seen[f.window] + 1))
    return out


def weighted(facts: List[Fact]) -> List[Fact]:
    """The increments with ``context_delta`` scaled by ``held``: what
    ``query.group`` and ``query.total`` then read as calls x tokens held."""
    return [f._replace(metrics={DELTA: f.metrics[DELTA] * n}) for f, n in held(facts)]


class Identity(NamedTuple):
    held: float       # sum of delta x held
    occupancy: float  # sum of every call's context_tokens
    windows: int
    holding: int      # windows where the two agree

    @property
    def holds(self) -> bool:
        return self.held == self.occupancy and self.windows == self.holding


def identity(facts: List[Fact]) -> Identity:
    """The identity checked per window and in total, like ``query.reconcile``."""
    mass: Dict[schema.WindowKey, float] = Counter()
    occ: Dict[schema.WindowKey, float] = Counter()
    for f in weighted(facts):
        mass[f.window] += f.metrics[DELTA]
    for f in facts:
        if f.kind == CALL:
            occ[f.window] += f.metrics[schema.CONTEXT_TOKENS]
    return Identity(sum(mass.values()), sum(occ.values()), len(occ),
                    sum(mass[k] == occ[k] for k in occ))


def expand(facts: List[Fact]) -> Tuple[List[Fact], int, int]:
    """``weighted(facts)`` with each inherited increment replaced by its
    parent's breakdown to the branch call (``query.through``), nested
    inheritance recursively: each part keeps its cause, tool and command,
    takes the fork's window dimensions and the fork's held count. Returns
    the facts, the inherited increments expanded, and those whose parts
    telescope exactly to the inherited mass."""
    by_window: Dict[schema.WindowKey, List[Fact]] = {}
    for f in facts:
        by_window.setdefault(f.window, []).append(f)
    window_dims = set(schema.WINDOW_DIMENSIONS)

    def parts(f: Fact, depth: int = 0) -> Optional[List[Fact]]:
        key, call = f.evidence.get(schema.PARENT_WINDOW), f.evidence.get(schema.BRANCH_CALL)
        found = [p for p in query.through(by_window.get(key, []), key, call) if p.kind == INCREMENT]
        if not found or depth > 32:
            return None
        out = []
        for p in found:
            nested = parts(p, depth + 1) if p.dims.get(schema.CAUSE_DIM) == schema.INHERITED else None
            out.extend(nested if nested is not None else [p])
        return out

    out, expanded, exact = [], 0, 0
    for f, n in held(facts):
        found = parts(f) if f.dims.get(schema.CAUSE_DIM) == schema.INHERITED else None
        if found is None:
            out.append(f._replace(metrics={DELTA: f.metrics[DELTA] * n}))
            continue
        expanded += 1
        exact += sum(p.metrics[DELTA] for p in found) == f.metrics[DELTA]
        own = {k: v for k, v in f.dims.items() if k in window_dims}
        for p in found:
            dims = dict(own, **{k: v for k, v in p.dims.items() if k not in window_dims})
            out.append(p._replace(dims=dims, window=f.window, metrics={DELTA: p.metrics[DELTA] * n}))
    return out, expanded, exact


def shares(facts: List[Fact], dim: str) -> Dict[str, float]:
    """Each regular row's share of the table's base (``query.group``)."""
    table = query.group(facts, dim, DELTA)
    return {r.value: table.share(r.mass) for r in table.rows if r.kind == query.REGULAR}


def compare(before: Dict[str, float], after: Dict[str, float], n: int = 10) -> str:
    """The top ``n`` by ``before`` with their rank and share under
    ``after``, and how many of them stay in the top ``n``."""
    rb, ra = sorted(before, key=lambda v: -before[v]), sorted(after, key=lambda v: -after[v])
    top = rb[:n]
    moved = sum(ra.index(v) != i for i, v in enumerate(top) if v in ra)
    kept = len(set(top) & set(ra[:n]))
    cells = ["%s %d>%s %.1f>%.1f" % (v, i + 1, ra.index(v) + 1 if v in ra else "-",
                                     100 * before[v], 100 * after.get(v, 0)) for i, v in enumerate(top)]
    swing = max((abs(before[v] - after.get(v, 0)) for v in top), default=0)
    return "%d of top %d kept, %d moved, max swing %.1f pts: %s" % (
        kept, len(top), moved, 100 * swing, "; ".join(cells))


def mean(calls: List[Fact]) -> float:
    """The average context per call over ``calls``: per population, never summed."""
    return sum(c.metrics[schema.CONTEXT_TOKENS] for c in calls) / len(calls) if calls else 0


def leaders(facts: List[Fact], dim: str) -> Tuple[int, int]:
    """Sessions whose largest ``dim`` row differs between the sum and the
    average, of the sessions with at least two rows: the drill a user runs."""
    by: Dict[str, List[Fact]] = {}
    for f in facts:
        by.setdefault(f.dims.get(schema.SESSION_DIM), []).append(f)
    differ = counted = 0
    for mine in by.values():
        before = shares(query.selection(mine, [], DELTA, False).facts, dim)
        after = shares(weighted(mine), dim)
        if len(before) > 1:
            counted += 1
            differ += max(before, key=before.get) != max(after, key=after.get)
    return differ, counted


def peaks(facts: List[Fact]) -> Dict[schema.WindowKey, Tuple[float, bool]]:
    """Each window's peak ``context_tokens`` and whether it is a subagent's."""
    out: Dict[schema.WindowKey, Tuple[float, bool]] = {}
    for f in facts:
        if f.kind == CALL:
            peak = max(out.get(f.window, (0, False))[0], f.metrics[schema.CONTEXT_TOKENS])
            out[f.window] = (peak, schema.SUBAGENT_DIM in f.dims)
    return out


def rank(values: List[float], p: float) -> float:
    """The nearest-rank percentile: a value some window reached, never an
    interpolation between two."""
    ordered = sorted(values)
    return ordered[max(0, -(-len(ordered) * p // 100) - 1)] if ordered else 0


def shape(found: Dict[schema.WindowKey, Tuple[float, bool]], sub: Optional[bool]) -> str:
    """median / p90 / max of the peaks of the windows (all, main or subagent)."""
    mine = {k: v[0] for k, v in found.items() if sub is None or v[1] == sub}
    if not mine:
        return "0 windows"
    top = max(mine, key=lambda k: mine[k])
    return "%d windows median %s p90 %s max %s (window=%s)" % (
        len(mine), *("{:,}".format(int(rank(list(mine.values()), p))) for p in (50, 90, 100)),
        schema.window_value(top))


def parents(loaded, cuts) -> Tuple[int, ...]:
    """Fork and replayed windows; those whose parent's branch call was read;
    those whose parent file was modified no earlier than theirs (so no
    ``--since`` keeps the copy and drops the parent); the fork-context-ref
    files and the copied (duplicate) records they carry; the copied records
    every other fork or replayed file carries."""
    copies = [n for n, ws in cuts.items() if ws and ws[0].start in (schema.FORK, schema.REPLAYED)]
    found = windows.inherits(loaded, cuts)
    path = {s.name: s.path for s in loaded.files}
    newer = sum(path[i.parent.file].stat().st_mtime >= path[n].stat().st_mtime
                for n, i in found.items() if n in copies)
    refs = {s.name for s in loaded.files if any(r.data.get("type") == windows.FORK_REF for r in s.records)}
    dup = {s.name: sum(r.duplicate for r in s.records) for s in loaded.files if s.name in copies}
    return (len(copies), sum(n in found for n in copies), newer, len(refs),
            sum(v for n, v in dup.items() if n in refs), sum(v for n, v in dup.items() if n not in refs))


def report(loaded, facts: List[Fact], cuts) -> List[str]:
    """The average-context lines, each beside its population."""
    check = identity(facts)
    calls = [f for f in facts if f.kind == CALL]
    sub = sum(schema.SUBAGENT_DIM in f.dims for f in calls)
    heavy = weighted(facts)
    flat, n_exp, n_exact = expand(facts)
    once = query.selection(facts, [], DELTA, False).facts
    inherited = sum(f.metrics[DELTA] for f in heavy if f.dims.get(schema.CAUSE_DIM) == schema.INHERITED)
    lines = [
        "average context per call: sum held %s vs sum call occupancy %s, %s in %d of %d windows; "
        "%s calls (main %s, subagent %s); average %s tokens" % (
            "{:,}".format(int(check.held)), "{:,}".format(int(check.occupancy)),
            "holds" if check.holds else "MISMATCH", check.holding, check.windows,
            *("{:,}".format(n) for n in (len(calls), len(calls) - sub, sub)), "{:,}".format(int(round(check.held / max(1, len(calls)))))),
        "average by population: main %s, subagent %s; calls holding over 200,000 tokens: %s of %s"
        % tuple("{:,}".format(int(round(x))) for x in (
            mean([c for c in calls if schema.SUBAGENT_DIM not in c.dims]),
            mean([c for c in calls if schema.SUBAGENT_DIM in c.dims]),
            sum(c.metrics[schema.CONTEXT_TOKENS] > 200000 for c in calls), len(calls))),
        "inherited under the average: %s of %s (%.2f%%); expanded by through %d of %d, exact %d"
        % ("{:,}".format(int(inherited)), "{:,}".format(int(check.held)),
           100 * inherited / (check.held or 1), n_exp,
           sum(f.dims.get(schema.CAUSE_DIM) == schema.INHERITED for f in heavy), n_exact),
        "fork and replayed windows %s, parent read %s, parent file no older %s; fork-context-ref "
        "files %s carrying %s copied records; the others carry %s"
        % tuple("{:,}".format(n) for n in parents(loaded, cuts)),
    ]
    main = [f for f in facts if schema.SUBAGENT_DIM not in f.dims]
    main_once, main_heavy = query.selection(main, [], DELTA, False).facts, weighted(main)
    for dim in (schema.CAUSE_DIM, schema.STARTED_BY_DIM, schema.TOOL_DIM, schema.COMMAND_DIM):
        lines.append("%s, sum>average: %s" % (dim, compare(shares(once, dim), shares(heavy, dim))))
        if dim != schema.STARTED_BY_DIM:
            lines.append("%s, main windows: %s" % (dim, compare(shares(main_once, dim), shares(main_heavy, dim), 5)))
    lines.append("cause, expanded: %s" % compare(shares(once, schema.CAUSE_DIM), shares(flat, schema.CAUSE_DIM)))
    for dim in (schema.CAUSE_DIM, schema.TOOL_DIM, schema.COMMAND_DIM):
        lines.append("sessions whose top %s differs, sum vs average: %d of %d" % ((dim,) + leaders(facts, dim)))
    found = peaks(facts)
    lines += ["window peaks %s: %s" % (name, shape(found, sub))
              for name, sub in (("all", None), ("main", False), ("subagent", True))]
    return lines
