"""The walk: chain integrity, identity, max-merge, the exact case."""
import json

import pytest

import fixtures as fx
from sa import query, schema, walk
from sa.schema import CALL, INCREMENT

ADDITIVE_CALL_METRICS = [n for n, s in schema.METRICS.items()
                         if s.carrier == CALL and s.aggregation == schema.ADDITIVE]


def _one_window(tmp_path, records=None):
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": records or fx.window_records()})
    return fx.load_facts(root)[1]


def _chain(facts):
    """Per window: (sum of booked increments, final occupancy)."""
    booked, final = {}, {}
    for f in facts:
        if f.kind == INCREMENT:
            booked[f.locator.file] = booked.get(f.locator.file, 0) + f.metrics[fx.DELTA]
        else:
            final[f.locator.file] = f.metrics[fx.PEAK]
    return booked, final


def test_chain_integrity_holds_over_every_branch(tmp_path):
    facts = _one_window(tmp_path)
    causes = {f.dims["cause"] for f in facts if f.kind == INCREMENT}
    reasons = {f.dims["reason"] for f in facts if f.dims.get("reason")}
    assert causes == set(schema.CAUSES), "fixture must exercise every cause"
    assert reasons == set(schema.REASONS), "fixture must exercise every reason"
    booked, final = _chain(facts)
    assert booked == final == {next(iter(final)): fx.FINAL_OCCUPANCY}
    r = query.reconcile(facts)
    assert r.holds
    assert r.intervals == sum(f.kind == CALL for f in facts) - 1 == fx.INTERVALS
    assert (r.exact, r.ambiguous, r.shrink) == (fx.EXACT, fx.AMBIGUOUS, fx.SHRINK)


def test_reconciliation_fails_on_a_missing_or_extra_increment(tmp_path):
    facts = _one_window(tmp_path)
    without_shrink = [f for f in facts if f.dims.get("cause") != schema.SHRINK]
    assert len(without_shrink) < len(facts)
    assert not query.reconcile(without_shrink).holds
    exact = next(f for f in facts if f.dims.get("cause") in schema.EXACT_CAUSES)
    zero = exact._replace(metrics={fx.DELTA: 0})  # mass unchanged, interval count off by one
    doubled = facts + [zero]
    assert query.reconcile(doubled).booked == query.reconcile(facts).booked
    assert not query.reconcile(doubled).holds


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
    assert base[fx.DELTA] == fx.FINAL_OCCUPANCY


def test_the_longest_running_copy_owns_a_replayed_prefix_whatever_its_filename(tmp_path):
    """A partial replay plus continuation: the continuation starts at the same
    moment and runs later, so it owns the shared prefix; the original's
    remaining tail becomes a window of its own, booking window_head at its
    first live call."""
    original = fx.stamped(fx.window_records(), 0)
    continuation = fx.stamped(fx.window_records()[:5], 0) + fx.stamped(
        fx.window_records("c-")[5:], 20)
    results = []
    for names in (("sess-0001", "sess-0002"), ("sess-0002", "sess-0001")):
        root = fx.corpus(tmp_path / names[0], {
            "proj-a/%s.jsonl" % names[0]: original,
            "proj-a/%s.jsonl" % names[1]: continuation})
        loaded, facts = fx.load_facts(root)
        assert loaded.duplicate_records == 5
        by_file = {s.path.stem: [r.duplicate for r in s.records] for s in loaded.files}
        assert by_file[names[0]] == [True] * 5 + [False] * 9
        assert by_file[names[1]] == [False] * 14
        heads = [f for f in facts if f.dims.get("cause") == schema.WINDOW_HEAD]
        assert sorted(f.metrics[fx.DELTA] for f in heads) == [1000, 1500]
        results.append(query.reconcile(facts).by_cause)
    assert results[0] == results[1]
    assert sum(results[0].values()) == 2 * fx.FINAL_OCCUPANCY


def test_a_tool_result_keeps_its_tool_when_its_tool_use_was_replayed(tmp_path):
    original = fx.stamped(fx.window_records(), 0)
    branch = fx.stamped(fx.window_records()[:1], 0) + fx.stamped([
        fx.assistant("b-uuid-0002", "msg-0001", fx.usage(1000, 50)),  # same call, split
        fx.tool_result("b-uuid-0003", "toolu_0001"),
        fx.assistant("b-uuid-0004", "b-msg-0002", fx.usage(1300, 0)),
    ], 1)  # ends before the original does, so the original owns the prefix
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": original,
                                "proj-a/sess-0002.jsonl": branch})
    loaded, facts = fx.load_facts(root)
    source = next(s for s in loaded.files if s.path.stem == "sess-0002")
    assert [r.duplicate for r in source.records] == [True, False, False, False]
    assert walk.tool_uses([r for r in source.records if not r.duplicate]) == {}
    (exact,) = [f for f in facts if f.locator.file == source.name
                and f.dims.get("cause") in schema.EXACT_CAUSES]
    assert (exact.dims["tool"], exact.dims["head"], exact.metrics[fx.DELTA]) == (
        "Bash", "Bash:pytest", fx.EXACT_FIRST_DELTA)


def test_split_message_id_merges_every_additive_metric_by_max(tmp_path):
    first = fx.assistant("uuid-0001", "msg-0001", fx.usage(1000, 10))
    second = fx.assistant("uuid-0002", "msg-0001", fx.usage(1000, 40))

    def call_metrics(records, path):
        (call,) = [f for f in _one_window(tmp_path / path, records) if f.kind == CALL]
        return call.metrics

    alone = [call_metrics([first], "a"), call_metrics([second], "b")]
    merged = call_metrics([first, second], "merged")
    assert any(alone[0][m] != alone[1][m] for m in ADDITIVE_CALL_METRICS)
    for name in ADDITIVE_CALL_METRICS:
        assert merged[name] == max(alone[0][name], alone[1][name])


def test_exact_interval_names_its_contributor_line(tmp_path):
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": fx.window_records()})
    facts = fx.load_facts(root)[1]
    exact = [f for f in facts if f.dims.get("cause") == schema.TOOL_RESULT]
    first = exact[0]
    assert first.metrics[fx.DELTA] == fx.EXACT_FIRST_DELTA
    assert (first.dims["tool"], first.dims["head"]) == ("Bash", "Bash:pytest")
    assert first.locator.file == "proj-a/sess-0001.jsonl"  # relative to the root
    with open(root / first.locator.file, encoding="utf-8") as handle:
        line = handle.read().splitlines()[first.locator.line - 1]
    assert json.loads(line)["uuid"] == first.locator.uuid == "uuid-0002"


def test_ambiguous_carries_candidate_locators_as_evidence(tmp_path):
    facts = _one_window(tmp_path)
    by_reason = {f.dims["reason"]: f for f in facts if f.dims.get("reason")}
    multi = by_reason[schema.MULTI_CONTRIBUTOR]
    assert [(c.line, c.uuid) for c in multi.evidence["candidates"]] == [
        (4, "uuid-0004"), (5, "uuid-0005")]
    assert "candidates" not in multi.dims
    empty = by_reason[schema.NO_CONTRIBUTOR]
    assert empty.evidence["candidates"] == []
    assert empty.metrics[fx.DELTA] == 12


def _exact(facts):
    return [f for f in facts if f.dims.get("cause") in schema.EXACT_CAUSES]


def test_a_result_interleaved_with_a_split_call_is_a_second_contributor(tmp_path):
    """Parallel tool use: constituent, result, constituent, result, next call.
    Both results sit between the call's first constituent and the next call."""
    records = [
        fx.assistant("uuid-0001", "msg-0001", fx.usage(1000, 50),
                     [fx.tool_use("toolu_0001", "Read", file_path="/x/a.py")]),
        fx.tool_result("uuid-0002", "toolu_0001"),
        fx.assistant("uuid-0003", "msg-0001", fx.usage(1000, 50),
                     [fx.tool_use("toolu_0002", "Write", file_path="/x/b.py")]),
        fx.tool_result("uuid-0004", "toolu_0002"),
        fx.assistant("uuid-0005", "msg-0002", fx.usage(1300, 0)),
    ]
    facts = _one_window(tmp_path / "interleaved", records)
    (closing,) = [f for f in facts if f.dims.get("reason")]
    assert closing.dims["reason"] == schema.MULTI_CONTRIBUTOR
    assert [c.uuid for c in closing.evidence["candidates"]] == ["uuid-0002", "uuid-0004"]
    assert closing.metrics[fx.DELTA] == fx.EXACT_FIRST_DELTA
    assert not _exact(facts)
    # Vacuity guard: the same call with one constituent and one result is exact.
    (exact,) = _exact(_one_window(tmp_path / "plain", records[:2] + records[4:]))
    assert (exact.dims["head"], exact.metrics[fx.DELTA]) == ("Read:py", fx.EXACT_FIRST_DELTA)


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
