"""The walk: chain integrity, identity, max-merge, the exact case."""
import json

import pytest

import fixtures as fx
import fixtures_edge as fe
from sa import query, reconciliation, schema, walk
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
    causes = {f.dims[schema.CAUSE_DIM] for f in facts if f.kind == INCREMENT}
    reasons = {f.dims[schema.REASON_DIM] for f in facts if f.dims.get(schema.REASON_DIM)}
    # One window inherits nothing: ``inherited`` needs a parent (tests/test_windows.py).
    assert causes == set(schema.CAUSES) - {schema.INHERITED}, "fixture must exercise every other cause"
    assert reasons == set(schema.REASONS), "fixture must exercise every reason"
    booked, final = _chain(facts)
    assert booked == final == {next(iter(final)): fx.FINAL_OCCUPANCY}
    r = reconciliation.reconcile(facts)
    assert r.holds
    assert r.intervals == sum(f.kind == CALL for f in facts) - 1 == fx.INTERVALS
    assert (r.exact, r.ambiguous, r.shrink) == (fx.EXACT, fx.AMBIGUOUS, fx.SHRINK)


def test_reconciliation_fails_on_a_missing_or_extra_increment(tmp_path):
    facts = _one_window(tmp_path)
    without_shrink = [f for f in facts if f.dims.get(schema.CAUSE_DIM) != schema.SHRINK]
    assert len(without_shrink) < len(facts)
    assert not reconciliation.reconcile(without_shrink).holds
    exact = next(f for f in facts if f.dims.get(schema.CAUSE_DIM) in schema.EXACT_CAUSES)
    zero = exact._replace(metrics={fx.DELTA: 0})  # mass unchanged, interval count off by one
    doubled = facts + [zero]
    assert reconciliation.reconcile(doubled).booked == reconciliation.reconcile(facts).booked
    assert not reconciliation.reconcile(doubled).holds


def test_a_call_split_across_files_is_one_call_owned_by_the_earlier_file(tmp_path):
    """D-MESSAGE-ID-DEDUP: a fork re-mints its parent's last call under a new
    uuid. The parent owns it, the fork's copy is a duplicate the population
    line counts, its usage still max-merges into the one call, and spend is
    counted once; the same fork under its own id is a second call."""
    root, fork_ref, parent, copy = fe.remint_corpus(tmp_path / "shared")
    loaded, facts = fx.load_facts(root)
    assert {s.path.stem: [r.duplicate for r in s.records] for s in loaded.files} == {
        "sess-0001": [False], "agent-fake1": [False, True]}
    assert loaded.duplicate_records == 1
    (call,) = [f for f in facts if f.kind == CALL]
    assert call.locator.file == "proj-a/sess-0001.jsonl"
    assert reconciliation.reconcile(facts).holds
    code, out, err = fx.run_cli("spend", "--root", str(root))
    assert code == 0, err
    assert ("read: 2 files from the last 7d (default) under %s; 0 lines skipped,"
            " 1 duplicate\nin view: 1 window*, 1 call\n" % root) in out
    # Merged over both files' constituents: the same metrics as the split within one file.
    (within,) = [f for f in _one_window(tmp_path / "within", [parent, copy]) if f.kind == CALL]
    assert call.metrics == within.metrics
    # Vacuity guards: under its own id the copy is a second call, billed again,
    # and the two differ on some metric, so the merge above did something.
    own = fx.corpus(tmp_path / "own", {
        "proj-a/sess-0001.jsonl": fx.stamped([parent], 0),
        "proj-a/sess-0001/subagents/agent-fake1.jsonl":
            [fork_ref] + fx.stamped([dict(copy, message={**copy["message"], "id": "fork-msg-0001"})], 1)})
    own_loaded, own_facts = fx.load_facts(own)
    two = [f for f in own_facts if f.kind == CALL]
    assert (own_loaded.duplicate_records, len(two)) == (0, 2)
    assert any(two[0].metrics[m] != two[1].metrics[m] for m in ADDITIVE_CALL_METRICS)
    assert sum(f.metrics[schema.SPEND] for f in two) == 2 * call.metrics[schema.SPEND]


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
    exact = [f for f in facts if f.dims.get(schema.CAUSE_DIM) == schema.TOOL_RESULT]
    first = exact[0]
    assert first.metrics[fx.DELTA] == fx.EXACT_FIRST_DELTA
    assert (first.dims[schema.TOOL_DIM], first.dims[schema.COMMAND_DIM]) == ("Bash", "Bash:pytest")
    assert first.locator.file == "proj-a/sess-0001.jsonl"  # relative to the root
    with open(root / first.locator.file, encoding="utf-8") as handle:
        line = handle.read().splitlines()[first.locator.line - 1]
    assert json.loads(line)["uuid"] == first.locator.uuid == "uuid-0002"


def test_ambiguous_carries_candidate_locators_as_evidence(tmp_path):
    facts = _one_window(tmp_path)
    by_reason = {f.dims[schema.REASON_DIM]: f for f in facts if f.dims.get(schema.REASON_DIM)}
    multi = by_reason[schema.SEVERAL]
    assert [(c.locator.line, c.locator.uuid, c.dims) for c in multi.evidence[schema.CANDIDATES]] == [
        (4, "uuid-0004", {schema.CAUSE_DIM: schema.USER_TEXT}),
        (5, "uuid-0005", {schema.CAUSE_DIM: schema.TOOL_RESULT, schema.TOOL_DIM: "Read",
                          schema.COMMAND_DIM: "Read:py"})]
    assert schema.CANDIDATES not in multi.dims
    assert schema.TOOL_DIM not in multi.dims  # a user_text candidate shares no tool
    empty = by_reason[schema.UNEXPLAINED]
    assert empty.evidence[schema.CANDIDATES] == []
    assert empty.metrics[fx.DELTA] == 12


def _exact(facts):
    return [f for f in facts if f.dims.get(schema.CAUSE_DIM) in schema.EXACT_CAUSES]


def test_a_result_interleaved_with_a_split_call_is_a_second_contributor(tmp_path):
    """Both results of ``fe.interleaved_records`` sit between the call's
    first constituent and the next call."""
    records = fe.interleaved_records()
    facts = _one_window(tmp_path / "interleaved", records)
    (closing,) = [f for f in facts if f.dims.get(schema.REASON_DIM)]
    assert closing.dims[schema.REASON_DIM] == schema.SEVERAL
    assert [c.locator.uuid for c in closing.evidence[schema.CANDIDATES]] == ["uuid-0002", "uuid-0004"]
    assert closing.metrics[fx.DELTA] == fx.EXACT_FIRST_DELTA
    assert not _exact(facts)
    # Vacuity guard: the same call with one constituent and one result is exact.
    (exact,) = _exact(_one_window(tmp_path / "plain", records[:2] + records[4:]))
    assert (exact.dims[schema.COMMAND_DIM], exact.metrics[fx.DELTA]) == ("Read:py", fx.EXACT_FIRST_DELTA)


def test_usage_less_synthetic_record_is_not_a_call(tmp_path):
    records = fx.window_records()
    zero = dict.fromkeys(("input_tokens", "output_tokens", "cache_read_input_tokens",
                          "cache_creation_input_tokens"), 0)
    synthetic = fx.assistant("uuid-9999", "msg-9999", zero, model="<synthetic>")
    records.insert(1, synthetic)
    plain = _one_window(tmp_path / "plain")
    with_synthetic = _one_window(tmp_path / "synthetic", records)
    strip = lambda facts: [(f.kind, f.dims[schema.CAUSE_DIM] if f.kind == INCREMENT else None,
                            f.metrics) for f in facts]
    assert strip(plain) == strip(with_synthetic)


def test_window_dimensions_come_from_the_live_records(tmp_path):
    """A continuation whose replayed prefix is owned by the original and
    carries the original's sessionId: its facts name the session its live
    records carry, not the first record's."""
    original = fx.stamped(fx.window_records() + [fx.user_text("uuid-0099")], 0)  # runs longest
    continuation = fx.stamped(fx.window_records()[:5], 0) + fx.stamped(
        fx.window_records("c-", session="sess-0002")[5:], 5)
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": original,
                                "proj-a/sess-0002.jsonl": continuation})
    loaded, facts = fx.load_facts(root)
    source = next(s for s in loaded.files if s.path.stem == "sess-0002")
    assert [r.duplicate for r in source.records] == [True] * 5 + [False] * 9
    assert walk.first_value(source.records, "sessionId") == fx.SESSION  # the first record's: replayed
    assert {f.dims[schema.SESSION_DIM] for f in facts if f.locator.file == source.name} == {"sess-0002"}


def test_fork_context_ref_is_evidence_on_the_window_head(tmp_path):
    records = [{"type": "fork-context-ref", "parentSessionId": "sess-0000",
                "parentLastUuid": "uuid-0000", "agentId": "agent-fake1"}]
    records += fx.window_records()
    facts = _one_window(tmp_path, records)
    head = [f for f in facts if f.dims.get(schema.CAUSE_DIM) == schema.STARTING_CONTEXT]
    assert len(head) == 1
    assert head[0].evidence == {schema.PARENT_SESSION: "sess-0000",
                                schema.PARENT_LAST_UUID: "uuid-0000"}
    assert head[0].dims[schema.SUBAGENT_DIM] == "agent-fake1"
    (main_head,) = [f for f in _one_window(tmp_path / "main")
                    if f.dims.get(schema.CAUSE_DIM) == schema.STARTING_CONTEXT]
    assert schema.SUBAGENT_DIM not in main_head.dims  # a main window is no agent (D-AGENT-DIM)


READ_A = fx.tool_use("toolu_0001", "Read", file_path="/x/a.py")
READ_B = fx.tool_use("toolu_0002", "Read", file_path="/x/b.py")
READ_MD = fx.tool_use("toolu_0003", "Read", file_path="/x/c.md")
BASH = fx.tool_use("toolu_0004", "Bash", command="ls")
WRITE_A = fx.tool_use("toolu_0005", "Write", file_path="/x/Makefile")
WRITE_B = fx.tool_use("toolu_0006", "Write", file_path="/x/README")


def _results(*tool_use_ids):
    return [fx.tool_result("uuid-%04d" % (2 + n), i) for n, i in enumerate(tool_use_ids)]


def _after_one_call(tmp_path, uses, between):
    """Facts of a window whose first call issues ``uses`` and whose next
    interval holds the records ``between``."""
    records = ([fx.assistant("uuid-0001", "msg-0001", fx.usage(1000, 50), uses)] + between
               + [fx.assistant("uuid-0010", "msg-0002", fx.usage(1300, 0))])
    facts = _one_window(tmp_path, records)
    assert reconciliation.reconcile(facts).holds
    return facts


def _ambiguous(facts):
    """The one several increment, carrying the whole remainder."""
    (closing,) = [f for f in facts if f.dims.get(schema.REASON_DIM)]
    assert closing.dims[schema.REASON_DIM] == schema.SEVERAL
    assert closing.metrics[fx.DELTA] == fx.EXACT_FIRST_DELTA
    assert not _exact(facts)
    return closing


def test_a_batched_result_record_is_one_contributor_per_block(tmp_path):
    batched = fx.tool_result("uuid-0002", "toolu_0001", "toolu_0004")
    closing = _ambiguous(_after_one_call(tmp_path / "batched", [READ_A, BASH], [batched]))
    assert [(c.locator.uuid, c.dims[schema.TOOL_DIM]) for c in closing.evidence[schema.CANDIDATES]] == [
        ("uuid-0002", "Read"), ("uuid-0002", "Bash")]
    # Vacuity guard: the same record with one block is the exact contributor.
    (exact,) = _exact(_after_one_call(tmp_path / "single", [READ_A], _results("toolu_0001")))
    assert (exact.locator.uuid, exact.dims[schema.TOOL_DIM]) == ("uuid-0002", "Read")


def test_ambiguous_carries_the_tool_and_head_every_candidate_shares(tmp_path):
    """D-AMBIGUOUS-TOOL: cause, reason, mass and candidates are unchanged;
    tool is set only when every candidate is a result of one tool, head only
    when they also agree on it, with ``other`` a value like any."""
    def closing(name, uses, between):
        facts = _after_one_call(tmp_path / name, uses, between)
        return _ambiguous(facts), query.group(facts, schema.TOOL_DIM, fx.DELTA).rows

    same_tool, rows = closing("same-tool", [READ_A, READ_MD], _results("toolu_0001", "toolu_0003"))
    assert (same_tool.dims[schema.TOOL_DIM], schema.COMMAND_DIM in same_tool.dims) == ("Read", False)
    assert [(r.value, r.mass) for r in rows if r.kind == query.REGULAR] == [("Read", 250)]
    same_head, _ = closing("same-head", [READ_A, READ_B], _results("toolu_0001", "toolu_0002"))
    assert (same_head.dims[schema.TOOL_DIM], same_head.dims[schema.COMMAND_DIM]) == ("Read", "Read:py")
    other, _ = closing("other", [WRITE_A, WRITE_B], _results("toolu_0005", "toolu_0006"))
    assert other.dims[schema.COMMAND_DIM] == "Write:other"
    mixed, rows = closing("mixed", [READ_A, BASH], _results("toolu_0001", "toolu_0004"))
    with_text, _ = closing("text", [READ_A], _results("toolu_0001") + [fx.user_text("uuid-0009")])
    for f in (mixed, with_text):
        assert schema.TOOL_DIM not in f.dims and schema.COMMAND_DIM not in f.dims
        assert len(f.evidence[schema.CANDIDATES]) == 2
    (residual,) = [r for r in rows if r.kind == query.RESIDUAL]
    assert residual.mass == 1000 + 50 + 250  # starting_context + replies + the mixed interval
    assert not [r for r in rows if r.kind == query.REGULAR]
