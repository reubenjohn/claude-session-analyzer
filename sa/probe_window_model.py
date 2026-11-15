"""The window-model probe: can "window = one context window" (it starts at a
session start, a subagent, a fork or a compaction and fills until it ends
or compacts) replace R2 (a window is a file) without breaking accounting?
Measured with the parser (``corpus``, ``walk``, ``query``) and the UX
probe's segmenting (``probe_ux.segments``), never a copy. A measuring
module, not engine. ``python3 -m sa.probe_window_model`` stamps the minute on
its first line. Aggregate counts only: no transcript text, ids or paths.

Run ``WINDOW PROBE 2026-11-15T09:20Z`` (605 files, 591 windows-as-files):

- No window spans files: 0 files replay after a live record, 0 call-bearing
  files share a sessionId or agentId, 0 main files replay another (no
  /branch or bg copy here). 10 subagent files replay a prefix, each from
  ONE owner that calls again after the branch: 10 branches, 0 continuations.
- Cut at the 9 live markers: 596 windows, all telescope (sum context_delta
  == last occupancy); 0 increments in two windows; the split removes 5
  shrinks and adds 5 window_heads, nothing else; records, calls, spend
  identical. Reconciled keyed by FILE it fails: segments must be the key.
- 5 split files: the file peak is the pre-compaction segment's on 5 of 5.
- Key: 8 hex of sha1 over the window_head ``file:line``: 0 collisions.
- Compaction: 0 assistant records between a marker and the next call, 0
  compact querySources: 9 compactions unpriced.
- Forks: inherited = the parent call's occupancy, re-minted (message.id)
  in 10 of 10; 9 replay the parent prefix by uuid less 2 records, 1 holds
  it by reference only; 0 nested, 0 parents compacted first.
"""
import datetime
import hashlib
from collections import Counter
from typing import Dict, List, Optional, Tuple

from . import probe_compaction as probe_ux, query, schema, usage, walk
from .corpus import Corpus, SourceFile, default_root, load, message_id
from .probe_compaction import fmt, is_marker, tally


def idbearing(source: SourceFile):
    return [r for r in source.records if r.data.get("uuid") or message_id(r.data)]


def replay_shape(source: SourceFile) -> str:
    flags = [r.duplicate for r in idbearing(source)]
    if not any(flags):
        return "no replay"
    if all(flags):
        return "all replayed"
    return "replayed prefix" if not any(flags[flags.index(False):]) else "replay after live"


class Owners(object):
    """Where each live uuid and message.id sits: (file, record index)."""

    def __init__(self, loaded: Corpus):
        self.at: Dict[Tuple[str, str], Tuple[SourceFile, int]] = {}
        for source in loaded.files:
            for i, r in enumerate(source.records):
                if r.duplicate:
                    continue
                for key in (("u", r.data.get("uuid")), ("m", message_id(r.data))):
                    if key[1]:
                        self.at.setdefault(key, (source, i))

    def of(self, data: dict) -> Optional[Tuple[SourceFile, int]]:
        found = self.at.get(("u", data.get("uuid")))
        return found or self.at.get(("m", message_id(data)))


def branch(source: SourceFile, owners: Owners) -> Optional[Tuple[SourceFile, int]]:
    """The parent record a window branched from: the ``fork-context-ref``'s
    ``parentLastUuid``, else the last replayed id-bearing record."""
    last = None
    for r in source.records:
        if r.data.get("type") == "fork-context-ref":
            return owners.at.get(("u", r.data.get("parentLastUuid")))
        if r.duplicate and (r.data.get("uuid") or message_id(r.data)):
            last = owners.of(r.data)
        elif not r.duplicate and r.data.get("type") == "assistant":
            break
    return last


def parent_call(owner: SourceFile, index: int, loaded: Corpus) -> Optional[walk.Call]:
    """The parent's last call whose first constituent is at or before ``index``."""
    found = [c for c in walk.calls(owner.live, loaded.usages)
             if owner.records.index(c.record) <= index]
    return found[-1] if found else None


# 1. files vs windows

def files_vs_windows(loaded: Corpus, owners: Owners) -> List[str]:
    shapes, owner_count, outcome = Counter(), Counter(), Counter()
    sessions, agents = Counter(), Counter()
    sid_per_file, entry = Counter(), Counter()
    for source in loaded.files:
        has_call = bool(walk.calls(source.live, loaded.usages))
        main = not probe_ux.is_subagent(source)
        shapes["%s %s%s" % (replay_shape(source), "main" if main else "subagent",
                            "" if has_call else " (no call)")] += 1
        sids = {r.data.get("sessionId") for r in source.live if r.data.get("sessionId")}
        sid_per_file[len(sids)] += 1
        if has_call and main:
            entry[str(walk.first_value(source.live, "entrypoint"))] += 1
        if has_call:
            for s in sids:
                sessions[s] += main
            for a in {r.data.get("agentId") for r in source.live if r.data.get("agentId")}:
                agents[a] += 1
        dups = [r for r in source.records if r.duplicate]
        if not dups:
            continue
        owner_count["%d owner file(s)" % len({owners.of(r.data)[0].name for r in dups if owners.of(r.data)})] += 1
        found = branch(source, owners)
        if found is None:
            outcome["branch record not found"] += 1
            continue
        owner, i = found
        later = [c for c in walk.calls(owner.live, loaded.usages) if owner.records.index(c.record) > i]
        outcome["owner calls after the branch (branch)" if later
                else "owner ends at the branch (continuation: window spans files)"] += 1
    return [
        "files by replay shape: %s" % tally(shapes),
        "live sessionIds per file: %s" % tally(Counter({"%d" % k: v for k, v in sid_per_file.items()})),
        "call-bearing main files sharing a sessionId: %s; call-bearing files sharing an agentId: %s"
        % (fmt(sum(n > 1 for n in sessions.values())), fmt(sum(n > 1 for n in agents.values()))),
        "call-bearing main files by entrypoint: %s" % tally(entry),
        "replaying files by owners of their replayed records: %s" % tally(owner_count),
        "replaying files by what the owner does next: %s" % tally(outcome),
    ]


# 2. accounting under the split

def window_of(f: schema.Fact) -> str:
    return f.locator.file  # probe_ux.segments names each segment ``file#k``


def base(name: str) -> str:
    return name.rsplit("#", 1)[0]


def key_of(f: schema.Fact) -> Tuple:
    loc = f.locator
    return (base(loc.file), loc.line, loc.uuid, f.dims.get(schema.CAUSE_DIM), f.metrics.get(schema.CONTEXT_DELTA))


def per_window(facts: List[schema.Fact]) -> Tuple[Counter, Dict[str, int], Dict[str, int]]:
    booked, last, peak, heads = Counter(), {}, {}, Counter()
    for f in facts:
        w = window_of(f)
        if f.kind == schema.CALL:
            occ = f.metrics[schema.CONTEXT_TOKENS]
            last[w] = occ
            peak[w] = max(peak.get(w, 0), occ)
        else:
            booked[w] += f.metrics[schema.CONTEXT_DELTA]
            heads[w] += f.dims[schema.CAUSE_DIM] == schema.STARTING_CONTEXT
    fails = Counter(booked[w] == last[w] for w in last)
    return Counter({"telescopes": fails[True], "fails": fails[False],
                    "one window_head": sum(heads[w] == 1 for w in last)}), peak, last


def window_key(f: schema.Fact) -> str:
    """The proposed ``window`` value: the window_head locator, hashed."""
    text = "%s:%d" % (f.locator.file, f.locator.line)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def split(loaded: Corpus, facts: List[schema.Fact]) -> List[str]:
    cut = [seg for source in loaded.files for seg in probe_ux.segments(source)]
    seg_facts = [f for seg in cut for f in walk.walk(seg, loaded.usages)]
    tele_files, peak_files, _ = per_window(facts)
    tele_segs, peak_segs, _ = per_window(seg_facts)
    rec = query.reconcile(seg_facts)
    merged = query.reconcile([f._replace(locator=f.locator._replace(file=base(f.locator.file)))
                              for f in seg_facts])
    incs = [f for f in facts if f.kind == schema.INCREMENT]
    seg_incs = [f for f in seg_facts if f.kind == schema.INCREMENT]
    homes: Dict[Tuple, set] = {}
    for f in seg_incs:
        homes.setdefault(key_of(f)[:3], set()).add(window_of(f))
    removed = Counter(map(key_of, incs)) - Counter(map(key_of, seg_incs))
    added = Counter(map(key_of, seg_incs)) - Counter(map(key_of, incs))
    calls_same = (Counter((key_of(f), f.metrics[schema.SPEND]) for f in facts if f.kind == schema.CALL)
                  == Counter((key_of(f), f.metrics[schema.SPEND]) for f in seg_facts if f.kind == schema.CALL))
    live_same = sum(len(s.live) for s in loaded.files) == sum(len(s.live) for s in cut)
    split_files = {base(w) for w in peak_segs if w.endswith("#1")}
    peak_where, peak_max = Counter(), 0
    for name in split_files:
        segs = sorted((w for w in peak_segs if base(w) == name), key=lambda w: int(w.rsplit("#", 1)[1]))
        top = max(segs, key=lambda w: peak_segs[w])
        peak_where["pre-compaction" if top == segs[0] else "later segment"] += 1
        peak_max += peak_files[name] == peak_segs[top]
    heads = [f for f in seg_facts if f.dims.get(schema.CAUSE_DIM) == schema.STARTING_CONTEXT]
    keys = Counter(window_key(f) for f in heads)
    spend = (query.total(facts, schema.SPEND), query.total(seg_facts, schema.SPEND))
    return [
        "(i) per window as files: %s; split: %s; reconcile keyed by segment holds %s, keyed by file holds %s"
        % (tally(tele_files), tally(tele_segs), rec.holds, merged.holds),
        "(ii) increment locators in more than one window: %s; removed by the split: %s; added: %s"
        % (fmt(sum(len(v) > 1 for v in homes.values())),
           tally(Counter(k[3] for k in removed.elements())), tally(Counter(k[3] for k in added.elements()))),
        "(iii) live records identical %s; call facts (locator, spend) identical %s; duplicates marked %s"
        % (live_same, calls_same, fmt(loaded.duplicate_records)),
        "(iv) before: " + probe_ux.rates(query.reconcile(facts)),
        "(iv) after: " + probe_ux.rates(rec),
        "(v) split files %s; their peak segment: %s; file peak == max segment peak on %s"
        % (fmt(len(split_files)), tally(peak_where), fmt(peak_max)),
        "(vi) windows: as files %s, split %s" % (fmt(len(peak_files)), fmt(len(peak_segs))),
        "(vii) window keys (8 hex of sha1 over the head locator file:line): %s heads, %s distinct, %s collisions"
        % (fmt(len(heads)), fmt(len(keys)), fmt(sum(n - 1 for n in keys.values()))),
        "(viii) spend total identical before/after: %s" % (spend[0] == spend[1]),
    ]


# 2 (viii). the summarising call

def unpriced(loaded: Corpus) -> List[str]:
    markers = between = 0
    for source in loaded.files:
        live = source.live
        calls = walk.calls(live, loaded.usages)
        for m in (i for i, r in enumerate(live) if is_marker(r.data)):
            markers += 1
            nxt = [c.first for c in calls if c.first > m]
            span = live[m + 1:nxt[0]] if nxt else live[m + 1:]
            between += sum(r.data.get("type") == "assistant" for r in span)
    sources = Counter("compact" if "compact" in str(r.data.get("querySource")) else "other"
                      for s in loaded.files for r in s.records if r.data.get("type") == "api-request")
    return ["(viii) live compactions %s; assistant records after a marker before the next call %s; "
            "api-request querySource: %s" % (fmt(markers), fmt(between), tally(sources))]


# 2 (ix). forks

def forks(loaded: Corpus, owners: Owners) -> List[str]:
    out, ratio = Counter(), []
    place, missing = Counter(), Counter()
    inheriting = set()
    rows = []
    for source in loaded.files:
        calls = walk.calls(source.live, loaded.usages)
        if not calls:
            continue
        found = branch(source, owners)
        if found is None:
            continue
        inheriting.add(source.name)
        rows.append((source, calls, found))
    for source, calls, (owner, i) in rows:
        out["nested (parent itself inherits)"] += owner.name in inheriting
        out["parent compacted before the branch"] += any(is_marker(r.data) for r in owner.records[:i + 1]
                                                         if not r.duplicate)
        call = parent_call(owner, i, loaded)
        if call is None:
            out["parent call not found"] += 1
            continue
        inherited = usage.usage_context(call.usage)
        head = usage.usage_context(calls[0].usage)
        out["head >= parent occupancy"] += head >= inherited
        ratio.append(head / inherited if inherited else 0.0)
        mine = {r.data.get("uuid") for r in source.records if r.data.get("uuid")}
        for r in source.records:
            if not r.duplicate:
                continue
            at = owners.at.get(("u", r.data.get("uuid")))
            place[("by uuid, at or before the branch" if at[1] <= i else "by uuid, past the branch")
                  if at else "by message.id only (re-mint)"] += 1
        prefix = [r for r in owner.records[:i + 1] if r.data.get("uuid") and not r.duplicate]
        gap = sum(r.data.get("uuid") not in mine for r in prefix)
        missing["all (by reference)" if gap == len(prefix) else "%d not replayed" % gap] += 1
        ref = next((r.data for r in source.records if r.data.get("type") == "fork-context-ref"), None)
        if ref is not None:
            out["fork-context-ref contextLength == parent call occupancy"] += ref.get("contextLength") == inherited
    return ["(ix) inheriting windows %s: %s" % (fmt(len(rows)), tally(out)),
            "(ix) their replayed records: %s" % tally(place),
            "(ix) parent prefix (live uuid records through the branch), per fork: %s" % tally(missing),
            "(ix) head / parent occupancy: min %.4f, max %.4f" % (min(ratio or [0]), max(ratio or [0]))]


def report(loaded: Corpus) -> List[str]:
    facts = walk.forest(loaded)
    owners = Owners(loaded)
    sections = [("1 files", files_vs_windows(loaded, owners)), ("2 split", split(loaded, facts)),
                ("2 spend", unpriced(loaded)), ("2 forks", forks(loaded, owners))]
    return ["[%s] %s" % (name, line) for name, lines in sections for line in lines]


if __name__ == "__main__":
    loaded = load(default_root())
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    print("WINDOW PROBE %s: %s files" % (now, fmt(len(loaded.files))))
    print("\n".join(report(loaded)))
