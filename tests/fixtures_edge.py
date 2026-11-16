"""Edge-case corpora built from ``fixtures``' records: a re-minted call,
batched and interleaved tool results."""
from fixtures import SESSION, assistant, corpus, stamped, tool_result, tool_use, usage


def remint_corpus(tmp_path):
    """A parent's last call and a fork's re-mint of it under a new uuid
    (D-MESSAGE-ID-DEDUP): two files, one call. Returns the root, the fork
    reference and the two records."""
    fork_ref = {"type": "fork-context-ref", "parentSessionId": SESSION,
                "parentLastUuid": "uuid-0001", "agentId": "agent-fake1"}
    parent = assistant("uuid-0001", "msg-0001", usage(1000, 50))
    copy = assistant("fork-uuid-0001", "msg-0001", usage(1000, 70))
    root = corpus(tmp_path, {
        "proj-a/sess-0001.jsonl": stamped([parent], 0),
        "proj-a/sess-0001/subagents/agent-fake1.jsonl": [fork_ref] + stamped([copy], 1)})
    return root, fork_ref, parent, copy


def batched_corpus(tmp_path):
    """One call with two Read tool_uses whose results come back batched in
    one record: two contributors sharing the tool, not the head."""
    return corpus(tmp_path, {"proj-a/sess-0001.jsonl": [
        assistant("uuid-0001", "msg-0001", usage(1000, 50),
                  [tool_use("toolu_0001", "Read", file_path="/x/a.py"),
                   tool_use("toolu_0002", "Read", file_path="/x/b.md")]),
        tool_result("uuid-0002", "toolu_0001", "toolu_0002"),
        assistant("uuid-0003", "msg-0002", usage(1300, 0)),
    ]})


def interleaved_records():
    """Parallel tool use: constituent, result, constituent, result, next
    call. Both results sit between the call's first constituent and the
    next call, and they share the tool and the head."""
    return [
        assistant("uuid-0001", "msg-0001", usage(1000, 50),
                  [tool_use("toolu_0001", "Read", file_path="/x/a.py")]),
        tool_result("uuid-0002", "toolu_0001"),
        assistant("uuid-0003", "msg-0001", usage(1000, 50),
                  [tool_use("toolu_0002", "Read", file_path="/x/b.py")]),
        tool_result("uuid-0004", "toolu_0002"),
        assistant("uuid-0005", "msg-0002", usage(1300, 0)),
    ]
