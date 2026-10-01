"""The local sweep's counts: every local figure the ``sa/`` docstrings cite,
measured by the package over one loaded corpus. A measuring module, not
engine: nothing here mints a fact. ``scripts/local_sweep.py`` runs it over
the live corpus and prints aggregate counts only: no transcript text, no
ids, no paths.
"""
from typing import Dict, Iterator, List, Tuple

from . import query, schema, usage, walk
from .corpus import Corpus, Record, SourceFile, message_id
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


def live_records(loaded: Corpus) -> Iterator[Tuple[SourceFile, List[Record]]]:
    for source in loaded.files:
        yield source, [r for r in source.records if not r.duplicate]


def batched_results(loaded: Corpus) -> Tuple[int, int]:
    """tool_result records carrying more than one block, and all of them."""
    blocks = [sum(b.get("type") == "tool_result" for b in walk.blocks(r.data))
              for _, live in live_records(loaded) for r in live if r.data.get("type") == "user"]
    return sum(n > 1 for n in blocks), sum(n > 0 for n in blocks)


def inside_spans(loaded: Corpus) -> Tuple[int, int, int]:
    """User records strictly inside a split call's span (first to last
    constituent), the calls holding any, and every call."""
    records = calls = holding = 0
    for _, live in live_records(loaded):
        users = [i for i, r in enumerate(live) if r.data.get("type") == "user"]
        last_of = last_constituents(live)
        for call in walk.calls(live, loaded.usages):
            first, last = span(last_of, call)
            inside = sum(first < i < last for i in users)
            records, calls, holding = records + inside, calls + 1, holding + (inside > 0)
    return records, holding, calls


def shared(facts: List[Fact]) -> List[Tuple[int, float]]:
    """multi_contributor intervals, those sharing one tool, those sharing the
    head too; each with its context_delta."""
    multi = [f for f in facts if f.dims.get(schema.REASON_DIM) == schema.MULTI_CONTRIBUTOR]
    tool = [f for f in multi if schema.TOOL_DIM in f.dims]
    head = [f for f in tool if schema.HEAD_DIM in f.dims]
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
    with_live = [(s.records, live) for s, live in live_records(loaded) if live]
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


def report(loaded: Corpus) -> List[str]:
    """Every count as one line, each beside the population it was taken over."""
    facts = walk.forest(loaded)
    rec = query.reconcile(facts)
    (multi, multi_mass), (tool, tool_mass), (head, head_mass) = shared(facts)
    lines = [
        ("%s files, %s windows, %s calls, %s intervals",
         (len(loaded.files), rec.windows, rec.calls, rec.intervals)),
        ("batched tool_result records: %s of %s", batched_results(loaded)),
        ("user records inside call spans: %s, in %s of %s calls", inside_spans(loaded)),
        ("multi_contributor intervals: %s (%s context tokens); sharing one tool %s (%s);"
         " sharing the head too %s (%s)", (multi, multi_mass, tool, tool_mass, head, head_mass)),
        ("message.id re-mints across files: %s (%s spend-equivalents) beside %s live calls",
         reminted(loaded) + (rec.calls,)),
        ("first-record vs live-record window-key disagreements: %s of %s files with a live record",
         key_disagreements(loaded)),
        ("parentUuid links naming a uuid in another file: %s of %s", cross_file_parents(loaded)),
    ]
    return [text % tuple(format(int(round(c)), ",d") for c in counts) for text, counts in lines]
