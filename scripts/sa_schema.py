#!/usr/bin/env python3
"""Census the fact schema of one or more Schema V2 datasets.

The fact taxonomy is a *measurement*, not prose: which attributes and metrics
exist on which fact shape, how each metric may be aggregated, which attributes
functionally determine others (the drill-order question), and how much of the
tool-output universe is missing its producer attribution.

This script is the generated replacement for the hand-transcribed matrices that
used to live in ``references/RESEARCH_fact_taxonomy.md``. Run it instead of
trusting a doc:

    sa schema dataset.ds.json
    sa schema a.ds.json b.ds.json --output json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import lib_cli, lib_dataset  # noqa: E402

# Fields that carry evidence/identity rather than a slice axis or a measure.
EVIDENCE_FIELDS = ("leaf_id", "preview", "locator", "provenance", "lint")

# How each metric may legally be combined across facts. Summing a peak or a
# derived metric is a correctness bug, so the class is declared, not inferred.
#
# ONE SUBAGENT, TWO NUMBERS. A real subagent's calls sum to
# `cache_read_input_tokens` = 4,950,327 while the largest window it ever held was
# 131,612 tokens. The two are 37.6x apart, and both are arithmetic on the same
# field: `cache_read` is the size of the prompt on ONE call, a STOCK re-reported
# every call, not a flow that accumulates. Measured error on real subagents runs
# 4.8x to 37.6x. It was declared `additive` here, and nothing pinned the
# declaration, so the sum it licensed passed for "token usage".
# `references/token-accounting.md` trap #1 names the error.
#
# The stock reading is not the only one, which is why moving it to `peak` alone
# would have LOST a capability rather than fixed a bug: cache reads bill at ~0.1x
# base input price, so under SPEND those same tokens genuinely do add up. Three
# questions, three metrics, none of them interchangeable:
#
#   context_tokens  peak      how much window was OCCUPIED at once
#   context_delta   additive  how much the window GREW, per call
#   spend           additive  what the calls' INPUT cost, in base-token-equivalents
#
# `spend` and `context_delta` are declared here and computed by
# `lib_parse.usage_spend` / `lib_parse.context_delta` (that module carries the
# cost weights and why they are what they are). Both are now carried on EVERY
# generation fact (`sa_aggregate.py:271-272`, landed in `1763152`), so both drill;
# the declaration is why. `tests/test_spend_and_occupancy.py` is the record for it.
#
# OWNER DECISION 2026-07-26, quoted from `references/token-accounting.md`:
# "**Keep the JSON keys `spend` / `context_delta` whatever the columns are
# called** — otherwise a rename becomes a migration."
# (`Ctx-Added` is the shipped column name.)
AGGREGATION = {
    "occurrences": "additive",
    "observed_chars": "additive",
    "duration_s": "additive",
    "input_tokens": "additive",
    "output_tokens": "additive",
    "cache_read_input_tokens": "peak",
    "cache_creation_input_tokens": "additive",
    "text_chars": "additive",
    "thinking_chars": "additive",
    "context_tokens": "peak",
    "context_delta": "additive",
    "spend": "additive",
    "rate": "derived",
}

# The noun each metric's mass is counted in, for any surface that has to say
# "share of ___". Declared beside AGGREGATION and keyed by METRIC, because that
# is what the unit is a property of — a view-keyed table would restate the same
# noun once per view that happens to use the metric, and the copies would drift.
# `metric_units` is the accessor; nothing should read this dict directly.
METRIC_UNITS = {
    "occurrences": "occurrences",
    "observed_chars": "chars",
    "duration_s": "seconds",
    "input_tokens": "input tokens",
    "output_tokens": "output tokens",
    "cache_read_input_tokens": "cache-read tokens",
    "cache_creation_input_tokens": "cache-creation tokens",
    "text_chars": "chars",
    "thinking_chars": "thinking chars",
    "context_tokens": "tokens",
    "context_delta": "occupancy-change tokens",
    # "input-side" is load-bearing: usage_spend covers the three INPUT classes and
    # deliberately excludes output_tokens, which bills on another axis. A column
    # labelled with the bare noun reads as total cost, which this is not.
    "spend": "input-side base-token-equivalents",
    "rate": "tokens/second",
}


def metric_units(metric):
    """The display noun for ``metric``; a neutral fallback for an unknown one.

    Falls back rather than raising: an unnamed metric is a labelling gap, and a
    report that refuses to render because of one is a worse outcome than a report
    that says "the metric".

    The ARITHMETIC is a different question, and it is not asked as an admission
    test anywhere. ``lib_drill.statistic_for`` reads ``AGGREGATION`` to SELECT the
    statistic — entropy concentration over mass shares for an ``additive`` metric,
    explained variance for a ``peak`` or a ``derived`` ratio — and raises only for
    a metric the schema does not classify at all. There is no gate that admits one
    class and refuses the rest; see ``lib_drill``'s note that AGGREGATION
    dispatches and does not gate, and ``tests/test_variance_explained.py``.
    """
    return METRIC_UNITS.get(metric, "the metric")

# Candidate functional dependencies: does `determinant` fix `dependent`?
# A holding dependency means the dependent adds no drill information once the
# determinant is fixed - it must not be offered as a further slice.
FD_CANDIDATES = (
    ("cluster_id", "tool_name"),
    ("subagent_info.agent_id", "subagent_info.agent_type"),
    ("subagent_info.agent_id", "subagent_info.spawn_depth"),
    ("subagent_info.agent_id", "subagent_info.label"),
    ("subagent_info.agent_id", "subagent_info.ordinal"),
    ("subagent_info.agent_id", "subagent_info.parent_agent_id"),
    ("locator.source", "subagent_info.agent_id"),
    ("tool_name", "cluster_id"),
    ("locator.source", "kind"),
)


def shape_of(fact):
    """The taxonomy key: kind, split further only where field sets genuinely differ."""
    kind = fact.get("kind", "?")
    if kind != "permission":
        return kind
    if "static_lint" in (fact.get("provenance") or []):
        return "permission/static_lint"
    return "permission/" + str(fact.get("permission_subkind", "?"))


def flatten(fact):
    """Fact -> {dotted field name: value} for attribute-side fields only."""
    out = {}
    for key, value in fact.items():
        if key in EVIDENCE_FIELDS or key == "metrics":
            continue
        if isinstance(value, dict):
            for sub, subvalue in value.items():
                out["%s.%s" % (key, sub)] = subvalue
        else:
            out[key] = value
    locator = fact.get("locator")
    if isinstance(locator, dict):
        for sub, subvalue in locator.items():
            out["locator.%s" % sub] = subvalue
    return out


def scopes(facts):
    """Cheap one-pass scope table: ({field: {shape, ...}}, {shape present, ...}).

    This is the query-path form of the census's attribute x shape matrix — a
    field is in a shape's scope iff at least one fact of that shape carries it,
    which is exactly a non-``None`` cell there. The drill engine's applicability
    gate (BUILD_SPEC.md §1, Filter B) and ``census()`` must derive scope from the
    same rule, so this is the one place the rule is written.

    Deliberately *not* ``census()``: that one takes datasets rather than a facts
    map, evaluates functional dependencies over every candidate pair, and retains
    every distinct value of every field — far too costly to run per query.
    """
    scope, present = {}, set()
    for fact in facts.values():
        shape = shape_of(fact)
        present.add(shape)
        for field in flatten(fact):
            scope.setdefault(field, set()).add(shape)
    return scope, present


def census(datasets):
    """Compute the full schema census over the union of the given datasets."""
    facts = {}
    for ds in datasets:
        facts.update(ds.get("facts", {}))

    shape_counts = {}
    attr_present, attr_values = {}, {}
    metric_present = {}
    for fact in facts.values():
        shape = shape_of(fact)
        shape_counts[shape] = shape_counts.get(shape, 0) + 1
        for field, value in flatten(fact).items():
            attr_present.setdefault(field, {})
            attr_present[field][shape] = attr_present[field].get(shape, 0) + 1
            if isinstance(value, (str, int, float, bool)) or value is None:
                attr_values.setdefault(field, set()).add(value)
        for metric in (fact.get("metrics") or {}):
            metric_present.setdefault(metric, {})
            metric_present[metric][shape] = metric_present[metric].get(shape, 0) + 1

    shapes = sorted(shape_counts)
    universal = [f for f in sorted(attr_present)
                 if all(attr_present[f].get(s, 0) == shape_counts[s] for s in shapes)]

    return {
        "fact_count": len(facts),
        "shapes": [{"shape": s, "facts": shape_counts[s]} for s in shapes],
        "attributes": _matrix(attr_present, shape_counts, shapes, attr_values),
        "metrics": _matrix(metric_present, shape_counts, shapes, None),
        "universal_attributes": universal,
        "unclassified_metrics": sorted(m for m in metric_present if m not in AGGREGATION),
        "functional_dependencies": _fds(facts),
        "attribution_gap": _attribution_gap(facts),
    }


def _matrix(present, shape_counts, shapes, values):
    """Rows of field x shape presence: 'all' / 'some' / absent, plus cardinality."""
    rows = []
    for field in sorted(present):
        cells = {}
        for shape in shapes:
            n = present[field].get(shape, 0)
            cells[shape] = "all" if n == shape_counts[shape] else ("some" if n else None)
        row = {"field": field, "cells": cells,
               "facts": sum(present[field].values())}
        if values is not None:
            row["cardinality"] = len(values.get(field, ()))
        else:
            row["aggregation"] = AGGREGATION.get(field, "UNCLASSIFIED")
        rows.append(row)
    return rows


def _get(fact, dotted):
    """Read a possibly-nested field by dotted path."""
    node = fact
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def _fds(facts):
    """For each candidate pair, does the determinant fix the dependent in this data?"""
    results = []
    for determinant, dependent in FD_CANDIDATES:
        groups = {}
        for fact in facts.values():
            dv, pv = _get(fact, determinant), _get(fact, dependent)
            if dv is None or pv is None:
                continue
            groups.setdefault(_key(dv), set()).add(_key(pv))
        violations = {k: sorted(v, key=str) for k, v in groups.items() if len(v) > 1}
        results.append({
            "determinant": determinant,
            "dependent": dependent,
            "support": len(groups),
            "violations": len(violations),
            "holds": bool(groups) and not violations,
            "example_violation": _example(violations),
        })
    return results


def _key(value):
    return json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value


def _example(violations):
    if not violations:
        return None
    key = sorted(violations, key=str)[0]
    return {"determinant_value": key, "dependent_values": violations[key][:4]}


def _attribution_gap(facts):
    """How much tool output can be sliced by producer? The P0 join, measured."""
    calls = [f for f in facts.values() if f.get("kind") == "tool"]
    results = [f for f in facts.values()
               if f.get("kind") == "injected" and f.get("injected_category") == "tool_results"]
    # tool_use_id is carried on the *locator*, not as a top-level attribute - so it
    # is evidence today, not a slice axis. That is precisely the join to be built.
    fields = ("locator.tool_use_id", "tool_name", "subagent_info")
    rows = []
    for label, group in (("tool_call", calls), ("tool_result", results)):
        entry = {"population": label, "facts": len(group)}
        for field in fields:
            entry[field] = sum(1 for f in group if _get(f, field) is not None)
        rows.append(entry)
    return rows


def render(data, out):
    """Text rendering; column order follows the shape census."""
    shapes = [s["shape"] for s in data["shapes"]]
    width = max([len(s) for s in shapes] + [4])
    glyph = {"all": "*".rjust(width), "some": "o".rjust(width), None: "-".rjust(width)}

    out.write("Facts: %d over %d shapes\n\n" % (data["fact_count"], len(shapes)))
    out.write("SHAPE COUNTS\n")
    for row in data["shapes"]:
        out.write("  %-28s %8d\n" % (row["shape"], row["facts"]))

    header = "  ".join(s.rjust(width) for s in shapes)
    for title, rows, extra in (("ATTRIBUTES x SHAPE", data["attributes"], "cardinality"),
                               ("METRICS x SHAPE", data["metrics"], "aggregation")):
        out.write("\n%s   (* = on every fact of that shape, o = on some, - = absent)\n" % title)
        out.write("%-30s  %s   %s\n" % ("field", header, extra))
        for row in rows:
            cells = "  ".join(glyph[row["cells"][s]] for s in shapes)
            out.write("%-30s  %s   %s\n" % (row["field"], cells, row[extra]))

    out.write("\nUNIVERSAL ATTRIBUTES (on every fact of every shape): %s\n"
              % (", ".join(data["universal_attributes"]) or "(none)"))
    if data["unclassified_metrics"]:
        out.write("UNCLASSIFIED METRICS (no declared aggregation class): %s\n"
                  % ", ".join(data["unclassified_metrics"]))

    out.write("\nFUNCTIONAL DEPENDENCIES  (holds => dependent adds no drill information)\n")
    out.write("%-48s %8s %10s  %s\n" % ("dependency", "support", "violations", "holds"))
    for fd in data["functional_dependencies"]:
        out.write("%-48s %8d %10d  %s\n" % (
            "%s -> %s" % (fd["determinant"], fd["dependent"]),
            fd["support"], fd["violations"], "yes" if fd["holds"] else "NO"))
        if fd["example_violation"]:
            out.write("      e.g. %s => %s\n" % (fd["example_violation"]["determinant_value"],
                                                 fd["example_violation"]["dependent_values"]))

    out.write("\nATTRIBUTION GAP  (can tool output be sliced by producer?)\n")
    out.write("%-14s %8s %20s %10s %14s\n"
              % ("population", "facts", "locator.tool_use_id", "tool_name", "subagent_info"))
    for row in data["attribution_gap"]:
        out.write("%-14s %8d %20d %10d %14d\n"
                  % (row["population"], row["facts"], row["locator.tool_use_id"],
                     row["tool_name"], row["subagent_info"]))


def main(argv=None):
    ap = argparse.ArgumentParser(prog=lib_cli.prog(__file__),
                                 description="Census the fact schema of Schema V2 datasets.")
    ap.add_argument("ds", nargs="+", help="Path(s) to Schema V2 dataset (ds.json); censused as a union")
    ap.add_argument("--output", choices=["text", "json"], default="text", help="Output format")
    lib_dataset.add_stale_arg(ap)
    a = ap.parse_args(argv)

    datasets = []
    for path in a.ds:
        try:
            ds = json.loads(Path(path).read_text())
        except (OSError, ValueError) as exc:
            sys.stderr.write("sa_schema: cannot read %s: %s\n" % (path, exc))
            return 2
        # The census is the empirical source for Filter B's scope table, so a
        # stale dataset here silently mis-derives the engine's gate.
        if not a.allow_stale_dataset:
            stale = lib_dataset.version_error(ds, path, tool="sa schema")
            if stale:
                sys.stderr.write(stale + "\n")
                return 2
        datasets.append(ds)

    data = census(datasets)
    if a.output == "json":
        print(json.dumps(data, indent=2, sort_keys=True, default=str))
    else:
        render(data, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
