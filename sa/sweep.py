"""The local sweep's counts: every local figure the ``sa/`` docstrings cite,
measured by the package over one loaded corpus. A measuring module, not
engine: nothing here mints a fact. ``python3 -m sa.sweep`` runs it over the
live corpus under ``~/.claude/projects``, which changes with every session,
so the figures are a snapshot of one machine at one minute, stamped on the
first line, which a docstring cites. Aggregate counts only: no transcript
text, no ids, no paths.
"""
import datetime
from bisect import bisect_left, bisect_right
from collections import Counter
from typing import Dict, List, Tuple

from . import query, schema, sweep_mean, usage, walk, windows
from .corpus import Corpus, Record, default_root, load, message_id
from .schema import Fact


def last_constituents(records: List[Record]) -> Dict[str, int]:
    """Each ``message.id``'s last index in ``records``, in one pass."""
    last = {message_id(r.data): i for i, r in enumerate(records)}
    last.pop(None, None)  # id-less records are no call's constituents
    return last


def span(last_of: Dict[str, int], call: walk.Call) -> Tuple[int, int]:
    """The indices of a call's first and last constituent, the records
    sharing its ``message.id`` (``(first, first)`` for an id-less call). A
    split call's results sit strictly inside its span (parallel tool use),
    which is why ``walk`` slices an interval from the previous call's FIRST
    constituent."""
    return call.first, last_of.get(message_id(call.record.data), call.first)


def batched_results(loaded: Corpus) -> Tuple[int, int]:
    """tool_result records carrying more than one block, and all of them."""
    blocks = [sum(b.get("type") == "tool_result" for b in walk.blocks(r.data))
              for source in loaded.files for r in source.live if r.data.get("type") == "user"]
    return sum(n > 1 for n in blocks), sum(n > 0 for n in blocks)


def inside_spans(loaded: Corpus) -> Tuple[int, int, int]:
    """User records strictly inside a split call's span (first to last
    constituent), the calls holding any, and every call. One pass per file
    indexes its user records; each span then counts them by bisection."""
    records = calls = holding = 0
    for source in loaded.files:
        live = source.live
        users = [i for i, r in enumerate(live) if r.data.get("type") == "user"]  # ascending
        last_of = last_constituents(live)
        for call in walk.calls(live, loaded.usages):
            first, last = span(last_of, call)
            inside = bisect_left(users, last) - bisect_right(users, first)
            records, calls, holding = records + inside, calls + 1, holding + (inside > 0)
    return records, holding, calls


def shared(facts: List[Fact]) -> List[Tuple[int, float]]:
    """multi_contributor intervals, those sharing one tool, those sharing the
    head too; each with its context_delta."""
    multi = [f for f in facts if f.dims.get(schema.REASON_DIM) == schema.SEVERAL]
    tool = [f for f in multi if schema.TOOL_DIM in f.dims]
    head = [f for f in tool if schema.COMMAND_DIM in f.dims]
    return [(len(fs), sum(f.metrics[schema.CONTEXT_DELTA] for f in fs)) for fs in (multi, tool, head)]


def reminted(loaded: Corpus) -> Tuple[int, float]:
    """message.ids a later file carries under a uuid of its own (a fork
    re-minting its parent's last call): the phantom calls dedup drops, and
    their spend."""
    seen, ids = set(), set()
    for source in loaded.files:
        for r in source.records:
            uuid = r.data.get("uuid")
            if r.duplicate and uuid and uuid not in seen:
                ids.add(message_id(r.data))
            if uuid:
                seen.add(uuid)
    return len(ids), sum(usage.usage_spend(usage.max_merge_usage(loaded.usages[i])) for i in ids)


def key_disagreements(loaded: Corpus) -> Tuple[int, int]:
    """Files whose first record and first live record disagree on sessionId
    or agentId, of the files with a live record."""
    keys = ("sessionId", "agentId")
    with_live = [(s.records, s.live) for s in loaded.files if s.live]
    return sum(any(walk.first_value(every, k) != walk.first_value(live, k) for k in keys)
               for every, live in with_live), len(with_live)


def cross_file_parents(loaded: Corpus) -> Tuple[int, int]:
    """parentUuid links naming a uuid outside their own file, and all of them."""
    linked = crossing = 0
    for source in loaded.files:
        uuids = {r.data.get("uuid") for r in source.records}
        for r in source.records:
            parent = r.data.get("parentUuid")
            if parent:
                linked, crossing = linked + 1, crossing + (parent not in uuids)
    return crossing, linked


def cut(loaded: Corpus) -> Dict[str, List[windows.Window]]:
    """Every file's windows, as ``walk.forest`` cuts them."""
    return {source.name: windows.cut(source, loaded.usages) for source in loaded.files}


def starts(cuts: Dict[str, List[windows.Window]]) -> Tuple[int, ...]:
    """Windows by what began them, in ``schema.STARTS`` order."""
    found = Counter(w.start for found in cuts.values() for w in found)
    return tuple(found[start] for start in schema.STARTS)


def compacting(loaded: Corpus) -> Tuple[int, int, int, int]:
    """Compaction markers that end their file (starting no window), all
    live markers, and the api-request records whose querySource is a
    compaction's (the summarising call), of all api-request records."""
    marks = windows.compactions(loaded)
    requests = [r for s in loaded.files for r in s.records if r.data.get("type") == "api-request"]
    summarising = sum("compact" in str(r.data.get("querySource")) for r in requests)
    return marks["ended"], sum(marks.values()), summarising, len(requests)


def continuations(loaded: Corpus) -> Tuple[int, int]:
    """Files holding a replayed record after a live one (a copy that is not
    a prefix: a window that would span files), and all files."""
    def continues(source) -> bool:
        flags = [r.duplicate for r in source.records if r.data.get("uuid") or message_id(r.data)]
        return False in flags and any(flags[flags.index(False):])
    return sum(continues(s) for s in loaded.files), len(loaded.files)


def fork_heads(loaded: Corpus, cuts: Dict[str, List[windows.Window]]) -> Tuple[int, str, str]:
    """Windows that inherit (a fork or replay whose parent call was read),
    and the least and greatest ratio of their first call's occupancy to
    the inherited occupancy."""
    found = windows.inherits(loaded, cuts)
    ratios = [usage.usage_context(cuts[name][0].calls[0].usage) / inherit.mass
              for name, inherit in found.items() if inherit.mass]
    return len(found), "%.3f" % min(ratios or [0]), "%.3f" % max(ratios or [0])


def fork_marks(loaded: Corpus, cuts: Dict[str, List[windows.Window]]) -> Tuple[int, ...]:
    """Fork windows (``windows.file_start``); those the file marks itself
    (``windows.marked_fork``), by an api-request and by a fork-context-ref;
    those replaying a prefix; those whose parent was found (``inherits``),
    so ``query.orphan_forks`` would count the rest."""
    forks = [s for s in loaded.files if cuts.get(s.name) and cuts[s.name][0].start == schema.FORK]
    def has(s, kind: str, **fields) -> bool:
        return any(r.data.get("type") == kind and all(r.data.get(k) == v for k, v in fields.items())
                   for r in s.records)
    found = windows.inherits(loaded, cuts)
    return (len(forks), sum(map(windows.marked_fork, forks)),
            sum(has(s, "api-request", querySource=windows.FORK_SOURCE) for s in forks),
            sum(has(s, windows.FORK_REF) for s in forks), sum(map(windows.replays, forks)),
            sum(s.name in found for s in forks))


def report(loaded: Corpus) -> List[str]:
    """Every count as one line, each beside the population it was taken over."""
    facts = walk.forest(loaded)
    rec = query.reconcile(facts)
    (multi, multi_mass), (tool, tool_mass), (head, head_mass) = shared(facts)
    cuts = cut(loaded)
    lines = [
        ("%s files, %s windows, %s calls, %s intervals",
         (len(loaded.files), rec.windows, rec.calls, rec.intervals)),
        ("batched tool_result records: %s of %s", batched_results(loaded)),
        ("user records inside call spans: %s, in %s of %s calls", inside_spans(loaded)),
        ("multi_contributor intervals: %s (%s " + schema.metric(schema.CONTEXT_DELTA).unit
         + "); sharing one tool %s (%s); sharing the head too %s (%s)",
         (multi, multi_mass, tool, tool_mass, head, head_mass)),
        ("message.id re-mints across files: %s (%s " + schema.metric(schema.SPEND).unit
         + ") beside %s live calls", reminted(loaded) + (rec.calls,)),
        ("first-record vs live-record window-key disagreements: %s of %s files with a live record",
         key_disagreements(loaded)),
        ("parentUuid links naming a uuid in another file: %s of %s", cross_file_parents(loaded)),
        ("windows by start: " + ", ".join("%s %%s" % s for s in schema.STARTS), starts(cuts)),
        ("compaction markers ending their file: %s of %s; compaction api-requests: %s of %s",
         compacting(loaded)),
        ("files replaying another after a live record: %s of %s", continuations(loaded)),
        ("inheriting windows: %s; first call / inherited occupancy: min %s, max %s",
         fork_heads(loaded, cuts)),
        ("fork windows %s: marked by the file %s (api-request %s, fork-context-ref %s), replaying"
         " a prefix %s, parent found %s", fork_marks(loaded, cuts)),
    ]
    return [text % tuple(c if isinstance(c, str) else format(int(round(c)), ",d") for c in counts)
            for text, counts in lines] + sweep_mean.report(loaded, facts, cuts)


if __name__ == "__main__":
    first, *rest = report(load(default_root()))
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    print("\n".join(["LOCAL SWEEP %s: %s" % (stamp, first)] + rest))
