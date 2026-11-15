"""Reading the forest: line numbers, skipping, project naming, filters; and
ownership: which copy of a replayed record counts, by uuid and by message.id."""
import pytest

import fixtures as fx
from sa import corpus, query, schema, walk


def test_physical_line_numbers_survive_skipped_lines(tmp_path):
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": [
        fx.user_text("uuid-0001"),
        "{not json",
        "",
        "[1, 2]",
        fx.user_text("uuid-0002"),
    ]})
    loaded = corpus.load(root)
    (source,) = loaded.files
    assert [(r.line, r.data["uuid"]) for r in source.records] == [
        (1, "uuid-0001"), (5, "uuid-0002")]
    assert loaded.skipped_lines == 3
    assert loaded.duplicate_records == 0


def test_project_is_the_first_path_component_for_agents_too(tmp_path):
    root = fx.corpus(tmp_path, {
        "proj-b/sess-0001.jsonl": [fx.user_text("uuid-0001")],
        "proj-b/sess-0001/subagents/agent-fake1.jsonl": [fx.user_text("uuid-0002")],
        "proj-a/sess-0002.jsonl": [fx.user_text("uuid-0003")],
    })
    loaded = corpus.load(root)
    assert [(s.project, s.path.name) for s in loaded.files] == [
        ("proj-a", "sess-0002.jsonl"), ("proj-b", "sess-0001.jsonl"),
        ("proj-b", "agent-fake1.jsonl")]
    assert (loaded.root, loaded.since_days) == (root, None)
    assert corpus.load(root, since_days=0).files == []  # modified within no time at all
    assert [s.project for s in corpus.load(root, since_days=1).files] == ["proj-a", "proj-b", "proj-b"]


def test_uuid_less_records_are_kept_and_never_deduped(tmp_path):
    bookkeeping = {"type": "mode", "mode": "default"}
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": [bookkeeping, bookkeeping]})
    loaded = corpus.load(root)
    assert len(loaded.files[0].records) == 2
    assert loaded.duplicate_records == 0


def test_a_file_without_timestamps_owns_nothing_a_stamped_copy_carries(tmp_path):
    """Whatever its filename, the unstamped copy of a window sorts after the
    stamped one and every shared record is marked duplicate in it."""
    for names in (("sess-0001", "sess-0002"), ("sess-0002", "sess-0001")):
        root = fx.corpus(tmp_path / names[0], {
            "proj-a/%s.jsonl" % names[0]: fx.window_records(),
            "proj-a/%s.jsonl" % names[1]: fx.stamped(fx.window_records(), 0)})
        loaded = corpus.load(root)
        assert [s.path.stem for s in loaded.files] == [names[1], names[0]]
        assert [all(r.duplicate for r in s.records) for s in loaded.files] == [False, True]
    # Vacuity guard: two unstamped copies fall back to path order.
    root = fx.corpus(tmp_path / "unstamped", {"proj-a/sess-0002.jsonl": fx.window_records(),
                                              "proj-a/sess-0001.jsonl": fx.window_records()})
    assert [s.path.stem for s in corpus.load(root).files] == ["sess-0001", "sess-0002"]


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
        heads = [f for f in facts if f.dims.get(schema.CAUSE_DIM) in (schema.WINDOW_HEAD, schema.INHERITED)]
        assert sorted(f.metrics[fx.DELTA] for f in heads) == [200, 1000, 1300]  # 1,500 = 1,300 inherited + 200
        results.append(query.reconcile(facts).by_cause)
    assert results[0] == results[1]
    assert sum(results[0].values()) == 2 * fx.FINAL_OCCUPANCY


def test_a_tool_result_keeps_its_tool_when_its_tool_use_was_replayed(tmp_path):
    original = fx.stamped(fx.window_records(), 0)
    branch = fx.stamped(fx.window_records()[:1], 0) + fx.stamped([
        fx.assistant("b-uuid-0002", "b-msg-0001", fx.usage(1000, 50)),  # the branch's own call
        fx.tool_result("b-uuid-0003", "toolu_0001"),  # answers the replayed tool_use
        fx.assistant("b-uuid-0004", "b-msg-0002", fx.usage(1300, 0)),
    ], 1)  # ends before the original does, so the original owns the prefix
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": original,
                                "proj-a/sess-0002.jsonl": branch})
    loaded, facts = fx.load_facts(root)
    source = next(s for s in loaded.files if s.path.stem == "sess-0002")
    assert [r.duplicate for r in source.records] == [True, False, False, False]
    assert walk.tool_uses(source.live) == {}
    (exact,) = [f for f in facts if f.locator.file == source.name
                and f.dims.get(schema.CAUSE_DIM) in schema.EXACT_CAUSES]
    assert (exact.dims[schema.TOOL_DIM], exact.dims[schema.HEAD_DIM], exact.metrics[fx.DELTA]) == (
        "Bash", "Bash:pytest", fx.EXACT_FIRST_DELTA)
