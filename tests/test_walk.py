"""The walk: chain integrity, identity, max-merge, the exact case."""
import json

import pytest

import fixtures as fx
from sa import query, schema
from sa.schema import CALL, INCREMENT


def _one_window(tmp_path, records=None):
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": records or fx.window_records()})
    return fx.load_facts(root)[1]


def _chain(facts):
    """Per window: (sum of booked increments, final occupancy)."""
    booked, final = {}, {}
    for f in facts:
        if f.kind == INCREMENT:
            booked[f.locator.file] = booked.get(f.locator.file, 0) + f.metrics["context_delta"]
        else:
            final[f.locator.file] = f.metrics["context_tokens"]
    return booked, final


def test_chain_integrity_holds_over_every_branch(tmp_path):
    facts = _one_window(tmp_path)
    causes = {f.dims["cause"] for f in facts if f.kind == INCREMENT}
    reasons = {f.dims.get("reason") for f in facts if f.kind == INCREMENT}
    assert causes == set(schema.CAUSES), "fixture must exercise every cause"
    assert set(schema.REASONS) - reasons == {schema.NO_CONTRIBUTOR}
    booked, final = _chain(facts)
    assert booked == final == {next(iter(final)): fx.FINAL_OCCUPANCY}
    r = query.reconcile(facts)
    assert r.holds and r.intervals == r.exact + r.ambiguous + r.shrink == 5
    assert (r.exact, r.ambiguous, r.shrink) == (2, 2, 1)


def test_chain_integrity_fails_without_shrink(tmp_path):
    facts = _one_window(tmp_path)
    mutant = [f for f in facts if f.dims.get("cause") != schema.SHRINK]
    assert len(mutant) < len(facts)
    booked, final = _chain(mutant)
    assert booked != final


def test_replayed_records_count_once_and_sibling_forks_twice(tmp_path):
    one = fx.corpus(tmp_path / "one", {"proj-a/sess-0001.jsonl": fx.window_records()})
    resumed = fx.corpus(tmp_path / "resumed", {
        "proj-a/sess-0001.jsonl": fx.window_records(),
        "proj-a/sess-0002.jsonl": fx.window_records()})
    forked = fx.corpus(tmp_path / "forked", {
        "proj-a/sess-0001.jsonl": fx.window_records(),
        "proj-a/sess-0001/subagents/agent-fake1.jsonl": fx.window_records("fork-")})

    def totals(root):
        loaded, facts = fx.load_facts(root)
        return loaded, {m: sum(f.metrics.get(m, 0) for f in facts) for m in schema.METRICS
                        if schema.METRICS[m].aggregation == schema.ADDITIVE}

    base_loaded, base = totals(one)
    resumed_loaded, same = totals(resumed)
    forked_loaded, double = totals(forked)
    assert resumed_loaded.duplicate_records == len(fx.window_records())
    assert forked_loaded.duplicate_records == 0
    assert base_loaded.duplicate_records == 0
    assert same == base
    assert double == pytest.approx({m: 2 * v for m, v in base.items()})
    assert base["context_delta"] == fx.FINAL_OCCUPANCY


def test_split_message_id_takes_the_max_output(tmp_path):
    records = [
        fx.assistant("uuid-0001", "msg-0001", fx.usage(1000, 10)),
        fx.assistant("uuid-0002", "msg-0001", fx.usage(1000, 40)),
    ]
    facts = _one_window(tmp_path, records)
    calls = [f for f in facts if f.kind == CALL]
    assert len(calls) == 1
    assert calls[0].metrics["output_tokens"] == 40


def test_exact_interval_names_its_contributor_line(tmp_path):
    facts = _one_window(tmp_path)
    exact = [f for f in facts if f.dims.get("cause") == schema.TOOL_RESULT]
    first = exact[0]
    assert first.metrics["context_delta"] == fx.EXACT_FIRST_DELTA
    assert (first.dims["tool"], first.dims["head"]) == ("Bash", "pytest")
    with open(first.locator.file, encoding="utf-8") as handle:
        line = handle.read().splitlines()[first.locator.line - 1]
    assert json.loads(line)["uuid"] == first.locator.uuid == "uuid-0002"


def test_ambiguous_carries_candidates_as_evidence(tmp_path):
    facts = _one_window(tmp_path)
    multi = [f for f in facts if f.dims.get("reason") == schema.MULTI_CONTRIBUTOR]
    assert len(multi) == 1
    assert multi[0].dims["candidate_count"] == 2
    assert multi[0].evidence["candidates"] == ["uuid-0004", "uuid-0005"]
    assert "candidates" not in multi[0].dims


def test_usage_less_synthetic_record_is_not_a_call(tmp_path):
    records = fx.window_records()
    zero = dict.fromkeys(("input_tokens", "output_tokens", "cache_read_input_tokens",
                          "cache_creation_input_tokens"), 0)
    synthetic = fx.assistant("uuid-9999", "msg-9999", zero, model="<synthetic>")
    records.insert(1, synthetic)
    plain = _one_window(tmp_path / "plain")
    with_synthetic = _one_window(tmp_path / "synthetic", records)
    strip = lambda facts: [(f.kind, f.dims["cause"] if f.kind == INCREMENT else None,
                            f.metrics) for f in facts]
    assert strip(plain) == strip(with_synthetic)


def test_fork_context_ref_is_evidence_on_the_window_head(tmp_path):
    records = [{"type": "fork-context-ref", "parentSessionId": "sess-0000",
                "parentLastUuid": "uuid-0000", "agentId": "agent-fake1"}]
    records += fx.window_records()
    facts = _one_window(tmp_path, records)
    head = [f for f in facts if f.dims.get("cause") == schema.WINDOW_HEAD]
    assert len(head) == 1
    assert head[0].evidence == {"parent_session": "sess-0000",
                                "parent_last_uuid": "uuid-0000"}
    assert head[0].dims["agent"] == "agent-fake1"
