"""A fork that inherited nothing, by reason (D-MISSING-PARENT): its parent
session was never read, or was read without the call it branched from.
Either way its copy counts as its own, and the scope says which."""
import fixtures as fx
from sa import query, render, schema


def _fork(tmp_path, parent):
    """The cli corpus's main window and a fork of it whose ref names
    ``parent`` and a branch uuid no file holds."""
    ref = {"type": "fork-context-ref", "parentSessionId": parent,
           "parentLastUuid": "uuid-0999", "agentId": "agent-fake1"}
    return fx.corpus(tmp_path, {
        "proj-a/sess-0001.jsonl": fx.window_records(),
        "proj-a/sess-0001/subagents/agent-fake1.jsonl": [ref] + fx.window_records("fork-", session=fx.SESSION)})


def _scope(root):
    code, out, err = fx.run_cli("context", "--root", str(root))
    assert code == 0, err
    return fx.sections(out)[0]


def test_a_fork_whose_parent_was_read_but_not_its_branch_call_says_so(tmp_path):
    root = _fork(tmp_path, fx.SESSION)
    facts = fx.load_facts(root)[1]
    assert any(f.dims.get(schema.STARTED_BY_DIM) == schema.FORK for f in facts)  # vacuity guard
    assert query.orphan_forks(facts, facts) == (0, 1)
    assert query.orphan_forks([f for f in facts if schema.SUBAGENT_DIM in f.dims], facts) == (0, 1)  # read, not in view
    found = "1 fork whose %s: %s" % (render.ORPHANED[1][0], render.ORPHAN[0])
    assert _scope(root)[-1].strip() == found and not any(render.ORPHANED[0][0] in l for l in _scope(root))


def test_a_fork_whose_parent_session_was_never_read_is_missing_its_parent(tmp_path):
    root = _fork(tmp_path, fx.FORK_PARENT)
    facts = fx.load_facts(root)[1]
    assert fx.FORK_PARENT not in {f.dims.get(schema.SESSION_DIM) for f in facts}  # truly absent
    assert query.orphan_forks(facts, facts) == (1, 0)
    assert _scope(root)[-1].strip() == "1 fork whose %s: %s" % (render.ORPHANED[0][0], render.ORPHAN[0])
    # its own session's main window read is not its parent: still missing, filtered out of view or not
    assert query.orphan_forks([f for f in facts if schema.SUBAGENT_DIM in f.dims], facts) == (1, 0)
