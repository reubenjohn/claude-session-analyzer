"""One dated snapshot of the live local corpus: every local figure the
``sa/`` docstrings cite, counted by the package itself.

The corpus under ``~/.claude/projects`` changes with every session, so the
figures are a snapshot of one machine on one day, not reproducible
elsewhere; a docstring cites them by date and this script. Prints aggregate
counts only: no transcript text, no ids, no paths.
"""
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sa import corpus, query, schema, usage, walk  # noqa: E402


def live_records(loaded):
    for source in loaded.files:
        yield source, [r for r in source.records if not r.duplicate]


def batched_results(loaded):
    """tool_result records, and those carrying more than one block."""
    blocks = [sum(b.get("type") == "tool_result" for b in walk._blocks(r.data))
              for _, live in live_records(loaded) for r in live if r.data.get("type") == "user"]
    return sum(n > 1 for n in blocks), sum(n > 0 for n in blocks)


def inside_spans(loaded):
    """User records strictly inside a split call's span (first to last
    constituent), the calls holding any, and every call."""
    records = calls = holding = 0
    for _, live in live_records(loaded):
        last = {}
        for i, r in enumerate(live):
            key = corpus.message_id(r.data)
            if key is not None:
                last[key] = i
        users = [i for i, r in enumerate(live) if r.data.get("type") == "user"]
        for call in walk.calls(live, loaded.usages):
            end = last.get(corpus.message_id(call.record.data), call.first)
            inside = sum(call.first < i < end for i in users)
            records, calls, holding = records + inside, calls + 1, holding + (inside > 0)
    return records, holding, calls


def shared(facts):
    """multi_contributor intervals, those sharing one tool, those sharing the
    head too; each with its context_delta."""
    multi = [f for f in facts if f.dims.get(schema.REASON_DIM) == schema.MULTI_CONTRIBUTOR]
    tool = [f for f in multi if schema.TOOL_DIM in f.dims]
    head = [f for f in tool if schema.HEAD_DIM in f.dims]
    return [(len(fs), sum(f.metrics[schema.CONTEXT_DELTA] for f in fs)) for fs in (multi, tool, head)]


def reminted(loaded):
    """message.ids a later file carries under a uuid of its own (a fork
    re-minting its parent's last call): the phantom calls dedup drops, and
    their spend."""
    seen, ids = set(), set()
    for source in loaded.files:
        for r in source.records:
            uuid = r.data.get("uuid")
            if r.duplicate and uuid and uuid not in seen:
                ids.add(corpus.message_id(r.data))
            if uuid:
                seen.add(uuid)
    return len(ids), sum(usage.usage_spend(usage.max_merge_usage(loaded.usages[i])) for i in ids)


def key_disagreements(loaded):
    """Files whose first record and first live record disagree on sessionId
    or agentId, of the files with a live record."""
    keys = ("sessionId", "agentId")
    with_live = [(s.records, live) for s, live in live_records(loaded) if live]
    return sum(any(walk._first_value(every, k) != walk._first_value(live, k) for k in keys)
               for every, live in with_live), len(with_live)


def cross_file_parents(loaded):
    """parentUuid links, and those naming a uuid outside their own file."""
    linked = crossing = 0
    for source in loaded.files:
        uuids = {r.data.get("uuid") for r in source.records}
        for r in source.records:
            parent = r.data.get("parentUuid")
            if parent:
                linked, crossing = linked + 1, crossing + (parent not in uuids)
    return crossing, linked


def main():
    loaded = corpus.load(corpus.default_root())
    facts = [f for source in loaded.files for f in walk.walk(source, loaded.usages)]
    rec = query.reconcile(facts)
    (multi, multi_mass), (tool, tool_mass), (head, head_mass) = shared(facts)
    lines = [
        ("LOCAL SWEEP " + str(datetime.date.today()) + ": %s files, %s windows, %s calls, %s intervals",
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
    for text, counts in lines:
        print(text % tuple(format(int(round(c)), ",d") for c in counts))


if __name__ == "__main__":
    main()
