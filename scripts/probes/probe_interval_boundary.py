#!/usr/bin/env python3
"""Phase 0b probe: does the strictly-between interval boundary hold up?

All three design briefs named the interval boundary as their weakest point.
This probe settles it in code over every ``*.jsonl`` under the corpus root
(computed at runtime as ``Path.home()/".claude"/"projects"``).

Definitions (lane = file; positions are indices in the deduped record order):

- Records are parsed in order; within a file, duplicate top-level ``uuid``
  occurrences after the first are dropped. uuid-less records are kept.
- A **call** is the set of assistant records sharing one ``message.id`` over the
  file; merged usage is a field-wise max (``max_merge_usage``). Assistant
  records with no ``message.id`` are singleton calls. A call is usage-carrying
  iff any merged token field is nonzero. Calls are ordered by first constituent.
- **Interval N** (N>=1) is the records strictly between call N-1's LAST
  constituent and call N's FIRST constituent, over consecutive usage-carrying
  calls in file order.
- ``docc = usage_context(merged N) - usage_context(merged N-1)``,
  ``out_prev = merged N-1 output_tokens``, remainder ``R = docc - out_prev``.

Measures: (a) exact-attribution rate + disjoint failure reasons, (b) the
candidate-definition delta (all non-assistant vs uuid-bearing vs token-relevant),
(c) interleaved message.ids and the empty/overlapping boundaries around them --
scanned twice, with and without within-file uuid dedup, because dedup is a
suspect for the interleaving Phase 0 saw, (d) Design C's per-lane conservation
test, plus a counterfactual that drops the shrink-quarantined intervals so the
test has something it can actually fail on.

Aggregate counts only on stdout: no ids, paths, or transcript text. Stdlib only.
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from lib_usage import context_delta, max_merge_usage, usage_context  # noqa: E402

USAGE_FIELDS = ("input_tokens", "output_tokens",
                "cache_read_input_tokens", "cache_creation_input_tokens")
TOKEN_RELEVANT = ("tool_result", "user_text")


def _msg(rec):
    m = rec.get("message")
    return m if isinstance(m, dict) else {}


def _usage(rec):
    u = _msg(rec).get("usage")
    return u if isinstance(u, dict) else {}


def _nonzero(u):
    return any(int(u.get(k, 0) or 0) for k in USAGE_FIELDS)


def _blocks(rec):
    c = _msg(rec).get("content")
    return [b for b in c if isinstance(b, dict)] if isinstance(c, list) else []


def classify(rec):
    """Contributor kind of one boundary record."""
    t = rec.get("type")
    if t == "user":
        if any(b.get("type") == "tool_result" for b in _blocks(rec)):
            return "tool_result"
        return "user_text"
    if t == "assistant":
        return ("usage_carrying_assistant" if _nonzero(_usage(rec))
                else "usage_less_assistant")
    if rec.get("uuid"):
        return "other_identified"
    return "bookkeeping"


def magnitude(n):
    n = abs(n)
    if n == 0:
        return "0"
    d = len(str(n))
    return f"{10 ** (d - 1)}-{10 ** d - 1}"


def read_file(path, tally):
    """(raw records, uuid-deduped records) of one file, in order."""
    try:
        text = path.read_text(errors="replace")
    except OSError:
        tally["unreadable"] += 1
        return [], []
    raw, recs, seen = [], [], set()
    for line in text.splitlines():
        if not line.strip():
            tally["blank"] += 1
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            tally["bad"] += 1
            continue
        if not isinstance(rec, dict):
            tally["bad"] += 1
            continue
        tally["records"] += 1
        raw.append(rec)
        u = rec.get("uuid")
        if u:
            if u in seen:
                tally["dup_uuid"] += 1
                if rec.get("type") == "assistant":
                    tally["dup_uuid_assistant"] += 1
                continue
            seen.add(u)
        recs.append(rec)
    return raw, recs


def build_calls(recs):
    """Calls in first-constituent order; each is a dict of positions + usage."""
    groups, asst_pos, asst_seq = {}, {}, 0
    for i, rec in enumerate(recs):
        if rec.get("type") != "assistant":
            continue
        mid = _msg(rec).get("id")
        key = mid if mid is not None else ("_noid_", i)
        groups.setdefault(key, []).append(i)
        asst_pos.setdefault(key, []).append(asst_seq)
        asst_seq += 1
    calls = []
    for key, pos in groups.items():
        ap = asst_pos[key]
        merged = max_merge_usage([_usage(recs[i]) for i in pos])
        calls.append({
            "first": pos[0], "last": pos[-1], "merged": merged,
            "carrying": _nonzero(merged),
            "interleaved": ap[-1] - ap[0] + 1 != len(ap),
            "has_id": not isinstance(key, tuple),
        })
    calls.sort(key=lambda c: c["first"])
    return calls


def overlapping(ranges):
    """Indices of ranges (start, end) that intersect another range."""
    live = sorted((s, e, k) for k, (s, e) in enumerate(ranges) if s < e)
    hit = set()
    for a in range(len(live)):
        s_a, e_a, k_a = live[a]
        for b in range(a + 1, len(live)):
            s_b, _e_b, k_b = live[b]
            if s_b >= e_a:
                break
            hit.add(k_a)
            hit.add(k_b)
    return hit


def pathologies(recs, out):
    """Interleaving and boundary pathologies of one file, into Counter ``out``."""
    calls = build_calls(recs)
    out["calls"] += len(calls)
    out["interleaved_ids"] += sum(1 for c in calls if c["interleaved"])
    uc = [c for c in calls if c["carrying"]]
    ranges, flags = [], []
    for n in range(1, len(uc)):
        prev, cur = uc[n - 1], uc[n]
        start, end = prev["last"] + 1, cur["first"]
        il = prev["interleaved"] or cur["interleaved"]
        ranges.append((start, end))
        flags.append(il)
        out["intervals"] += 1
        out["adjacent"] += il
        if start >= end:
            out["zero_records"] += 1
            out["zero_records_il"] += il
        if prev["last"] >= cur["first"]:
            out["inverted"] += 1
            out["inverted_il"] += il
    for k in overlapping(ranges):
        out["overlap"] += 1
        out["overlap_il"] += flags[k]


def main():
    root = Path.home() / ".claude" / "projects"
    files = sorted(root.rglob("*.jsonl"))
    tally = Counter()
    dedup_path = Counter()     # (c) over uuid-deduped records
    raw_path = Counter()       # (c) over raw records, no dedup
    calls_total = calls_carrying = calls_noid = 0
    intervals = 0
    kinds = Counter()          # contributor kinds over all boundary records
    exact = 0
    disjoint = Counter()       # first-matching failure reason
    marginal = Counter()       # non-disjoint reason counts
    cand_all = cand_uuid = cand_tokrel = 0     # exactly-one under 3 definitions
    ex_n, ex_r = Counter(), Counter()   # exact intervals, split by attachments
    mass = Counter()           # global bucket totals
    lanes = lanes_hold = cf_hold = 0
    cf_err = Counter()
    cf_fail_quar = 0

    for path in files:
        raw, recs = read_file(path, tally)
        pathologies(recs, dedup_path)
        pathologies(raw, raw_path)
        calls = build_calls(recs)
        calls_total += len(calls)
        calls_noid += sum(1 for c in calls if not c["has_id"])
        uc = [c for c in calls if c["carrying"]]
        calls_carrying += len(uc)
        if not uc:
            continue
        lanes += 1

        rows = []
        for n in range(1, len(uc)):
            prev, cur = uc[n - 1], uc[n]
            start, end = prev["last"] + 1, cur["first"]
            intervals += 1
            between = recs[start:end] if start < end else []

            docc = context_delta(prev["merged"], cur["merged"])
            out_prev = int(prev["merged"].get("output_tokens", 0) or 0)
            rem = docc - out_prev
            ck = Counter(classify(r) for r in between)
            kinds.update(ck)
            n_all = sum(1 for r in between if r.get("type") != "assistant")
            n_uuid = sum(1 for r in between
                         if r.get("type") != "assistant" and r.get("uuid"))
            n_tok = sum(ck[k] for k in TOKEN_RELEVANT)
            cand_all += n_all == 1
            cand_uuid += n_uuid == 1
            cand_tokrel += n_tok == 1

            if n_tok == 1 and rem >= 0 and docc >= 0:
                exact += 1
                b = "with" if ck["other_identified"] else "without"
                ex_n[b] += 1
                ex_r[b] += rem
            elif n_tok > 1:
                disjoint["multi_contributor"] += 1
            elif n_tok == 0:
                disjoint["zero_token_relevant"] += 1
            elif docc < 0:
                disjoint["docc_negative"] += 1
            else:
                disjoint["remainder_negative"] += 1
            marginal["multi_contributor"] += n_tok > 1
            marginal["zero_token_relevant"] += n_tok == 0
            marginal["docc_negative"] += docc < 0
            marginal["remainder_negative"] += rem < 0

            # Design C bucket assignment: every branch books exactly docc.
            if docc < 0:
                booked = docc
                mass["quarantined"] += docc
            elif docc < out_prev:
                booked = docc
                mass["ambiguous_negative_remainder"] += docc
            else:
                booked = out_prev + rem
                mass["feed_forward"] += out_prev
                if n_tok == 1:
                    mass["exact_remainder"] += rem
                else:
                    mass["ambiguous_remainder"] += rem
            rows.append((booked, docc < 0))

        head = usage_context(uc[0]["merged"])
        final = usage_context(uc[-1]["merged"])
        lanes_hold += head + sum(b for b, _q in rows) == final
        # Counterfactual: the quarantined intervals are dropped from the chain
        # rather than shown in a reconciliation footer.
        cf = head + sum(b for b, q in rows if not q)
        if cf == final:
            cf_hold += 1
        else:
            cf_err[magnitude(cf - final)] += 1
            cf_fail_quar += any(q for _b, q in rows)

    def pct(a, b):
        return f"{a}/{b} = {100.0 * a / b:.2f}%" if b else f"{a}/0 = n/a"

    print(f"corpus: {len(files)} files ({tally['unreadable']} unreadable), "
          f"{tally['records']} parsed records, {tally['bad']} unparseable "
          f"lines skipped, {tally['blank']} blank lines skipped, "
          f"{tally['dup_uuid']} duplicate-uuid records dropped "
          f"({tally['dup_uuid_assistant']} of them assistant records)")
    print(f"calls: {calls_total} total ({calls_noid} from assistant records "
          f"with no message.id), usage-carrying {pct(calls_carrying, calls_total)}"
          f"; lanes (files with >=1 usage-carrying call): {lanes}; "
          f"intervals: {intervals}")

    print(f"\n[a] exact attribution (population: {intervals} intervals)")
    print(f"  exactly-1 token-relevant AND R>=0 AND docc>=0: {pct(exact, intervals)}")
    print("  failure reasons, DISJOINT (priority: multi > zero > docc<0 > R<0):")
    for k, v in disjoint.most_common():
        print(f"    {k}: {pct(v, intervals)}")
    print("  failure reasons, MARGINAL (overlapping, same population):")
    for k in ("multi_contributor", "zero_token_relevant",
              "docc_negative", "remainder_negative"):
        print(f"    {k}: {pct(marginal[k], intervals)}")

    print(f"\n[b] candidate definition, exactly-one rate "
          f"(same population: {intervals} intervals)")
    print(f"  all non-assistant records (Phase 0 s3 defn): {pct(cand_all, intervals)}")
    print(f"  non-assistant WITH uuid (bookkeeping excluded): "
          f"{pct(cand_uuid, intervals)}")
    print(f"  token-relevant only (tool_result | user_text): "
          f"{pct(cand_tokrel, intervals)}")
    print("  contributor kinds over all boundary records:")
    for k, v in kinds.most_common():
        print(f"    {k}: {v}")
    print("  is 'token-relevant' safe? mean exact remainder R by whether the "
          "interval ALSO held uuid-bearing non-user records (attachment/system) "
          f"(population: {exact} exact intervals):")
    for k in ("without", "with"):
        n = ex_n[k]
        avg = f"{ex_r[k] / n:.0f}" if n else "n/a"
        print(f"    {k} such records: n={n}, mean R={avg}")

    print("\n[c] interleaved ids and boundary pathologies")
    for label, c in (("AFTER within-file uuid dedup (the spec'd boundary)",
                      dedup_path),
                     ("BEFORE dedup, same files (Phase 0 s2's construction)",
                      raw_path)):
        print(f"  {label}:")
        print(f"    interleaved message.ids: "
              f"{pct(c['interleaved_ids'], c['calls'])} (population: calls)")
        print(f"    intervals adjacent to an interleaved id: "
              f"{pct(c['adjacent'], c['intervals'])}")
        print(f"    intervals with zero records between: "
              f"{pct(c['zero_records'], c['intervals'])} "
              f"[adjacent to interleaved: {c['zero_records_il']}]")
        print(f"    intervals INVERTED (prev last >= cur first): "
              f"{pct(c['inverted'], c['intervals'])} "
              f"[adjacent to interleaved: {c['inverted_il']}]")
        print(f"    intervals OVERLAPPING another interval: "
              f"{pct(c['overlap'], c['intervals'])} "
              f"[adjacent to interleaved: {c['overlap_il']}]")

    print(f"\n[d] conservation: lane_head + sum(buckets) == final occupancy "
          f"(population: {lanes} lanes)")
    print(f"  holds exactly, as specified: {pct(lanes_hold, lanes)}")
    print("  NOTE: tautological by construction -- every branch books exactly "
          "docc, so the buckets telescope to final-head. It tests the CHAIN "
          "(no interval dropped, reordered, or double-counted), not the split.")
    print("  global bucket mass (context tokens):")
    for k, v in mass.most_common():
        print(f"    {k}: {v}")
    print(f"  counterfactual (quarantined intervals dropped from the chain "
          f"instead of footed): holds {pct(cf_hold, lanes)}")
    print(f"    failing lanes that contain a quarantined interval: {cf_fail_quar}")
    print("    |error| magnitude histogram over failing lanes:")
    for k in sorted(cf_err, key=lambda s: (len(s), s)):
        print(f"      {k}: {cf_err[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
