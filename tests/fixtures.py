"""Synthetic transcript records and files. Every id is obviously fake.

``window_records`` is the shared fixture: one window whose six intervals
exercise every cause and every ambiguity reason of the walk, and whose
arithmetic is written out, so tests assert exact figures.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from sa import corpus as corpus_module, glossary, schema, walk
from screen import (AVERAGE, also, average, checks, closing, headline, hint, joined, key, listed, pointer_v,  # noqa: F401
                    sections, verbose, worked)

SESSION = "sess-0001"
FORK_PARENT = "sess-0000"
REPO = Path(__file__).resolve().parents[1]


def window_value(name, line=1):
    """The ``window`` value of the window at ``name:line``."""
    return schema.window_value(schema.WindowKey(name, line))


def metric_named(**spec):
    """The one declared metric whose spec has these fields, e.g. the only
    one increments carry; fails unless there is exactly one."""
    names = [name for name, s in schema.METRICS.items()
             if all(getattr(s, field) == value for field, value in spec.items())]
    assert len(names) == 1, (spec, names)
    return names[0]


DELTA = metric_named(carrier=schema.INCREMENT, aggregation=schema.ADDITIVE)
HELD = metric_named(aggregation=schema.PER_CALL)
PEAK = metric_named(aggregation=schema.PEAK)


def unit(metric):
    return schema.metric(metric).unit


def count_column(metric):
    """The count column's name: the carrier kind's."""
    return schema.PLURAL[schema.metric(metric).carrier]


def printed(metric):
    """The metric as the mass column and the total name it."""
    return glossary.printed(metric)


def total_line(metric):
    """The prefix of the headline's total line: a per-call metric's is the average's."""
    if schema.metric(metric).aggregation == schema.PER_CALL:
        return AVERAGE
    return "%s: " % glossary.marked(metric)


def usage(context, output, cache_write_1h=0, cache_write_5m=0):
    """A usage dict whose occupancy (input + cache_read + cache_creation)
    is exactly ``context``."""
    write = cache_write_1h + cache_write_5m
    return {"input_tokens": 4, "cache_read_input_tokens": context - 4 - write,
            "cache_creation_input_tokens": write, "output_tokens": output,
            "cache_creation": {"ephemeral_1h_input_tokens": cache_write_1h,
                               "ephemeral_5m_input_tokens": cache_write_5m}}


def assistant(uuid, message_id, use, blocks=(), session=SESSION, model="fake-model"):
    return {"type": "assistant", "uuid": uuid, "sessionId": session,
            "message": {"id": message_id, "role": "assistant", "model": model,
                        "content": list(blocks), "usage": use}}


def tool_use(tool_use_id, name, **tool_input):
    return {"type": "tool_use", "id": tool_use_id, "name": name, "input": tool_input}


def tool_result(uuid, *tool_use_ids, session=SESSION):
    """One user record; several ids make a record that batches its results."""
    return {"type": "user", "uuid": uuid, "sessionId": session,
            "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": i, "content": "ok"} for i in tool_use_ids]}}


def user_text(uuid, text="hello", session=SESSION):
    return {"type": "user", "uuid": uuid, "sessionId": session,
            "message": {"role": "user", "content": text}}


def attachment(uuid):
    return {"type": "attachment", "uuid": uuid,
            "attachment": {"type": "total_tokens_reminder"}}


def stamped(records, start):
    """Copies carrying consecutive ISO timestamps from minute ``start``: a
    replayed prefix stamped from the same start repeats its original stamps."""
    return [dict(record, timestamp="2026-01-01T%02d:%02d:00Z" % divmod(start + n, 60))
            for n, record in enumerate(records)]


# Occupancy, output and the increments each interval books:
#   head        1000                         -> starting_context 1000
#   1 result    1000 -> 1300, out_prev 50    -> replies 50, tool_result 250
#   2 contrib.  1300 -> 1500, out_prev 20    -> replies 20, ambiguous 180
#   1 result    1500 -> 1400, out_prev 10    -> shrink -100
#   1 result    1400 -> 1410, out_prev 30    -> ambiguous 10 (negative remainder)
#   1 text      1410 -> 1500, out_prev 5     -> replies 5, user_text 85
#   attachment  1500 -> 1520, out_prev 8     -> replies 8, ambiguous 12 (no contributor)
# Sum 1000+50+250+20+180-100+10+5+85+8+12 = 1520 = final occupancy.
FINAL_OCCUPANCY = 1520
EXACT_FIRST_DELTA = 250
INTERVALS = 6
EXACT, AMBIGUOUS, SHRINK = 2, 3, 1


def window_records(prefix="", session=SESSION, base=0):
    """One window. ``prefix`` renumbers every uuid and message id so a copy
    reads as a sibling fork (new ids, same text) rather than a replay;
    ``base`` lifts every call's context."""
    u = lambda n: "%suuid-%04d" % (prefix, n)
    m = lambda n: "%smsg-%04d" % (prefix, n)
    use = lambda context, output: usage(base + context, output)
    return [
        assistant(u(1), m(1), use(1000, 50),
                  [tool_use("toolu_0001", "Bash", command="pytest -q")], session),
        tool_result(u(2), "toolu_0001", session=session),
        assistant(u(3), m(2), use(1300, 20),
                  [tool_use("toolu_0002", "Read", file_path="/x/a.py")], session),
        user_text(u(4), "and also", session),
        tool_result(u(5), "toolu_0002", session=session),
        assistant(u(6), m(3), use(1500, 10),
                  [tool_use("toolu_0003", "Read", file_path="/x/b.md")], session),
        tool_result(u(7), "toolu_0003", session=session),
        assistant(u(8), m(4), use(1400, 30),
                  [tool_use("toolu_0004", "Read", file_path="/x/c.md")], session),
        tool_result(u(9), "toolu_0004", session=session),
        assistant(u(10), m(5), use(1410, 5), [], session),
        user_text(u(11), "next", session),
        assistant(u(12), m(6), use(1500, 8), [], session),
        attachment(u(13)),
        assistant(u(14), m(7), use(1520, 0), [], session),
    ]


def write_jsonl(path, lines):
    """Write records (dicts) and raw lines (strings) as one file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for line in lines:
            handle.write((line if isinstance(line, str) else json.dumps(line)) + "\n")
    return path


def corpus(tmp_path, files):
    """``files``: ``{relative path: records}`` under a fresh root."""
    root = Path(tmp_path) / "projects"
    for name, lines in files.items():
        write_jsonl(root / name, lines)
    return root


def load_facts(root, keep=None):
    loaded = corpus_module.load(root, keep)
    return loaded, walk.forest(loaded)


def cli_corpus(tmp_path, projects=("proj-a", "proj-b")):
    """Two projects, three windows: a main window, a forked subagent (same
    text, new ids; its ref names FORK_PARENT, never read), another
    project's window peaking 200K+, a file with no call. ``projects``
    names the two directories."""
    fork = {"type": "fork-context-ref", "parentSessionId": FORK_PARENT,
            "parentLastUuid": "uuid-0000", "agentId": "agent-fake1"}
    a, b = projects
    return corpus(tmp_path, {
        a + "/sess-0001.jsonl": window_records(),
        a + "/sess-0001/subagents/agent-fake1.jsonl":
            [fork] + window_records("fork-", session="sess-0001"),
        b + "/sess-0002.jsonl": window_records("b-", "sess-0002", 250000),
        b + "/empty.jsonl": [user_text("uuid-9001", session="sess-0003")],
    })


def run_cli(*args):
    """``python3 -m sa <args>``: (exit status, stdout, stderr)."""
    done = subprocess.run([sys.executable, "-m", "sa"] + list(args), cwd=str(REPO),
                          capture_output=True, text=True)
    return done.returncode, done.stdout, done.stderr


LEAF = re.compile(r"\s+(-?[\d,-]+\s+){1,3}:\d+(\s|$)")  # a by change/call row: its figures, then :line


def marker(uuid):
    """A compaction marker."""
    return {"type": "system", "subtype": "compact_boundary", "uuid": uuid,
            "compactMetadata": {"trigger": "auto"}}


# The window corpus: six windows in five files (D-CONTEXT-WINDOW).
#   P  main, compacted mid-file:  window 1 head 1000 -> 1600 (A3, the branch
#      call, at 1500); marker; window 2 head 400 -> 500
#   F  fork of P (a subagent replaying P through A3, A3 re-minted):
#      inherited 1500, head 150, -> 1700
#   R  replayed main (a resume of P through A2's result): inherited 1300,
#      head 100, -> 1450
#   E  main whose marker ends its file: 150800 -> 150900, then the marker
#   S  plain subagent: 60600 -> 60650 (E, S: two more peak bands)
W_PARENT, W_FORK, W_REPLAY = "proj-w/sess-0101.jsonl", "proj-w/sess-0101/subagents/agent-fork1.jsonl", \
    "proj-w/sess-0102.jsonl"
W_ENDED, W_SUB = "proj-w/sess-0103.jsonl", "proj-w/sess-0103/subagents/agent-plain.jsonl"
W_FINALS = {(W_PARENT, 1): 1600, (W_PARENT, 8): 500, (W_FORK, 1): 1700, (W_REPLAY, 1): 1450,
            (W_ENDED, 1): 150900, (W_SUB, 1): 60650}
W_INHERITED = {W_FORK: 1500, W_REPLAY: 1300}
W_STARTS = {(W_PARENT, 1): schema.SESSION_START, (W_PARENT, 8): schema.COMPACTION,
            (W_FORK, 1): schema.FORK, (W_REPLAY, 1): schema.REPLAYED,
            (W_ENDED, 1): schema.SESSION_START, (W_SUB, 1): schema.SUBAGENT_START}
W_DUPLICATES = 6 + 1 + 4  # F's replayed prefix and re-mint, R's prefix


def _with(record, **extra):
    return dict(record, **extra)


def window_parent(session="sess-0101"):
    return stamped([
        assistant("w-uuid-0001", "w-msg-0001", usage(1000, 50),
                  [tool_use("toolu_w001", "Bash", command="pytest -q")], session),
        tool_result("w-uuid-0002", "toolu_w001", session=session),
        assistant("w-uuid-0003", "w-msg-0002", usage(1300, 20),
                  [tool_use("toolu_w002", "Read", file_path="/x/a.py")], session),
        tool_result("w-uuid-0004", "toolu_w002", session=session),
        assistant("w-uuid-0005", "w-msg-0003", usage(1500, 10),
                  [tool_use("toolu_w003", "Bash", command="git status")], session),
        tool_result("w-uuid-0006", "toolu_w003", session=session),
        assistant("w-uuid-0007", "w-msg-0004", usage(1600, 0), [], session),
        marker("w-uuid-0008"),
        _with(user_text("w-uuid-0009", "summary", session), isCompactSummary=True),
        assistant("w-uuid-0010", "w-msg-0005", usage(400, 10),
                  [tool_use("toolu_w004", "Read", file_path="/x/b.md")], session),
        tool_result("w-uuid-0011", "toolu_w004", session=session),
        assistant("w-uuid-0012", "w-msg-0006", usage(500, 0), [], session),
    ], 0)


def window_corpus(tmp_path):
    """The window corpus above; returns the root."""
    parent = window_parent()
    s = "sess-0101"
    fork = parent[:6] + [_with(r, agentId="agent-fork1") for r in stamped([
        assistant("fork-uuid-0005", "w-msg-0003", usage(1500, 10), [], s),
        assistant("fork-uuid-0001", "fork-msg-0001", usage(1650, 30),
                  [tool_use("toolu_f001", "Bash", command="ls")], s),
        tool_result("fork-uuid-0002", "toolu_f001", session=s),
        assistant("fork-uuid-0003", "fork-msg-0002", usage(1700, 0), [], s)], 6)]
    replay = parent[:4] + stamped([
        assistant("r-uuid-0001", "r-msg-0001", usage(1400, 10), [], "sess-0102"),
        user_text("r-uuid-0002", "again", "sess-0102"),
        assistant("r-uuid-0003", "r-msg-0002", usage(1450, 0), [], "sess-0102")], 4)
    ended = stamped([
        assistant("e-uuid-0001", "e-msg-0001", usage(150800, 20), [], "sess-0103"),
        user_text("e-uuid-0002", "more", "sess-0103"),
        assistant("e-uuid-0003", "e-msg-0002", usage(150900, 0), [], "sess-0103"),
        marker("e-uuid-0004")], 100)
    sub = [_with(r, agentId="agent-plain") for r in stamped([
        assistant("s-uuid-0001", "s-msg-0001", usage(60600, 5), [], "sess-0103"),
        user_text("s-uuid-0002", "task", "sess-0103"),
        assistant("s-uuid-0003", "s-msg-0002", usage(60650, 0), [], "sess-0103")], 110)]
    return corpus(tmp_path, {W_PARENT: parent, W_FORK: fork, W_REPLAY: replay,
                             W_ENDED: ended, W_SUB: sub})


def every_corpus(tmp_path):
    """``cli_corpus`` and ``window_corpus`` under one root: every declared
    cause, reason and start is carried by some fact."""
    cli_corpus(tmp_path)
    return window_corpus(tmp_path)


