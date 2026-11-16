"""The headline block: which levers it walks, what it refuses to name, and whose base each share names."""
import re

import fixtures as fx
from sa import render, cli, glossary, grammar, heads, notes, query, residual, schema, tables
from sa.schema import CALL

CONTEXT, SPEND = cli.VIEWS["context"], cli.VIEWS["spend"]
CAUSE, TOOL, HEAD = schema.CAUSE_DIM, schema.TOOL_DIM, schema.COMMAND_DIM


def _levers_of(out):
    """The dimensions the headline walks, in order: ``largest <dim>``, or
    the growth line's tool, then its command after ``→``."""
    text = fx.headline(out).partition("; ")[2]  # the block: the level's line names a drill's changes "from"
    if text.startswith("largest ") or "; largest " in text:
        return [re.search(r"largest (\w+) ", text).group(1)] + ([HEAD] if " → " in text else [])
    return [TOOL] + ([HEAD] if " → " in text else []) if " from " in text else []


def _rows(out):
    """The regular rows of the tables shown, split: a label, its figures, its share."""
    return [l.split() for l in out.splitlines() if re.match(r"^\S+\s+-?[\d,]+(\s+[\d,]+)+\s+[\d.]+%", l)]


def _largest_shown(out):
    """The mass of the first (largest) regular row of the first table shown."""
    return int(_rows(out)[0][1].replace(",", ""))


def test_headline_walks_the_view_levers_whatever_by_shows(tmp_path):
    """The headline is grouped from the view's levers alone: a shown table
    whose top row is larger (a cause, a session, a window) never leads, and
    ``by change`` shows no table at all. Pinning a lever drops it from the
    walk; every lever pinned, nothing leads."""
    root = fx.cli_corpus(tmp_path)
    assert CONTEXT.tables[0] == CAUSE and CAUSE not in CONTEXT.levers
    assert CONTEXT.levers == (TOOL, HEAD) and SPEND.levers == (schema.SUBAGENT_DIM,)
    lead = "; growth 433 0.5% from Bash 214 → Bash:pytest 214"
    for by in (CAUSE, schema.SESSION_DIM, schema.WINDOW_DIM):
        code, out, err = fx.run_cli("context", "--root", str(root), "by", by)
        assert code == 0, err
        assert fx.headline(out).endswith(lead), by
        assert _largest_shown(out) > 214, by  # vacuity guard: the shown table's top row is larger
    code, out, err = fx.run_cli("context", "--root", str(root), "by", "change")
    assert code == 0, err
    assert fx.headline(out).endswith(lead)
    for by in ([], ["by", schema.SESSION_DIM], ["by", grammar.FACTS["spend"]]):
        code, out, err = fx.run_cli("spend", "--root", str(root), *by)
        assert code == 0, err
        assert _levers_of(out) == [schema.SUBAGENT_DIM], by
    # A pinned head implies its tool, and every Bash call here has the one
    # head, so pinning either leaves no lever that is not the filter itself.
    facts = fx.load_facts(root)[1]
    assert query.values(query.select(facts, [(TOOL, "Bash")]), HEAD, CONTEXT.metric) == ["Bash:pytest"]
    for pin in ("%s=Bash:pytest" % HEAD, "%s=Bash" % TOOL):
        assert _levers_of(fx.run_cli("context", "--root", str(root), pin)[1]) == [], pin


def test_a_pin_omits_the_tables_and_levers_it_implies(tmp_path):
    """Pinning a command implies its tool; pinning a window implies its subagent,
    session and project. Any table or lever whose facts all share one value
    is omitted, since it would only repeat the filter; ``by DIM`` still prints
    it on request, and unpinned every default table prints."""
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "%s=Bash:pytest" % HEAD)
    assert code == 0, err
    assert _levers_of(out) == []
    for dim in (TOOL, CAUSE):  # the fixture's one Bash:pytest increment per window is exact
        assert not re.search(r"^by %s\s" % dim, out, re.M), dim
    also = next(l for l in out.splitlines() if l.startswith(render.ALSO))[len(render.ALSO):].split(", ")
    for dim in (schema.SUBAGENT_DIM, schema.SESSION_DIM, schema.PROJECT_DIM):  # two values each
        assert dim in also, dim  # a table away
    asked = fx.run_cli("context", "--root", str(root), "%s=Bash:pytest" % HEAD, "by", TOOL)[1]
    assert re.search(r"^Bash\s+214\s+3\s+100\.0%$", asked, re.M)
    window = ["%s=%s" % (schema.WINDOW_DIM, fx.window_value("proj-a/sess-0001.jsonl"))]
    code, out, err = fx.run_cli("context", "--root", str(root), *window)
    assert code == 0, err
    for dim in schema.WINDOW_DIMENSIONS:
        assert "by %s" % dim not in out, dim
    assert "by %s" % TOOL in out and "by %s" % HEAD in out
    assert " from Bash " in fx.headline(out)  # the window's tools are not implied
    unpinned = fx.run_cli("context", "--root", str(root))[1]
    assert all(re.search(r"^by (?:[\w /]+, )*%s[\s:,]" % dim, unpinned, re.M) for dim in CONTEXT.tables)  # vacuity guard


def test_headline_refines_the_top_tool_by_the_head_within_it_and_names_a_larger_head_elsewhere(tmp_path):
    """Three exact results in a window of 4 calls: Bash:ls 60 (held by 3
    calls), Bash:make 40 (2) under Bash, and Read:py (1) under Read; per
    call, Bash:ls 45, Bash:make 20. At 200 (50 per call) the top head
    overall lies under another tool, so it follows the refinement, named
    with its tool; at 30 the head within Bash is the top head and nothing
    follows. Pinning the tool leaves the head as the one lever when the
    tool has several."""
    def records(read_py):
        return [fx.assistant("uuid-0001", "msg-0001", fx.usage(1000, 0),
                             [fx.tool_use("toolu_0001", "Bash", command="ls")]),
                fx.tool_result("uuid-0002", "toolu_0001"),
                fx.assistant("uuid-0003", "msg-0002", fx.usage(1060, 0),
                             [fx.tool_use("toolu_0002", "Bash", command="make")]),
                fx.tool_result("uuid-0004", "toolu_0002"),
                fx.assistant("uuid-0005", "msg-0003", fx.usage(1100, 0),
                             [fx.tool_use("toolu_0003", "Read", file_path="/x/a.py")]),
                fx.tool_result("uuid-0006", "toolu_0003"),
                fx.assistant("uuid-0007", "msg-0004", fx.usage(1100 + read_py, 0))]
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": records(200)})
    facts = fx.load_facts(root)[1]
    heads = [(r.value, r.mass) for r in query.group(facts, HEAD, CONTEXT.metric, 4).rows
             if r.kind == query.REGULAR]
    assert heads == [("Read:py", 50), ("Bash:ls", 45), ("Bash:make", 20)]  # guard: the masses
    code, out, err = fx.run_cli("context", "--root", str(root))
    assert code == 0, err
    assert fx.headline(out).endswith("; growth 115 10.3%% from Bash 65 → Bash:ls 45; top %s Read:py 50" % HEAD)
    code, out, err = fx.run_cli("context", "--root", str(root), "%s=Bash" % TOOL)
    assert code == 0, err
    assert fx.headline(out).endswith(" · 2 changes in 1 window, 4 calls; largest %s 45 69.2%% Bash:ls" % HEAD)
    root = fx.corpus(tmp_path / "within", {"proj-a/sess-0001.jsonl": records(30)})
    code, out, err = fx.run_cli("context", "--root", str(root))
    assert code == 0, err
    assert fx.headline(out).endswith(" from Bash 65 → Bash:ls 45")


def test_a_top_tool_with_no_head_still_names_the_top_head_under_its_tool(tmp_path):
    """Agent has no head extractor: its result of 90 (60 per call: 2 of 3
    calls held it) is the top tool with nothing within it, and the top
    head, Bash:ls 60 (20 per call) under Bash, follows."""
    records = [fx.assistant("uuid-0001", "msg-0001", fx.usage(1000, 0),
                            [fx.tool_use("toolu_0001", "Agent", prompt="x")]),
               fx.tool_result("uuid-0002", "toolu_0001"),
               fx.assistant("uuid-0003", "msg-0002", fx.usage(1090, 0),
                            [fx.tool_use("toolu_0002", "Bash", command="ls")]),
               fx.tool_result("uuid-0004", "toolu_0002"),
               fx.assistant("uuid-0005", "msg-0003", fx.usage(1150, 0))]
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": records})
    assert "Agent" not in heads.EXTRACTORS  # the missing head is the tool's, not a fixture gap
    code, out, err = fx.run_cli("context", "--root", str(root))
    assert code == 0, err
    assert fx.headline(out).endswith(" from Agent 60; top %s Bash:ls 20" % HEAD)
    assert "Agent 60 →" not in fx.headline(out)
    headed = fx.run_cli("context", "--root", str(fx.cli_corpus(tmp_path / "headed")))[1]
    assert " → Bash:" in fx.headline(headed)  # vacuity guard: a command within its tool


def test_the_headline_never_names_a_cause(tmp_path):
    """One interval with two Read results of one head: ambiguous is the
    largest cause after starting_context and carries the shared tool and command,
    which lead; no cause does, even under ``by cause``."""
    uses = [fx.tool_use("toolu_0001", "Read", file_path="/x/a.py"),
            fx.tool_use("toolu_0002", "Read", file_path="/x/b.py")]
    records = [fx.assistant("uuid-0001", "msg-0001", fx.usage(1000, 50), uses),
               fx.tool_result("uuid-0002", "toolu_0001"), fx.tool_result("uuid-0003", "toolu_0002"),
               fx.assistant("uuid-0004", "msg-0002", fx.usage(1300, 0))]
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": records})
    code, out, err = fx.run_cli("context", "--root", str(root), "by", CAUSE)
    assert code == 0, err
    assert [r[0] for r in _rows(out)] == [schema.STARTING_CONTEXT, glossary.marked(schema.AMBIGUOUS), schema.REPLIES]
    assert _largest_shown(out) == 1000 > 125  # vacuity guard: the cause rows are the larger
    assert fx.headline(out).endswith(" from Read 125 → Read:py 125")  # the shared ambiguous counts
    assert "names a tool" in glossary.GLOSSARY[schema.AMBIGUOUS].surprise  # -v says so
    verbose = fx.run_cli("context", "--root", str(root), "by", CAUSE, "-v")[1]
    for value in (schema.STARTING_CONTEXT, schema.AMBIGUOUS):
        term = glossary.printed(value).replace("_", " ") if value == schema.STARTING_CONTEXT else value
        assert "\n".join(notes.define(term)) in verbose, value
    # With one result the interval is exact: the same lead.
    root = fx.corpus(tmp_path / "exact", {"proj-a/sess-0001.jsonl": records[:2] + records[3:]})
    out = fx.run_cli("context", "--root", str(root), "by", CAUSE, "-v")[1]
    assert " from Read 125 → " in fx.headline(out)
    assert " + 0 %s + " % schema.AMBIGUOUS in fx.worked(out)  # the checks' split, worked under -v
    assert schema.STARTING_CONTEXT.replace("_", " ") in dict(fx.key(out))  # vacuity guard: -v defines


def test_headline_share_is_of_the_added_while_the_table_share_is_of_its_base(tmp_path):
    """Per call, Bash holds 214 of the 84,766 held before shrink (84,709,
    the average, net of the -57 shrink): the table's share column is over
    the 214 that have a tool at all; the headline's shares are of the
    84,766, the signed row out of them as out of the cause table's."""
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "by", TOOL)
    assert code == 0, err
    assert re.search(r"^%s\s+84,552\s+\d+\s+-  = %s 84,333 \+ " % (
        re.escape(residual.label(TOOL)), schema.STARTING_CONTEXT), out, re.M)  # in no share, its parts shown
    assert re.search(r"^%s\s+-57\s" % re.escape(glossary.marked(schema.SHRINK)), out, re.M)
    assert " 84,333 99.5% " in fx.headline(out) and " 433 0.5% " in fx.headline(out)  # of the 84,766
    verbose = fx.run_cli("context", "--root", str(root), "by", TOOL, "-v")[1]
    assert re.search(r"\n  added 254,860 - %s 300 +  = 254,560 " % schema.SHRINK, fx.worked(verbose))  # summed
    assert " from Bash 214" in fx.headline(out)
    assert re.search(r"^by %s\s.*\s+%s\s+share$" % (TOOL, fx.count_column(CONTEXT.metric)), out, re.M)
    assert re.search(r"^Bash\s+214\s+3\s+100\.0%$", out, re.M)
    assert re.search(r"^%s\s+214\s+3  %s$" % (re.escape(tables.BASE_LABEL), re.escape(  # the base: what has a tool
        tables.BASE_NOTE % residual.label(TOOL))), out, re.M)


def test_headline_total_and_table_base_are_one_sum(tmp_path):
    """Three calls whose spends sum to a .5 in file order and to just under
    it grouped by session (an agent file shares its parent's session, with
    another session's file between them in owner order)."""
    files = {"proj-a/sess-0001.jsonl": (0, 1, fx.SESSION),
             "proj-b/sess-0002.jsonl": (1, 1, "sess-0002"),
             "proj-a/sess-0001/subagents/agent-fake1.jsonl": (2, 13, fx.SESSION)}
    root = fx.corpus(tmp_path, {
        name: fx.stamped([fx.assistant("uuid-%d" % start, "msg-%d" % start,
                                       fx.usage(4 + cache_read, 0), session=session)], start)
        for name, (start, cache_read, session) in files.items()})
    a, b, c = [f.metrics[SPEND.metric] for f in fx.load_facts(root)[1] if f.kind == CALL]
    assert tables.num((a + b) + c) != tables.num((a + c) + b)  # the two orders really straddle a .5
    code, out, err = fx.run_cli("spend", "--root", str(root), "by", schema.SESSION_DIM)
    assert code == 0, err
    headline = re.match(r"%s([\d,]+) " % re.escape(fx.total_line(SPEND.metric)), fx.headline(out)).group(1)
    grouped = query.group(fx.load_facts(root)[1], schema.SESSION_DIM, SPEND.metric)
    assert not [r for r in grouped.rows if r.kind != query.REGULAR]  # every row in a share: the base is the total
    assert re.search(r"^%s\s+%s\s" % (re.escape(tables.BASE_LABEL), headline), out, re.M)
    assert headline == tables.num(grouped.base)  # the base is the total less the other rows, never re-summed
