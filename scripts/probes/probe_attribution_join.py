#!/usr/bin/env python3
"""Phase 0 probe: does the RAW transcript corpus support attribution joins?

v1's data model cannot attribute spend because (a) a generation's locator is a
single index with no end/constituents, and (b) its tool_result facts carry no
tool_use_id. This probe measures, over every *.jsonl under
``Path.home()/".claude"/"projects"``, whether the raw data loses that or v1 does:

1. tool_result linkage — fraction of tool_result content blocks carrying a
   tool_use_id, and fraction of those resolvable to a tool_use block seen
   earlier in the same file.
2. Generation shape — for records sharing one message.id, fraction forming a
   contiguous run of record indices (can a [start,end) span locate a
   generation?). Measured over all parsed records, and again over
   assistant-record indices only.
3. Interval contributors — between consecutive usage-carrying assistant calls
   (adjacent records sharing a message.id collapse into one call), the
   distribution of non-assistant records in between.
4. Identifiability — fraction of those contributors with a uuid, a known type,
   and (for tool_result carriers) every tool_use_id resolvable.
5. Identity traps (owner-flagged) — files whose records' embedded sessionId
   differs from the filename stem, uuids duplicated within a file, and uuids
   appearing in more than one file (resumed-session replay).

Prints aggregate numbers only: no session ids, no paths, no transcript text.
Stdlib only. Blank/unparseable lines are skipped but counted; record indices
are positions in the parsed-record sequence, physical line numbers are kept
alongside but never printed.
"""
import json
import sys
from collections import Counter
from pathlib import Path

KNOWN_TYPES = {"user", "assistant", "system", "summary", "attachment", "mode",
               "file-history-snapshot", "last-prompt", "ai-title",
               "queue-operation", "fork-context-ref", "permission-mode"}
USAGE_FIELDS = ("input_tokens", "output_tokens",
                "cache_read_input_tokens", "cache_creation_input_tokens")


def content_blocks(rec):
    msg = rec.get("message")
    if not isinstance(msg, dict):
        return []
    c = msg.get("content")
    return [b for b in c if isinstance(b, dict)] if isinstance(c, list) else []


def has_usage(rec):
    msg = rec.get("message")
    if not isinstance(msg, dict):
        return False
    u = msg.get("usage")
    return isinstance(u, dict) and any(int(u.get(k, 0) or 0) for k in USAGE_FIELDS)


def classify_contributor(rec, blocks):
    t = rec.get("type")
    if t == "user":
        kinds = {b.get("type") for b in blocks}
        if "tool_result" in kinds:
            return "tool_result_user"
        return "user_text"
    if t == "assistant":
        return "assistant_no_usage"
    if t in KNOWN_TYPES:
        return "meta:" + str(t)
    return "unknown_type"


def main():
    root = Path.home() / ".claude" / "projects"
    files = sorted(root.rglob("*.jsonl"))
    n_records = blank = bad = 0

    tr_total = tr_with_id = tr_id_resolved = 0
    mid_total = mid_multi = mid_contig_all = mid_contig_asst = mid_multi_contig_all = 0
    intervals = 0
    contrib_hist = Counter()          # non-assistant contributors per interval
    contrib_kinds = Counter()
    ident_total = ident_ok = 0
    ident_fail = Counter()
    files_multi_agent = files_with_calls = 0
    calls_total = 0
    exactly_one_identifiable = 0      # intervals: 1 non-asst contributor, identifiable
    files_sid_mismatch = files_with_sid = 0
    dup_uuid_in_file = uuid_total = 0
    uuid_first_file = {}              # uuid -> first file index seen
    uuid_multi_file = set()           # uuids seen in >1 file

    for file_idx, path in enumerate(files):
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        recs = []                     # (physical_line_no, rec)
        for lineno, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                blank += 1
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            if not isinstance(rec, dict):
                bad += 1
                continue
            recs.append((lineno, rec))
        n_records += len(recs)

        seen_tool_use = set()         # tool_use ids seen so far, in record order
        mid_pos_all = {}              # message.id -> [record index over all recs]
        mid_pos_asst = {}             # message.id -> [index over assistant recs]
        asst_i = 0
        agent_ids = set()
        # measurement 1 + collect positions
        for i, (_ln, rec) in enumerate(recs):
            t = rec.get("type")
            blocks = content_blocks(rec)
            if t == "assistant":
                agent_ids.add(rec.get("agentId"))
                mid = rec.get("message", {}).get("id")
                if mid is not None:
                    mid_pos_all.setdefault(mid, []).append(i)
                    mid_pos_asst.setdefault(mid, []).append(asst_i)
                asst_i += 1
            for b in blocks:
                bt = b.get("type")
                if bt == "tool_result":
                    tr_total += 1
                    tid = b.get("tool_use_id")
                    if tid:
                        tr_with_id += 1
                        if tid in seen_tool_use:
                            tr_id_resolved += 1
                elif bt == "tool_use" and b.get("id"):
                    seen_tool_use.add(b["id"])
        if len(agent_ids) > 1:
            files_multi_agent += 1

        # measurement 5: identity traps
        sids = {r.get("sessionId") for _ln, r in recs} - {None}
        if sids:
            files_with_sid += 1
            if path.stem not in sids:
                files_sid_mismatch += 1
        file_uuids = [r["uuid"] for _ln, r in recs if r.get("uuid")]
        uuid_total += len(file_uuids)
        uniq = set(file_uuids)
        dup_uuid_in_file += len(file_uuids) - len(uniq)
        for u in uniq:
            prev = uuid_first_file.setdefault(u, file_idx)
            if prev != file_idx:
                uuid_multi_file.add(u)

        # measurement 2
        for mid, pos in mid_pos_all.items():
            mid_total += 1
            contig_all = pos[-1] - pos[0] + 1 == len(pos)
            pa = mid_pos_asst[mid]
            if contig_all:
                mid_contig_all += 1
            if pa[-1] - pa[0] + 1 == len(pa):
                mid_contig_asst += 1
            if len(pos) > 1:
                mid_multi += 1
                if contig_all:
                    mid_multi_contig_all += 1

        # measurements 3 + 4: calls = maximal runs of usage-bearing assistant
        # records sharing one message.id (non-usage records of the same id in
        # between do not break the run).
        call_spans = []               # (start_idx, end_idx_exclusive)
        cur_mid, cur_start, cur_end = None, None, None
        for i, (_ln, rec) in enumerate(recs):
            if rec.get("type") == "assistant" and has_usage(rec):
                mid = rec.get("message", {}).get("id")
                if mid is not None and mid == cur_mid:
                    cur_end = i + 1
                    continue
                if cur_mid is not None:
                    call_spans.append((cur_start, cur_end))
                cur_mid, cur_start, cur_end = mid, i, i + 1
        if cur_mid is not None:
            call_spans.append((cur_start, cur_end))
        calls_total += len(call_spans)
        if call_spans:
            files_with_calls += 1
        seen_tool_use2 = set()
        for i, (_ln, rec) in enumerate(recs):
            for b in content_blocks(rec):
                if b.get("type") == "tool_use" and b.get("id"):
                    seen_tool_use2.add((i, b["id"]))
        tu_by_id = {}
        for i, tid in sorted(seen_tool_use2):
            tu_by_id.setdefault(tid, i)
        for (s1, e1), (s2, _e2) in zip(call_spans, call_spans[1:]):
            intervals += 1
            between = [(i, recs[i][1]) for i in range(e1, s2)]
            non_asst = []
            for i, rec in between:
                blocks = content_blocks(rec)
                kind = classify_contributor(rec, blocks)
                contrib_kinds[kind] += 1
                if kind == "assistant_no_usage":
                    continue
                non_asst.append((i, rec, blocks, kind))
            contrib_hist[min(len(non_asst), 5)] += 1
            interval_all_ok = len(non_asst) == 1
            for i, rec, blocks, kind in non_asst:
                ident_total += 1
                ok = True
                if not rec.get("uuid"):
                    ident_fail["no_uuid"] += 1
                    ok = False
                if rec.get("type") not in KNOWN_TYPES:
                    ident_fail["unknown_type"] += 1
                    ok = False
                if kind == "tool_result_user":
                    tids = [b.get("tool_use_id") for b in blocks
                            if b.get("type") == "tool_result"]
                    if not all(t and t in tu_by_id and tu_by_id[t] < i
                               for t in tids):
                        ident_fail["tool_use_id_unresolvable"] += 1
                        ok = False
                if ok:
                    ident_ok += 1
                else:
                    interval_all_ok = False
            if len(non_asst) == 1 and interval_all_ok:
                exactly_one_identifiable += 1

    def pct(a, b):
        return f"{a}/{b} = {100.0 * a / b:.2f}%" if b else f"{a}/0 = n/a"

    print(f"corpus: {len(files)} files, {n_records} parsed records, "
          f"{blank} blank lines skipped, {bad} unparseable lines skipped")
    print(f"files with >1 distinct agentId on assistant records: "
          f"{pct(files_multi_agent, len(files))}")
    print("\n[1] tool_result linkage (population: all tool_result blocks)")
    print(f"  carry tool_use_id: {pct(tr_with_id, tr_total)}")
    print(f"  id matches an earlier tool_use in same file: "
          f"{pct(tr_id_resolved, tr_with_id)}")
    print("\n[2] generation shape (population: message.ids on assistant records)")
    print(f"  contiguous over ALL parsed records: {pct(mid_contig_all, mid_total)}")
    print(f"  contiguous over assistant records only: "
          f"{pct(mid_contig_asst, mid_total)}")
    print(f"  multi-record ids: {pct(mid_multi, mid_total)}; of those, "
          f"contiguous over all records: {pct(mid_multi_contig_all, mid_multi)}")
    print(f"\n[3] intervals between consecutive usage-calls "
          f"(population: {intervals} intervals from {calls_total} calls "
          f"in {files_with_calls} files with >=1 call)")
    for k in sorted(contrib_hist):
        label = f"{k}" if k < 5 else "5+"
        print(f"  {label} non-assistant contributors: "
              f"{pct(contrib_hist[k], intervals)}")
    print("  contributor kinds (population: all between-records incl. "
          "usage-less assistant):")
    for kind, n in contrib_kinds.most_common():
        print(f"    {kind}: {n}")
    print("\n[4] identifiability (population: non-assistant contributor "
          "records in [3])")
    print(f"  identifiable (uuid + known type + resolvable tool_use_ids): "
          f"{pct(ident_ok, ident_total)}")
    for reason, n in ident_fail.most_common():
        print(f"  fail[{reason}]: {n}")
    print(f"  intervals with exactly one, identifiable contributor: "
          f"{pct(exactly_one_identifiable, intervals)}")
    print("\n[5] identity traps")
    print(f"  files whose embedded sessionId set excludes the filename stem: "
          f"{pct(files_sid_mismatch, files_with_sid)} "
          f"(population: files with any sessionId)")
    print(f"  duplicate uuid occurrences within a file: "
          f"{pct(dup_uuid_in_file, uuid_total)} "
          f"(population: uuid-bearing records)")
    print(f"  uuids appearing in >1 file: "
          f"{pct(len(uuid_multi_file), len(uuid_first_file))} "
          f"(population: distinct uuids corpus-wide)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
