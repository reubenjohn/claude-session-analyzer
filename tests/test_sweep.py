"""The sweep's counts over the fixtures: each count that is zero on one
corpus is non-zero on another, so the figure a docstring cites is read by
code that has been seen to count."""
import fixtures as fx
from sa import schema, sweep


def _batched_corpus(tmp_path):
    """One call with two Read tool_uses whose results come back batched in
    one record: two contributors sharing the tool, not the head."""
    return fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": [
        fx.assistant("uuid-0001", "msg-0001", fx.usage(1000, 50),
                     [fx.tool_use("toolu_0001", "Read", file_path="/x/a.py"),
                      fx.tool_use("toolu_0002", "Read", file_path="/x/b.md")]),
        fx.tool_result("uuid-0002", "toolu_0001", "toolu_0002"),
        fx.assistant("uuid-0003", "msg-0002", fx.usage(1300, 0)),
    ]})


def test_counts_over_the_cli_corpus(tmp_path):
    loaded, facts = fx.load_facts(fx.cli_corpus(tmp_path))
    assert sweep.batched_results(loaded) == (0, 12)  # four results in each of three windows
    assert sweep.inside_spans(loaded) == (0, 0, 21)
    assert sweep.shared(facts) == [(3, 3 * 180), (0, 0), (0, 0)]  # user text shares no tool
    assert sweep.reminted(loaded) == (0, 0)
    assert sweep.key_disagreements(loaded) == (0, 4)
    assert sweep.cross_file_parents(loaded) == (0, 0)
    lines = sweep.report(loaded)
    assert lines[0] == "4 files, 3 windows, 21 calls, 18 intervals" and len(lines) == 7


def test_each_zero_count_is_non_zero_on_the_corpus_built_for_it(tmp_path):
    loaded, facts = fx.load_facts(fx.remint_corpus(tmp_path / "remint")[0])
    (call,) = [f for f in facts if f.kind == schema.CALL]
    assert sweep.reminted(loaded) == (1, call.metrics[schema.SPEND])
    # The fork's only call is the replay, so its live records carry no sessionId.
    assert sweep.key_disagreements(loaded) == (1, 2)
    loaded, facts = fx.load_facts(_batched_corpus(tmp_path / "batched"))
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
