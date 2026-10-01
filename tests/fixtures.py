"""Synthetic transcript records and files. Every id is obviously fake.

``window_records`` is the shared fixture: one window whose six intervals
exercise every cause and every ambiguity reason of the walk, and whose
arithmetic is written out so a test can assert exact figures rather than
re-derive them.
"""
import json
from pathlib import Path

from sa import corpus as corpus_module, schema, walk

SESSION = "sess-0001"


def metric_named(**spec):
    """The one declared metric whose spec has these fields, e.g. the only
    metric carried by increments; fails if the schema no longer has exactly one."""
    names = [name for name, s in schema.METRICS.items()
             if all(getattr(s, field) == value for field, value in spec.items())]
    assert len(names) == 1, (spec, names)
    return names[0]


DELTA = metric_named(carrier=schema.INCREMENT)
PEAK = metric_named(aggregation=schema.PEAK)


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
#   head        1000                         -> window_head 1000
#   1 result    1000 -> 1300, out_prev 50    -> feed_forward 50, tool_result 250
#   2 contrib.  1300 -> 1500, out_prev 20    -> feed_forward 20, ambiguous 180
#   1 result    1500 -> 1400, out_prev 10    -> shrink -100
#   1 result    1400 -> 1410, out_prev 30    -> ambiguous 10 (negative remainder)
#   1 text      1410 -> 1500, out_prev 5     -> feed_forward 5, user_text 85
#   attachment  1500 -> 1520, out_prev 8     -> feed_forward 8, ambiguous 12 (no contributor)
# Sum 1000+50+250+20+180-100+10+5+85+8+12 = 1520 = final occupancy.
FINAL_OCCUPANCY = 1520
EXACT_FIRST_DELTA = 250
INTERVALS = 6
EXACT, AMBIGUOUS, SHRINK = 2, 3, 1


def window_records(prefix="", session=SESSION):
    """One window. ``prefix`` renumbers every uuid and message id so a copy
    reads as a sibling fork (new ids, same text) rather than a replay."""
    u = lambda n: "%suuid-%04d" % (prefix, n)
    m = lambda n: "%smsg-%04d" % (prefix, n)
    return [
        assistant(u(1), m(1), usage(1000, 50),
                  [tool_use("toolu_0001", "Bash", command="pytest -q")], session),
        tool_result(u(2), "toolu_0001", session=session),
        assistant(u(3), m(2), usage(1300, 20),
                  [tool_use("toolu_0002", "Read", file_path="/x/a.py")], session),
        user_text(u(4), "and also", session),
        tool_result(u(5), "toolu_0002", session=session),
        assistant(u(6), m(3), usage(1500, 10),
                  [tool_use("toolu_0003", "Read", file_path="/x/b.md")], session),
        tool_result(u(7), "toolu_0003", session=session),
        assistant(u(8), m(4), usage(1400, 30),
                  [tool_use("toolu_0004", "Read", file_path="/x/c.md")], session),
        tool_result(u(9), "toolu_0004", session=session),
        assistant(u(10), m(5), usage(1410, 5), [], session),
        user_text(u(11), "next", session),
        assistant(u(12), m(6), usage(1500, 8), [], session),
        attachment(u(13)),
        assistant(u(14), m(7), usage(1520, 0), [], session),
    ]


def write_jsonl(path, lines):
    """Write records (dicts) and raw lines (strings) as one file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for line in lines:
            handle.write((line if isinstance(line, str) else json.dumps(line)) + "\n")
    return path


def corpus(tmp_path, files):
    """``files``: ``{relative path: records}`` under a fresh root; returns the root."""
    root = Path(tmp_path) / "projects"
    for name, lines in files.items():
        write_jsonl(root / name, lines)
    return root


def load_facts(root, keep=None):
    loaded = corpus_module.load(root, keep)
    return loaded, [f for source in loaded.files for f in walk.walk(source)]
