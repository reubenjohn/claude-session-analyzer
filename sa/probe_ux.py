"""The UX-pass probe (``references/UX_FEEDBACK.md`` track B): what the
records say about compaction, window starts, fork prefixes and the content
of a window's head, measured with the parser itself (``corpus``, ``walk``),
never a copy of it. A measuring module, not engine: nothing here changes a
fact the CLI books. ``python3 -m sa.probe_ux`` runs it over the live corpus
under ``~/.claude/projects`` and stamps the minute on the first line, so
``references/PROPOSAL_UX_MODEL.md`` can cite it by date. Aggregate counts
only: no transcript text, no ids, no paths.

One section per question of the proposal: ``compaction``, ``segmented``
(the reconciliation with each window cut at its markers), ``triggers``,
``inherited`` (fork prefixes against their parent) and ``head_content``.
"""
import datetime
import json
from collections import Counter
from typing import Dict, List, Optional, Tuple

from . import query, schema, usage, walk
from .corpus import Corpus, SourceFile, default_root, load, message_id

COMPACT = "compact_boundary"
HOUR = 3600.0


def is_marker(data: dict) -> bool:
    return data.get("type") == "system" and data.get("subtype") == COMPACT


def is_subagent(source: SourceFile) -> bool:
    return "/subagents/" in source.name


def ctx(call: walk.Call) -> int:
    return usage.usage_context(call.usage)


def stamp(data: dict) -> Optional[float]:
    text = data.get("timestamp")
    if not text:
        return None
    return datetime.datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


def fmt(value) -> str:
    return format(int(round(value)), ",d") if isinstance(value, (int, float)) else str(value)


def pct(part: float, whole: float) -> str:
    return "%.2f%%" % (100.0 * part / whole) if whole else "n/a"


def tally(counter: Counter) -> str:
    return ", ".join("%s %s" % (k, fmt(v)) for k, v in counter.most_common()) or "none"


def bucket(n: float) -> str:
    for edge, label in ((1000, "<1k"), (10000, "1k-10k"), (100000, "10k-100k")):
        if n < edge:
            return label
    return ">=100k"


# 1. compaction

def neighbours(calls: List[walk.Call], index: int) -> Tuple[Optional[int], Optional[int]]:
    """Positions in ``calls`` of the last call before live index ``index`` and the first after."""
    before = [k for k, c in enumerate(calls) if c.first < index]
    after = [k for k, c in enumerate(calls) if c.first > index]
    return (before[-1] if before else None), (after[0] if after else None)


def compaction(loaded: Corpus) -> List[str]:
    every = live_markers = 0
    windows = Counter()
    drop, pre_match, post_match, after = Counter(), Counter(), Counter(), Counter()
    unmarked_sizes, unmarked_before, unmarked_model = Counter(), Counter(), Counter()
    marked_shrinks = all_shrinks = 0
    for source in loaded.files:
        every += sum(is_marker(r.data) for r in source.records)
        live = source.live
        marks = [i for i, r in enumerate(live) if is_marker(r.data)]
        live_markers += len(marks)
        if marks:
            windows["subagent" if is_subagent(source) else "main"] += 1
        calls = walk.calls(live, loaded.usages)
        for m in marks:
            meta = live[m].data.get("compactMetadata") or {}
            prev, nxt = neighbours(calls, m)
            if prev is None or nxt is None:
                drop["no call before" if prev is None else "no call after (window ends)"] += 1
                after["isCompactSummary user record, window ends"] += any(
                    r.data.get("isCompactSummary") for r in live[m + 1:])
                continue
            p, n = ctx(calls[prev]), ctx(calls[nxt])
            later = [k for k in range(nxt, len(calls)) if ctx(calls[k]) < p]
            drop["at the next call" if n < p else "at a later call" if later else "never"] += 1
            pre = meta.get("preTokens")
            pre_match["equal" if pre == p else "within 1%" if pre and abs(pre - p) <= 0.01 * p
                      else "differs"] += 1
            post = meta.get("postTokens")
            post_match["next call - postTokens " + bucket(n - post) if post is not None
                       else "no postTokens"] += 1
            span = live[m + 1:calls[nxt].first]
            after["isCompactSummary user record"] += any(r.data.get("isCompactSummary") for r in span)
            after["assistant record between marker and next call"] += any(
                r.data.get("type") == "assistant" for r in span)
        for k in range(1, len(calls)):
            if ctx(calls[k]) >= ctx(calls[k - 1]):
                continue
            all_shrinks += 1
            lo, hi = calls[k - 1].first, calls[k].first
            if any(is_marker(r.data) for r in live[lo + 1:hi]):
                marked_shrinks += 1
                continue
            size = ctx(calls[k - 1]) - ctx(calls[k])
            unmarked_sizes[bucket(size)] += 1
            users = [r for r in live[lo + 1:hi] if r.data.get("type") == "user"]
            unmarked_before["user text" if any(not r.data.get("isMeta") for r in users)
                            else "no user text"] += 1
            models = {(calls[j].record.data.get("message") or {}).get("model") for j in (k - 1, k)}
            unmarked_model["model changes" if len(models) > 1 else "same model"] += 1
    sources = Counter("compact-sourced" if "compact" in str(r.data.get("querySource")) else "other"
                      for source in loaded.files for r in source.records
                      if r.data.get("type") == "api-request")
    return [
        "compact_boundary markers: %s in all records, %s live (owned), %s in replayed copies"
        % (fmt(every), fmt(live_markers), fmt(every - live_markers)),
        "windows holding a live marker: %s" % tally(windows),
        "occupancy drop after a live marker: %s" % tally(drop),
        "marker preTokens vs the previous call's occupancy: %s" % tally(pre_match),
        "marker postTokens vs the next call's occupancy: %s" % tally(post_match),
        "between marker and next call: %s" % tally(after),
        "api-request records by querySource: %s (the summarizing call)" % tally(sources),
        "shrink intervals: %s, %s with a marker between the calls, %s without"
        % (fmt(all_shrinks), fmt(marked_shrinks), fmt(all_shrinks - marked_shrinks)),
        "unmarked shrink sizes: %s" % tally(unmarked_sizes),
        "unmarked shrinks by model: %s" % tally(unmarked_model),
        "unmarked shrinks, what lies between the calls: %s" % tally(unmarked_before),
    ]


# 2. segmentation

def segments(source: SourceFile) -> List[SourceFile]:
    """The window cut at each live marker: one SourceFile per segment, the
    records outside it marked duplicate so that ``walk`` mints nothing from
    them while its tool_use join still spans the whole file."""
    marks = [i for i, r in enumerate(source.records) if is_marker(r.data) and not r.duplicate]
    if not marks:
        return [source]
    cuts = [0] + marks + [len(source.records)]
    out = []
    for k in range(len(cuts) - 1):
        lo, hi = cuts[k], cuts[k + 1]
        records = [r if lo <= i < hi else r._replace(duplicate=True)
                   for i, r in enumerate(source.records)]
        out.append(source._replace(name="%s#%d" % (source.name, k), records=records))
    return out


def rates(rec: query.Reconciliation) -> str:
    growth = rec.final_occupancy - rec.by_cause[schema.WINDOW_HEAD]
    return ("%s windows, %s calls, %s intervals; context total %s; growth %s; window_head %s (%s); "
            "exact %s (%s), ambiguous %s (%s), shrink %s (%s, %s tokens); holds %s"
            % (fmt(rec.windows), fmt(rec.calls), fmt(rec.intervals), fmt(rec.final_occupancy), fmt(growth),
               fmt(rec.by_cause[schema.WINDOW_HEAD]), pct(rec.by_cause[schema.WINDOW_HEAD], rec.final_occupancy),
               fmt(rec.exact), pct(rec.exact, rec.intervals), fmt(rec.ambiguous),
               pct(rec.ambiguous, rec.intervals), fmt(rec.shrink), pct(rec.shrink, rec.intervals),
               fmt(rec.by_cause[schema.SHRINK]), rec.holds))


def segmented(loaded: Corpus, facts: List[schema.Fact]) -> List[str]:
    cut = [seg for source in loaded.files for seg in segments(source)]
    seg_facts = [f for seg in cut for f in walk.walk(seg, loaded.usages)]
    return ["as files: " + rates(query.reconcile(facts)),
            "cut at markers: " + rates(query.reconcile(seg_facts))]


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


def report(loaded: Corpus) -> List[str]:
    facts = walk.forest(loaded)
    sections = [("1 compaction", compaction(loaded)), ("2 segmented", segmented(loaded, facts)),
                ("3 triggers", triggers(loaded)), ("4 inherited", inherited(loaded, facts)),
                ("5 head content", head_content(loaded))]
    return ["[%s] %s" % (name, line) for name, lines in sections for line in lines]


if __name__ == "__main__":
    loaded = load(default_root())
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    print("UX PROBE %s: %s files" % (now, fmt(len(loaded.files))))
    print("\n".join(report(loaded)))
