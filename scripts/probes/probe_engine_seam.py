#!/usr/bin/env python3
"""Phase 0c probe: does the recommended fact shape feed the PORTED engine unmodified?

Builds Design C + panel-graft facts over every ``*.jsonl`` under
``Path.home()/".claude"/"projects"`` and drives ``lib_drill`` exactly as shipped.
No engine byte is edited; the one accommodation is the shim below = finding [0].

``generation`` facts carry ``spend`` / ``output_tokens`` / ``context_tokens``,
plus ``context_delta`` as v1 carried it -- for finding [3] only. ``increment``
facts (boundary and bucket rules from the sibling ``probe_interval_boundary.py``)
carry ``context_delta`` and ``cause.*``. Both carry ``lane``, ``agent_id`` and
``locator``. Aggregate counts, opaque ordinals and normalised command heads
only on stdout: no ids, paths, transcript text.
"""
import importlib
import json
import sys
import types
from collections import Counter
from pathlib import Path

# SHIM (finding [0]). Ported sa_schema.py imports `lib_cli` / `lib_dataset` for its
# CLI main(); unported, so `import lib_drill` raises. Stubbed, never edited.
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS / "lib"))
sys.path.insert(0, str(SCRIPTS))
_pkg = importlib.import_module("lib")
for _n in ("lib_cli", "lib_dataset"):
    _m = types.ModuleType("lib." + _n)
    sys.modules["lib." + _n] = _m
    setattr(_pkg, _n, _m)
import sa_schema  # noqa: E402
import lib_drill  # noqa: E402
from lib_usage import (context_delta, max_merge_usage,  # noqa: E402
                       usage_context, usage_spend)

UF = ("input_tokens", "output_tokens",
      "cache_read_input_tokens", "cache_creation_input_tokens")
FILE_TOOLS = {"Read", "Write", "Edit", "NotebookEdit"}
INC = ("kind", "increment")
GEN = ("kind", "generation")


def _msg(rec):
    m = rec.get("message")
    return m if isinstance(m, dict) else {}


def _blocks(rec):
    c = _msg(rec).get("content")
    return [b for b in c if isinstance(b, dict)] if isinstance(c, list) else []


def classify(rec):
    if rec.get("type") == "user":
        return ("tool_result" if any(b.get("type") == "tool_result"
                                     for b in _blocks(rec)) else "user_text")
    return None


def head_of(name, inp):
    """GRAFT UNDER TEST. Bash -> first token, never a path; file tools -> ext."""
    if not isinstance(inp, dict):
        return None
    if name in FILE_TOOLS:
        f = inp.get("file_path") or inp.get("notebook_path")
        ext = Path(f).suffix.lower() if isinstance(f, str) else ""
        return ext if (1 < len(ext) <= 8 and ext[1:].isalnum()) else "[noext]"
    if name != "Bash" or not isinstance(inp.get("command"), str):
        return None
    tok = inp["command"].strip().split(None, 1)
    if not tok:
        return None
    tok = tok[0]
    if "/" in tok or "\\" in tok or tok[0] in "~$":
        return "[path]"
    if len(tok) > 20:
        return "[long]"
    return tok if all(c.isalnum() or c in "._-" for c in tok) else "[other]"


def read_file(path, tally):
    """uuid-deduped records, in order, stamped with PHYSICAL line numbers: blank
    and unparseable lines are skipped, so parsed index N is not raw line N."""
    try:
        text = path.read_text(errors="replace")
    except OSError:
        tally["unreadable"] += 1
        return []
    recs, seen = [], set()
    for ln, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            rec = None
        if not isinstance(rec, dict):
            tally["bad"] += 1
            continue
        tally["records"] += 1
        u = rec.get("uuid")
        if u:
            if u in seen:
                tally["dup_uuid"] += 1
                continue
            seen.add(u)
        rec["__ln"] = ln
        recs.append(rec)
    return recs


def build_calls(recs):
    groups = {}
    for i, rec in enumerate(recs):
        if rec.get("type") != "assistant":
            continue
        mid = _msg(rec).get("id")
        groups.setdefault(mid if mid is not None else ("_noid_", i), []).append(i)
    calls = []
    for pos in groups.values():
        merged = max_merge_usage([_msg(recs[i]).get("usage") for i in pos])
        calls.append({"first": pos[0], "last": pos[-1], "merged": merged,
                      "carrying": any(int(merged.get(k, 0) or 0) for k in UF),
                      "line": recs[pos[0]].get("__ln"),
                      "agent": recs[pos[0]].get("agentId")})
    calls.sort(key=lambda c: c["first"])
    return calls


def tool_index(recs):
    """{tool_use_id: (tool_name, input_head)} from assistant tool_use blocks."""
    out = {}
    for rec in recs:
        if rec.get("type") != "assistant":
            continue
        for b in _blocks(rec):
            if b.get("type") == "tool_use" and b.get("id"):
                out[b["id"]] = (b.get("name"), head_of(b.get("name"), b.get("input")))
    return out


def result_tool(rec, tools):
    for b in _blocks(rec):
        if b.get("tool_use_id") in tools:
            return tools[b["tool_use_id"]]
    return (None, None)


def build_facts():
    """The corpus as one {fact_id: fact} map, plus tallies and Sigma lane finals."""
    files = sorted((Path.home() / ".claude" / "projects").rglob("*.jsonl"))
    facts, tally, agents, lane_final = {}, Counter(), {}, {}
    for lane, path in enumerate(files):
        recs = read_file(path, tally)
        uc = [c for c in build_calls(recs) if c["carrying"]]
        if not uc:
            continue
        tools = tool_index(recs)
        base = {"lane": lane}
        for c in uc:
            if c["agent"]:
                base["agent_id"] = agents.setdefault(c["agent"], "a%d" % len(agents))
                break

        def mint(cause, delta, line):
            facts["i%d" % tally["inc"]] = dict(
                base, kind="increment", cause=cause,
                metrics={"context_delta": delta},
                locator={"line": line, "source": lane})
            tally["inc"] += 1

        # Deltas first so a generation fact can carry its own (the v1 carrier).
        deltas = [usage_context(uc[0]["merged"])] + [
            context_delta(uc[n - 1]["merged"], uc[n]["merged"])
            for n in range(1, len(uc))]
        for c, d in zip(uc, deltas):
            facts["g%d" % tally["gen"]] = dict(
                base, kind="generation", locator={"line": c["line"], "source": lane},
                metrics={"spend": usage_spend(c["merged"]), "context_delta": d,
                         "output_tokens": int(c["merged"].get("output_tokens", 0) or 0),
                         "context_tokens": usage_context(c["merged"])})
            tally["gen"] += 1
        mint({"kind": "lane_head"}, deltas[0], uc[0]["line"])

        for n in range(1, len(uc)):
            prev, cur, docc = uc[n - 1], uc[n], deltas[n]
            out_prev = int(prev["merged"].get("output_tokens", 0) or 0)
            tokrel = [(r, k) for r in recs[prev["last"] + 1:cur["first"]]
                      if (k := classify(r))]
            cands = sorted(set(result_tool(r, tools)[0] or k for r, k in tokrel))
            if docc < 0:
                mint({"kind": "shrink"}, docc, cur["line"])
            elif docc < out_prev:
                mint({"kind": "ambiguous", "candidates": cands}, docc, cur["line"])
            else:
                mint({"kind": "feed_forward"}, out_prev, prev["line"])
                rem = docc - out_prev
                if len(tokrel) == 1:
                    rec, kind = tokrel[0]
                    name, hd = result_tool(rec, tools)   # (None, None) on text
                    cause = {"kind": kind}
                    if name:
                        cause["tool_name"] = name
                    if hd:
                        cause["tool_input_head"] = hd
                    mint(cause, rem, rec.get("__ln"))
                else:
                    mint({"kind": "ambiguous", "candidates": cands}, rem, cur["line"])
        lane_final[lane] = usage_context(uc[-1]["merged"])
    tally["files"] = len(files)
    tally["lanes"] = len(lane_final)
    return facts, tally, sum(lane_final.values())


def pub(key):
    s = key if isinstance(key, str) else json.dumps(key, sort_keys=True)
    return (s[:38] + "..") if len(s) > 40 else s


def row(r):
    """One ranked dimension; statistic-scoped fields read, never defaulted."""
    tail = ("conc=%.4f basis=%s/%s top_metric_share=%.4f"
            % (r["conc"], r["dist_basis"], r["dist_basis_reason"],
               r["top_metric_share"])
            if r["statistic"] == lib_drill.CONCENTRATION else "stat=%.4f" % r["stat"])
    return ("    %-24s score=%.4f cover=%.3f card=%-5d tms=%.3f n_meas=%-7d "
            "top=%-14s %s%s%s"
            % (r["dimension"], r["score"], r["cover"], r["card"],
               r["top_member_share"], r["n_measured"], pub(r["top_key"]), tail,
               (" aliases=%s" % r["aliases"]) if r["aliases"] else "",
               ("  [FOLDED INTO %s]" % r["folded_into"]) if r["folded_into"] else ""))


def show(facts, base, dim, metric, denom, keys):
    """resolve_path each bucket of ``dim``, as % of ``denom``."""
    for key in keys:
        node = lib_drill.resolve_path(facts, base + [(dim, key)], metric)
        print("      %-13s facts=%-6d %s=%-15.1f %+6.2f%% of total"
              % (pub(key), len(node["members"]), metric, node["total"],
                 100.0 * node["total"] / denom))


def top_real(facts, members, dim, metric, k=3):
    """k heaviest NON-RESIDUAL buckets (``top_key`` includes, and here IS, it)."""
    mass = Counter()
    for m in members:
        key = lib_drill.dimension_value(facts[m], dim)
        if key != lib_drill.RESIDUAL:
            mass[key] += (facts[m].get("metrics") or {}).get(metric, 0)
    return [k for k, _ in mass.most_common(k)]


DEMO = {"kind": "k", "cause": {"kind": "a", "tool": {"name": "Bash"}},
        "lst": [1, 2], "locator": {"line": 1, "source": 7}, "preview": "t"}
WANT = ("cause.kind", "cause.tool_name", "cause.tool_input_head",
        "cause.candidates", "agent_id", "lane", "locator.line", "locator.source")


def main():
    facts, t, chain = build_facts()
    p = print
    p("corpus: %d files, %d records, %d unparseable, %d dup-uuid dropped, %d lanes"
      "\nfacts: %d = %d generation + %d increment  [POPULATION for every figure "
      "below unless restated]"
      % (t["files"], t["records"], t["bad"], t["dup_uuid"], t["lanes"],
         len(facts), t["gen"], t["inc"]))
    p("\n[0] SHIM the engine required (it must not need one): sa_schema.py:23 "
      "`from lib import lib_cli, lib_dataset`, unported. ZERO engine bytes changed.")

    inc = lib_drill.resolve_path(facts, [INC], "context_delta")
    gen = lib_drill.resolve_path(facts, [GEN], "spend")
    scope, present = sa_schema.scopes(facts)
    p("\n[1] SEAM: discover_dimensions at the increment root, context_delta "
      "(population: %d increments); shapes=%s"
      % (len(inc["members"]), sorted(present)))
    ranked = lib_drill.discover_dimensions(facts, inc["members"], "context_delta",
                                           collapse=False)
    for r in ranked:
        p(row(r))
    up = set(r["dimension"] for r in ranked if not r["folded_into"])
    p("    surfaced=%s\n    NOT surfaced=%s (all in scope for 'increment': %s)"
      % ([d for d in WANT if d in up], [d for d in WANT if d not in up],
         all(scope.get(d) for d in WANT)))
    p("    flatten(synthetic)=%s ; dimension_value walks any depth (cause.tool.name"
      " -> %r) but flatten stops at 2, so 3-deep is never OFFERED ; a list "
      "json-dumps to ONE opaque key (lst -> %r)"
      % (sorted(sa_schema.flatten(DEMO)),
         lib_drill.dimension_value(DEMO, "cause.tool.name"),
         lib_drill.dimension_value(DEMO, "lst")))
    cands = Counter(lib_drill.dimension_value(facts[m], "cause.candidates")
                    for m in inc["members"])
    res = cands.get(lib_drill.RESIDUAL, 0)
    p("    cause.candidates: %d keys, residual=%d (%.3f) -> REJECTED by Filter C "
      "(> %.2f); '[]' bucket=%d, i.e. an empty list != the residual"
      % (len(cands), res, res / float(len(inc["members"])),
         lib_drill.TOP_MEMBER_SHARE_MAX, cands.get("[]", 0)))

    p("\n[2] CHAIN INTEGRITY (population: %d lanes / %d increments)"
      % (t["lanes"], len(inc["members"])))
    show(facts, [INC], "cause.kind", "context_delta", chain,
         ("lane_head", "feed_forward", "tool_result", "user_text",
          "ambiguous", "shrink"))
    p("    root resolve_path over increments=%r (%s, n_valued=%d); sum over lanes "
      "of final observed occupancy=%r; VERDICT %s"
      % (inc["total"], inc["total_statistic"], inc["n_valued"], chain,
         "PASS" if inc["total"] == chain else "FAIL %d" % (inc["total"] - chain)))

    p("\n[3] DOUBLE-CARRIER HAZARD: context_delta on BOTH kinds in ONE map")
    both = lib_drill.resolve_path(facts, [], "context_delta")
    p("    root, no predicate, all %d facts=%r ; true total (chain)=%r ; "
      "DOUBLE-COUNT FACTOR %.6fx ; predicate [(\"kind\",\"increment\")]=%r -> %s"
      % (len(facts), both["total"], chain, both["total"] / float(chain),
         inc["total"], "restores it" if inc["total"] == chain else "does NOT"))
    mixed = lib_drill.discover_dimensions(facts, list(facts), "context_delta")
    p("    SECOND cost: at the mixed root Filter B (containment) drops every "
      "increment-only axis; offered=%s" % [r["dimension"] for r in mixed])

    p("\n[4] THE PIVOT (population: %d increments, context_delta)" % len(inc["members"]))
    live = [r for r in ranked if not r["folded_into"]]
    top = {r["dimension"]: (i + 1, r) for i, r in enumerate(live)}
    p("    ranks FIRST: %s (score=%.4f)" % (live[0]["dimension"], live[0]["score"]))
    for dim in ("cause.tool_input_head", "agent_id"):
        if dim not in top:
            p("    %-21s NOT OFFERED (filtered before statistics)" % dim)
            continue
        rank, r = top[dim]
        p("    %-21s rank #%d of %d (stats in [1]); engine top_key=%s "
          "(top_metric_share=%.4f) IS the residual"
          % (dim, rank, len(live), pub(r["top_key"]), r["top_metric_share"]))
        show(facts, [INC], dim, "context_delta", chain,
             top_real(facts, inc["members"], dim, "context_delta"))

    p("\n[5] SPEND preset: same engine, same map, other predicate. root=%.1f %s "
      "(%s, n_valued=%d, population: %d generation facts)"
      % (gen["total"], sa_schema.metric_units("spend"), gen["total_statistic"],
         gen["n_valued"], len(gen["members"])))
    for r in lib_drill.discover_dimensions(facts, gen["members"], "spend"):
        p(row(r))
    p("    drill by agent_id (top_key = residual = no agentId):")
    show(facts, [GEN], "agent_id", "spend", gen["total"],
         top_real(facts, gen["members"], "agent_id", "spend"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
