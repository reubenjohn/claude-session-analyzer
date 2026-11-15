"""The UX-pass probe, window-start half (``references/UX_FEEDBACK.md``
track B): how a window starts (``triggers``), what a fork or resume
inherits against its parent (``inherited``) and what a fresh window's head
holds (``head_content``), measured with the parser itself. Run both halves
with ``python3 -m sa.probe_ux``. Aggregate counts only: no transcript text,
no ids, no paths.
"""
import json
from collections import Counter
from typing import Dict, List, Optional, Tuple

from . import query, schema, usage, walk
from .corpus import Corpus, SourceFile, message_id
from .probe_compaction import HOUR, ctx, fmt, is_subagent, pct, stamp, tally

# 3. triggers

def replay_prefix(source: SourceFile) -> bool:
    """The file opens with records another file owns: it inherited them."""
    for r in source.records:
        if r.data.get("uuid") or message_id(r.data):
            return r.duplicate
    return False


def trigger(source: SourceFile) -> Tuple[str, List[str]]:
    """A window's start class and the conflicts among its deciding fields."""
    sub, fork_ref = is_subagent(source), any(
        r.data.get("type") == "fork-context-ref" for r in source.records)
    agent = walk.first_value(source.live, "agentId")
    replay = replay_prefix(source)
    sources = {r.data.get("querySource") for r in source.live if r.data.get("type") == "api-request"}
    conflicts = []
    if sub != bool(agent):
        conflicts.append("path vs agentId")
    if ("agent:builtin:fork" in sources) != (fork_ref or replay) and sources:
        conflicts.append("fork querySource vs inherited prefix")
    if fork_ref:
        kind = "fork (fork-context-ref)"
    elif replay:
        kind = "fork/branch (replayed prefix)" if sub else "resume/branch (replayed prefix)"
    else:
        kind = "subagent" if sub else "session start"
    return kind, conflicts


def triggers(loaded: Corpus) -> List[str]:
    kinds, conflicts, labelled = Counter(), Counter(), Counter()
    gaps = gap_shrinks = 0
    for source in loaded.files:
        calls = walk.calls(source.live, loaded.usages)
        if not calls:
            continue
        kind, found = trigger(source)
        kinds[kind] += 1
        for c in found:
            conflicts[c] += 1
        labelled["with api-request" if any(r.data.get("type") == "api-request" for r in source.live)
                 else "without"] += 1
        for k in range(1, len(calls)):
            t0, t1 = stamp(calls[k - 1].record.data), stamp(calls[k].record.data)
            if t0 and t1 and t1 - t0 >= HOUR:
                gaps += 1
                gap_shrinks += ctx(calls[k]) < ctx(calls[k - 1])
    return [
        "window starts (files with a call): %s" % tally(kinds),
        "windows with a conflicting field: %s" % tally(conflicts),
        "windows carrying api-request records (querySource): %s" % tally(labelled),
        "intervals across a >=1h gap (resume in place): %s, of which shrink %s"
        % (fmt(gaps), fmt(gap_shrinks)),
    ]


# 4. inherited prefixes

def occupancy_through(owner: SourceFile, usages, target: str) -> Optional[float]:
    """The owner window's booked context_delta through the call whose
    message.id is ``target``: its facts up to the next call fact."""
    booked, hit, lines = 0.0, False, {r.line: r for r in owner.records}
    for f in walk.walk(owner, usages):
        if f.kind == schema.CALL:
            if hit:
                return booked
            hit = message_id(lines[f.locator.line].data) == target
        else:
            booked += f.metrics[schema.CONTEXT_DELTA]
    return booked if hit else None


def inherited(loaded: Corpus, facts: List[schema.Fact]) -> List[str]:
    owner_of: Dict[str, SourceFile] = {}
    by_uuid: Dict[str, Tuple[SourceFile, int]] = {}
    for source in loaded.files:
        for i, r in enumerate(source.records):
            call, uuid = message_id(r.data), r.data.get("uuid")
            if call and not r.duplicate:
                owner_of.setdefault(call, source)
            if uuid and not r.duplicate:
                by_uuid[uuid] = (source, i)
    outcome, inherited_mass, heads, ratios = Counter(), 0.0, 0.0, []
    for source in loaded.files:
        live_calls = walk.calls(source.live, loaded.usages)
        if not live_calls:
            continue
        kind, _ = trigger(source)
        if kind in ("subagent", "session start"):
            continue
        head = ctx(live_calls[0])
        parent_call = None
        for r in source.records:
            if r.data.get("type") == "fork-context-ref":
                found = by_uuid.get(r.data.get("parentLastUuid"))
                if found:
                    owner, i = found
                    ids = [message_id(x.data) for x in owner.records[:i + 1] if message_id(x.data)]
                    parent_call = ids[-1] if ids else None
                break
            if r.duplicate and message_id(r.data):
                parent_call = message_id(r.data)
            if not r.duplicate and r.data.get("type") == "assistant":
                break
        owner = owner_of.get(parent_call) if parent_call else None
        if owner is None:
            outcome["parent call not found"] += 1
            continue
        parent_ctx = usage.usage_context(usage.max_merge_usage(loaded.usages[parent_call]))
        booked = occupancy_through(owner, loaded.usages, parent_call)
        ff = usage.max_merge_usage(loaded.usages[parent_call])["output_tokens"]
        rest = head - parent_ctx - ff
        outcome["parent booked == parent occupancy" if booked == parent_ctx else "parent booked differs"] += 1
        outcome["head - parent occupancy - feed-forward >= 0" if rest >= 0 else "head - parent occupancy - feed-forward < 0"] += 1
        ratios.append(head / parent_ctx if parent_ctx else 0.0)
        inherited_mass += min(parent_ctx, head)
        heads += head
    rec = query.reconcile(facts)
    return [
        "inheriting windows: %s" % tally(outcome),
        "their window_head %s; inherited from the parent %s (%s of those heads)"
        % (fmt(heads), fmt(inherited_mass), pct(inherited_mass, heads)),
        "head / parent occupancy: min %.4f, max %.4f" % (min(ratios or [0]), max(ratios or [0])),
        "context total counted per window %s; unique (inherited counted once) %s; inherited %s of total"
        % (fmt(rec.final_occupancy), fmt(rec.final_occupancy - inherited_mass),
           pct(inherited_mass, rec.final_occupancy)),
    ]


# 5. head content

def head_content(loaded: Corpus) -> List[str]:
    fresh = Counter()
    by_shape: Dict[str, set] = {}
    chars = Counter()
    for source in loaded.files:
        calls = walk.calls(source.live, loaded.usages)
        if not calls or trigger(source)[0] not in ("subagent", "session start"):
            continue
        first = calls[0]
        before = source.live[:first.first]
        shape = next((r.data for r in before if r.data.get("type") == "api-request-shape"), None)
        request = next((r.data for r in before if r.data.get("type") == "api-request"), None)
        fresh["fresh windows"] += 1
        fresh["shape record before the first call"] += shape is not None
        read = first.usage.get("cache_read_input_tokens") or 0
        fresh["first call reads cache"] += read > 0
        if shape:
            body = shape.get("shape") or {}
            chars["system"] += sum(len(str(b.get("text", ""))) for b in body.get("system", []))
            chars["tools"] += sum(len(json.dumps(t)) for t in body.get("tools", []))
        chars["head tokens"] += ctx(first)
        key = (request or shape or {}).get("shapeHash")
        if key and read:
            by_shape.setdefault(key, set()).add(read)
    groups = list(by_shape.values())
    return [
        "fresh windows (session start + subagent): %s" % tally(fresh),
        "chars in shape records (system, tools) vs head tokens: %s" % tally(chars),
        "shapeHash groups with a warm first call: %s; with one cache_read value: %s; with >1: %s"
        % (fmt(len(groups)), fmt(sum(len(g) == 1 for g in groups)), fmt(sum(len(g) > 1 for g in groups))),
    ]
