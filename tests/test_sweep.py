"""The sweep's counts over the fixtures: each count that is zero on one
corpus is non-zero on another, so the figure a docstring cites is read by
code that has been seen to count."""
import fixtures as fx
from sa import schema, sweep, sweep_mean


def test_counts_over_the_cli_corpus(tmp_path):
    loaded, facts = fx.load_facts(fx.cli_corpus(tmp_path))
    assert sweep.batched_results(loaded) == (0, 12)  # four results in each of three windows
    assert sweep.inside_spans(loaded) == (0, 0, 21)
    assert sweep.shared(facts) == [(3, 3 * 180), (0, 0), (0, 0)]  # user text shares no tool
    assert sweep.reminted(loaded) == (0, 0)
    assert sweep.key_disagreements(loaded) == (0, 4)
    assert sweep.cross_file_parents(loaded) == (0, 0)
    lines = sweep.report(loaded)
    assert lines[0] == "4 files, 3 windows, 21 calls, 18 intervals"
    assert lines[12:] == sweep_mean.report(loaded, facts, sweep.cut(loaded))
    assert "holds in 3 of 3 windows" in lines[12]
    assert sweep.fork_marks(loaded, sweep.cut(loaded)) == (1, 1, 0, 1, 0, 0)  # by its ref, parent absent


def test_each_zero_count_is_non_zero_on_the_corpus_built_for_it(tmp_path):
    loaded, facts = fx.load_facts(fx.remint_corpus(tmp_path / "remint")[0])
    (call,) = [f for f in facts if f.kind == schema.CALL]
    assert sweep.reminted(loaded) == (1, call.metrics[schema.SPEND])
    # The fork's only call is the replay, so its live records carry no sessionId.
    assert sweep.key_disagreements(loaded) == (1, 2)
    loaded, facts = fx.load_facts(fx.batched_corpus(tmp_path / "batched"))
    assert sweep.batched_results(loaded) == (1, 1)
    assert sweep.shared(facts) == [(1, fx.EXACT_FIRST_DELTA), (1, fx.EXACT_FIRST_DELTA), (0, 0)]
    loaded, facts = fx.load_facts(fx.corpus(tmp_path / "interleaved",
                                            {"proj-a/sess-0001.jsonl": fx.interleaved_records()}))
    assert sweep.inside_spans(loaded) == (1, 1, 2)  # the first result sits inside the split call
    assert sweep.shared(facts) == [(1, fx.EXACT_FIRST_DELTA)] * 3
    # A chain of parentUuid links within the file, its first naming a uuid outside it.
    parents = ["uuid-0000"] + ["uuid-%04d" % n for n in range(1, 14)]
    linked = [dict(r, parentUuid=p) for r, p in zip(fx.window_records(), parents)]
    loaded, _ = fx.load_facts(fx.corpus(tmp_path / "linked", {"proj-a/sess-0001.jsonl": linked}))
    assert sweep.cross_file_parents(loaded) == (1, 14)


def test_window_counts_over_the_window_corpus(tmp_path):
    loaded, _ = fx.load_facts(fx.window_corpus(tmp_path))
    cuts = sweep.cut(loaded)
    assert dict(zip(schema.STARTS, sweep.starts(cuts))) == {
        start: list(fx.W_STARTS.values()).count(start) for start in schema.STARTS}
    assert sweep.compacting(loaded) == (1, 2, 0, 0)  # E's marker ends its file
    assert sweep.continuations(loaded) == (0, 5)
    assert sweep.fork_heads(loaded, cuts) == (2, "%.3f" % (1400 / 1300), "%.3f" % (1650 / 1500))
    assert sweep.fork_marks(loaded, cuts) == (1, 0, 0, 0, 1, 1)  # F: unmarked, known by its replay


def test_the_zero_window_counts_are_non_zero_on_a_corpus_built_for_them(tmp_path):
    """A file that replays its parent after a live record of its own, and a
    compaction's api-request record."""
    parent = fx.stamped(fx.window_records(), 0)
    own = fx.stamped([fx.assistant("c-uuid-0001", "c-msg-0001", fx.usage(500, 0))], 30)
    request = {"type": "api-request", "querySource": "compact"}
    loaded, _ = fx.load_facts(fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": parent,
                                                   "proj-a/sess-0002.jsonl": own + parent[:1] + [request]}))
    assert sweep.continuations(loaded) == (1, 2)
    assert sweep.compacting(loaded)[2:] == (1, 1)
    fork = {"type": "api-request", "querySource": "agent:builtin:fork"}  # a fork's request, its parent absent
    sub = [dict(r, agentId="agent-fake1") for r in fx.window_records("s-")] + [fork]
    loaded, _ = fx.load_facts(fx.corpus(tmp_path / "fork", {"proj-a/sess-0001/subagents/agent-fake1.jsonl": sub}))
    assert sweep.fork_marks(loaded, sweep.cut(loaded)) == (1, 1, 1, 0, 0, 0)
