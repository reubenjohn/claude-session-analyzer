"""The headline block: which levers it walks, what it refuses to name, and whose base each share names."""
import re

import fixtures as fx
from sa import cli, glossary, heads, query, schema, tables
from sa.schema import CALL

CONTEXT, SPEND = cli.VIEWS["context"], cli.VIEWS["spend"]
CAUSE, TOOL, HEAD = schema.CAUSE_DIM, schema.TOOL_DIM, schema.COMMAND_DIM


def _levers_of(out):
    """The dimensions the headline walks, in order: ``largest <dim>``, or
    the growth line's tool, then its command after ``→``."""
    text = fx.headline(out)
    if "; largest " in text:
        return [re.search(r"; largest (\w+) ", text).group(1)] + ([HEAD] if " → " in text else [])
    return [TOOL] + ([HEAD] if " → " in text else []) if " from " in text else []


def _largest_shown(out):
    """The mass of the first (largest) regular row of the first table shown."""
    return int(next(l for l in out.splitlines() if l.endswith("%") and not l.startswith(" "))
               .split()[1].replace(",", ""))


def test_headline_walks_the_view_levers_whatever_by_shows(tmp_path):
    """The headline is grouped from the view's levers alone: a shown table
    whose top row is larger (a cause, a session, a window) never leads, and
    ``--by fact`` shows no table at all. Pinning a lever drops it from the
    walk; every lever pinned, nothing leads."""
    root = fx.cli_corpus(tmp_path)
    assert CONTEXT.tables[0] == CAUSE and CAUSE not in CONTEXT.levers
    assert CONTEXT.levers == (TOOL, HEAD) and SPEND.levers == (schema.SUBAGENT_DIM,)
    lead = "; growth 1,860 0.7% from Bash 750 → Bash:pytest 750"
    for by in (CAUSE, schema.SESSION_DIM, schema.WINDOW_DIM):
        code, out, err = fx.run_cli("context", "--root", str(root), "--by", by)
        assert code == 0, err
        assert fx.headline(out).endswith(lead), by
        assert _largest_shown(out) > 750, by  # vacuity guard: the shown table's top row is larger
    code, out, err = fx.run_cli("context", "--root", str(root), "--by", "fact")
    assert code == 0, err
    assert fx.headline(out).endswith(lead)
    for by in ([], ["--by", schema.SESSION_DIM], ["--by", "fact"]):
        code, out, err = fx.run_cli("spend", "--root", str(root), *by)
        assert code == 0, err
        assert _levers_of(out) == [schema.SUBAGENT_DIM], by
    assert SPEND.tables[0] != schema.SUBAGENT_DIM  # vacuity guard: not the first table printed
    # A pinned head implies its tool, and every Bash call here has the one
    # head, so pinning either leaves no lever that is not the filter itself.
    facts = fx.load_facts(root)[1]
    assert query.values(query.select(facts, [(TOOL, "Bash")]), HEAD, CONTEXT.metric) == ["Bash:pytest"]
    for pin in ("%s=Bash:pytest" % HEAD, "%s=Bash" % TOOL):
        assert _levers_of(fx.run_cli("context", "--root", str(root), "--where", pin)[1]) == [], pin


def test_a_pin_omits_the_tables_and_levers_it_implies(tmp_path):
    """Pinning a command implies its tool; pinning a window implies its subagent,
    session and project. Any table or lever whose facts all share one value
    is omitted, since it would only repeat the filter; ``--by`` still prints
    it on request, and unpinned every default table prints."""
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--where", "%s=Bash:pytest" % HEAD)
    assert code == 0, err
    assert _levers_of(out) == []
    for dim in (TOOL, CAUSE):  # the fixture's one Bash:pytest increment per window is exact
        assert not re.search(r"^by %s\s" % dim, out, re.M), dim
    for dim in (schema.SUBAGENT_DIM, schema.SESSION_DIM, schema.PROJECT_DIM):  # two values each
        assert re.search(r"^by (?:[\w /]+, )*%s[\s:,]" % dim, out, re.M), dim  # a table, or its relabel line
    asked = fx.run_cli("context", "--root", str(root), "--where", "%s=Bash:pytest" % HEAD, "--by", TOOL)[1]
    assert re.search(r"^Bash\s+750\s+3\s+100\.0%$", asked, re.M)
    window = ["--where", "%s=%s" % (schema.WINDOW_DIM, fx.window_value("proj-a/sess-0001.jsonl"))]
    code, out, err = fx.run_cli("context", "--root", str(root), *window)
    assert code == 0, err
    for dim in schema.WINDOW_DIMENSIONS:
        assert "by %s" % dim not in out, dim
    assert "by %s" % TOOL in out and "by %s" % HEAD in out
    assert " from Bash " in fx.headline(out)  # the window's tools are not implied
    unpinned = fx.run_cli("context", "--root", str(root))[1]
    assert all(re.search(r"^by (?:[\w /]+, )*%s[\s:,]" % dim, unpinned, re.M) for dim in CONTEXT.tables)  # vacuity guard


def test_headline_refines_the_top_tool_by_the_head_within_it_and_names_a_larger_head_elsewhere(tmp_path):
    """Three exact results: Bash:ls 60 and Bash:make 40 under Bash, and
    Read:py under Read. At 70 the top head overall lies under another
    tool, so it follows the refinement, named with its tool; at 30 the
    head within Bash is the top head and nothing follows. Pinning the tool
    leaves the head as the one lever when the tool has several."""
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
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": records(70)})
    facts = fx.load_facts(root)[1]
    heads = [(r.value, r.mass) for r in query.group(facts, HEAD, fx.DELTA).rows
             if r.kind == query.REGULAR]
    assert heads == [("Read:py", 70), ("Bash:ls", 60), ("Bash:make", 40)]  # guard: the masses
    code, out, err = fx.run_cli("context", "--root", str(root))
    assert code == 0, err
    assert fx.headline(out).endswith("; growth 170 14.5%% from Bash 100 → Bash:ls 60; top %s Read:py 70" % HEAD)
    code, out, err = fx.run_cli("context", "--root", str(root), "--where", "%s=Bash" % TOOL)
    assert code == 0, err
    assert fx.headline(out).endswith(" in 1 window; largest %s 60 60.0%% Bash:ls" % HEAD)
    root = fx.corpus(tmp_path / "within", {"proj-a/sess-0001.jsonl": records(30)})
    code, out, err = fx.run_cli("context", "--root", str(root))
    assert code == 0, err
    assert fx.headline(out).endswith(" from Bash 100 → Bash:ls 60")


def test_a_top_tool_with_no_head_still_names_the_top_head_under_its_tool(tmp_path):
    """Agent has no head extractor: its result of 90 is the top tool with
    nothing within it, and the top head, Bash:ls 60 under Bash, follows."""
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
    assert fx.headline(out).endswith(" from Agent 90; top %s Bash:ls 60" % HEAD)
    assert "Agent 90 →" not in fx.headline(out)
    headed = fx.run_cli("context", "--root", str(fx.cli_corpus(tmp_path / "headed")))[1]
    assert " → Bash:" in fx.headline(headed)  # vacuity guard: a command within its tool


def test_the_headline_never_names_a_cause(tmp_path):
    """One interval with two Read results of one head: ambiguous is the
    largest cause after starting_context and carries the shared tool and command,
    which lead; no cause does, even under ``--by cause``."""
    uses = [fx.tool_use("toolu_0001", "Read", file_path="/x/a.py"),
            fx.tool_use("toolu_0002", "Read", file_path="/x/b.py")]
    records = [fx.assistant("uuid-0001", "msg-0001", fx.usage(1000, 50), uses),
               fx.tool_result("uuid-0002", "toolu_0001"), fx.tool_result("uuid-0003", "toolu_0002"),
               fx.assistant("uuid-0004", "msg-0002", fx.usage(1300, 0))]
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": records})
    code, out, err = fx.run_cli("context", "--root", str(root), "--by", CAUSE)
    assert code == 0, err
    rows = [l.split() for l in out.splitlines() if l.endswith("%") and not l.startswith("  ")]
    assert [r[0] for r in rows] == [schema.STARTING_CONTEXT, glossary.marked(schema.AMBIGUOUS), schema.REPLIES]
    assert _largest_shown(out) == 1000 > 250  # vacuity guard: the cause rows are the larger
    assert fx.headline(out).endswith(" from Read 250 → Read:py 250")  # the shared ambiguous counts
    assert "a tool's row" in tables.UNSPLITTABLE[schema.AMBIGUOUS]  # the key says so
    for value in (schema.STARTING_CONTEXT, schema.AMBIGUOUS):
        assert (glossary.printed(value), tables.UNSPLITTABLE[value]) in fx.key(out)
    # With one result the interval is exact: the same lead.
    root = fx.corpus(tmp_path / "exact", {"proj-a/sess-0001.jsonl": records[:2] + records[3:]})
    out = fx.run_cli("context", "--root", str(root), "--by", CAUSE)[1]
    assert " from Read 250 → " in fx.headline(out)
    assert fx.key(out)[-1][0] == schema.AMBIGUOUS  # footnoted where first printed: the checks
    assert " 0 %s (0.0%%)" % glossary.marked(schema.AMBIGUOUS) in out.splitlines()[-1]
    assert schema.STARTING_CONTEXT in dict(fx.key(out))  # vacuity guard: the key prints


def test_headline_share_is_of_the_added_while_the_table_share_is_of_its_base(tmp_path):
    """Bash carries 750 of the 254,860 tokens added (254,560 net of the -300
    shrink): the table's share column is over the 750 that have a tool at
    all; the headline's shares are of the 254,860 added, named once on the
    total's line, the signed row out of them as out of the cause table's."""
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--by", TOOL)
    assert code == 0, err
    assert re.search(r"^%s\s+254,110\s+\d+\s+-  no tool: " % re.escape(tables.RESIDUAL_ROW), out, re.M)
    assert re.search(r"^%s \(signed\)\s+-300\s" % re.escape(glossary.marked(schema.SHRINK)), out, re.M)
    assert " 253,000 99.3% " in fx.headline(out) and " 1,860 0.7% " in fx.headline(out)  # of the 254,860
    assert out.splitlines()[-1].startswith("%s checks: 254,860 added - 300 %s = 254,560" % (tables.OK_MARK, schema.SHRINK))
    assert " from Bash 750" in fx.headline(out)
    assert re.search(r"^by %s\s.*\s+%s\s+share of 750 \(all but unassigned\)$" % (TOOL, fx.count_column(CONTEXT.metric)), out, re.M)
    assert re.search(r"^Bash\s+750\s+3\s+100\.0%$", out, re.M)


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
    code, out, err = fx.run_cli("spend", "--root", str(root), "--by", SPEND.tables[1])
    assert code == 0, err
    headline = re.match(r"%s([\d,]+) " % re.escape(fx.total_line(SPEND.metric)), fx.headline(out)).group(1)
    assert re.search(r"^by %s\s.*share of total$" % SPEND.tables[1], out, re.M)  # the base is the total
    grouped = query.group(fx.load_facts(root)[1], SPEND.tables[1], SPEND.metric)
    assert headline == tables.num(grouped.base)  # the base is the total less the other rows, never re-summed
