"""The UX-pass probe, records half (``references/UX_FEEDBACK.md`` track B):
what the records say about compaction, and the reconciliation with each
window cut at its markers (``segmented``), measured with the parser itself
(``corpus``, ``walk``), never a copy of it. Also the helpers both probe
modules share. Run both with ``python3 -m sa.probe_ux``. Aggregate counts
only: no transcript text, no ids, no paths.
"""
import datetime
from collections import Counter
from typing import List, Optional, Tuple

from . import query, schema, usage, walk
from .corpus import COMPACT, Corpus, SourceFile, is_marker  # noqa: F401 (re-exported)

HOUR = 3600.0


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
    growth = rec.final_occupancy - rec.by_cause[schema.STARTING_CONTEXT]
    return ("%s windows, %s calls, %s intervals; context total %s; growth %s; window_head %s (%s); "
            "exact %s (%s), ambiguous %s (%s), shrink %s (%s, %s tokens); holds %s"
            % (fmt(rec.windows), fmt(rec.calls), fmt(rec.intervals), fmt(rec.final_occupancy), fmt(growth),
               fmt(rec.by_cause[schema.STARTING_CONTEXT]), pct(rec.by_cause[schema.STARTING_CONTEXT], rec.final_occupancy),
               fmt(rec.exact), pct(rec.exact, rec.intervals), fmt(rec.ambiguous),
               pct(rec.ambiguous, rec.intervals), fmt(rec.shrink), pct(rec.shrink, rec.intervals),
               fmt(rec.by_cause[schema.SHRINK]), rec.holds))


def segmented(loaded: Corpus, facts: List[schema.Fact]) -> List[str]:
    cut = [seg for source in loaded.files for seg in segments(source)]
    seg_facts = [f for seg in cut for f in walk.walk(seg, loaded.usages)]
    return ["as files: " + rates(query.reconcile(facts)),
            "cut at markers: " + rates(query.reconcile(seg_facts))]
