"""``--by fact``: an ambiguous change's candidates each carry their size as
the transcript records it, characters of text, never tokens."""
import re

import fixtures as fx
from sa import schema, walk


def _records():
    """One call, two Read results batched into one record (one with an
    image beside its text), and a typed line: one ambiguous gap."""
    uses = [fx.tool_use("toolu_0001", "Read", file_path="/x/a.py"),
            fx.tool_use("toolu_0002", "Read", file_path="/x/b.png")]
    results = fx.tool_result("uuid-0002", "toolu_0001", "toolu_0002")
    first, second = results["message"]["content"]
    first["content"] = "x" * 1234
    second["content"] = [{"type": "text", "text": "y" * 45}, {"type": "image", "source": {}}]
    return [fx.assistant("uuid-0001", "msg-0001", fx.usage(1000, 50), uses), results,
            fx.user_text("uuid-0003", "z" * 7), fx.assistant("uuid-0004", "msg-0002", fx.usage(3000, 0))]


def test_each_candidate_carries_its_recorded_characters(tmp_path):
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": _records()})
    facts = fx.load_facts(root)[1]
    (ambiguous,) = [f for f in facts if f.dims.get(schema.CAUSE_DIM) == schema.AMBIGUOUS]
    sizes = [(c.chars, c.other) for c in ambiguous.evidence[schema.CANDIDATES]]
    assert sizes == [(1234, 0), (45, 1), (7, 0)]  # one per tool_result block, then the typed text
    code, out, err = fx.run_cli("context", "--root", str(root), "--by", "fact", "--where",
                                "%s=%s" % (schema.CAUSE_DIM, schema.AMBIGUOUS))
    assert code == 0, err
    lines = out.splitlines()
    at = lines.index(next(l for l in lines if l.strip() == schema.CANDIDATES + ":"))
    assert [re.search(r"  ([\d,]+ characters(?: \+ \d+ non-text)?)  ", l).group(1)
            for l in lines[at + 1:at + 4]] == ["1,234 characters", "45 characters + 1 non-text", "7 characters"]
    assert "token" not in "".join(lines[at:at + 4])  # never converted


def test_recorded_size_reads_text_and_counts_the_rest():
    assert walk.recorded_size("abc") == (3, 0)
    assert walk.recorded_size([{"type": "text", "text": "ab"}, "c", {"type": "image"}]) == (3, 1)
    assert walk.recorded_size(None) == (0, 0)
