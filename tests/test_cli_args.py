"""What ``python3 -m sa`` refuses and how it narrows: every refusal is exit
status 2 with nothing on stdout, and sits beside the accepted form of the
same argument so the refusal is never vacuous."""
import os
import re
import time

import pytest

import fixtures as fx
import fixtures_edge as fe
from sa import cli, corpus, grammar, query, render, schema

CONTEXT = cli.VIEWS["context"]
CAUSE, TOOL = schema.CAUSE_DIM, schema.TOOL_DIM


def _answers(code, out, err):
    assert code == 0, err
    assert re.search(r"^(%s|\S+: )[1-9]" % re.escape(fx.total_line(CONTEXT.metric)), fx.headline(out))


@pytest.mark.parametrize("dim,args", [(TOOL, ("%s=Bash" % TOOL,)), (CAUSE, (grammar.BY, CAUSE))])
def test_spend_refuses_a_dimension_its_carrier_never_has(tmp_path, dim, args):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("spend", "--root", str(root), *args)
    assert code == 2 and not out and len(err.splitlines()) <= 2
    assert "spend's %s carry no %s" % (schema.PLURAL[schema.CALL], dim) in err
    assert ", ".join(schema.KIND_DIMENSIONS[schema.CALL]) in err  # where the choices live
    _answers(*fx.run_cli("context", "--root", str(root), *args))  # vacuity guard


@pytest.mark.parametrize("word,said", [
    ("changes", "context lists its %s: by %s" % (schema.PLURAL[schema.INCREMENT], grammar.FACTS["context"])),
    (grammar.FACTS["spend"], "context lists its %s: by %s" % (schema.PLURAL[schema.INCREMENT],
                                                              grammar.FACTS["context"])),
    ("colour", "unknown dimension 'colour'")])
def test_by_refuses_what_is_neither_the_facts_nor_a_dimension_naming_both(tmp_path, word, said):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), grammar.BY, word)
    assert code == 2 and not out and len(err.splitlines()) <= 2 and said in err
    for by in (grammar.FACTS["context"], schema.DIMENSIONS[0]):
        _answers(*fx.run_cli("context", "--root", str(root), grammar.BY, by))  # vacuity guard


def test_unknown_dimension_is_refused(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "colour=red")
    assert code == 2 and not out and "unknown dimension" in err


@pytest.mark.parametrize("dim,value", [(dim, value) for dim in sorted(schema.VOCABULARY)
                                       for value in schema.VOCABULARY[dim]])
def test_unknown_value_of_a_closed_vocabulary_dimension_is_refused(tmp_path, dim, value):
    """Every declared value is accepted (the fixture carries each one), and
    the undeclared one beside it is refused naming the vocabulary. Every
    parent is kept, so inherited mass is counted in its parent: the drill
    is held by the fork's calls (D-PER-CALL), so it is no zero either."""
    root = fx.every_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "%s=bogus" % dim)
    assert code == 2 and not out
    assert "unknown %s 'bogus'; declared: %s" % (dim, ", ".join(schema.VOCABULARY[dim])) in err
    code, out, err = fx.run_cli("context", "--root", str(root), "%s=%s" % (dim, value))
    assert code == 0, err  # vacuity guard
    lead = re.escape(fx.total_line(CONTEXT.metric)) if dim in schema.WINDOW_DIMENSIONS else r"%s\*?: " % value
    assert re.search(r"^%s-?[1-9]" % lead, fx.headline(out))  # a drill names its pin; shrink's is negative


@pytest.mark.parametrize("bogus,message,good", [
    (["%s=bash" % TOOL], "no change has %s=bash; nearest: %s=Bash\nevery %s: %s" % (
        TOOL, TOOL, TOOL, grammar.run("context", grammar.BY, TOOL)), ["%s=Bash" % TOOL]),
    (["%s=proj-c" % schema.PROJECT_DIM], "no change has %s=proj-c; nearest: %s=proj-b" % (
        schema.PROJECT_DIM, schema.PROJECT_DIM), ["%s=proj-a" % schema.PROJECT_DIM]),
    # Narrowed pair by pair: project b has no agent window, project a has one.
    (["%s=proj-b" % schema.PROJECT_DIM, "%s=agent-fake1" % schema.SUBAGENT_DIM],
     "no %s has %s=agent-fake1 with the pins before it; none present" % (
         schema.PLURAL[schema.INCREMENT][:-1], schema.SUBAGENT_DIM),
     ["%s=proj-a" % schema.PROJECT_DIM, "%s=agent-fake1" % schema.SUBAGENT_DIM]),
])
def test_a_value_no_fact_carries_is_refused_naming_the_values_present(tmp_path, bogus, message, good):
    """An open-vocabulary filter that matches nothing is the same confident
    zero as a misspelt cause; the data's values, by mass, are the vocabulary."""
    assert not {pair.split("=")[0] for pair in bogus} & set(schema.VOCABULARY)
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), *bogus)
    assert code == 2 and not out and len(err.splitlines()) <= 2
    assert message + "\n" in err
    _answers(*fx.run_cli("context", "--root", str(root), *good))  # vacuity guard


def test_a_declared_value_no_fact_carries_is_a_measured_zero(tmp_path):
    """The batched corpus books one ambiguous increment, a several:
    the other declared reasons are present in no fact, which is a measured
    zero over the population named, like ``--since 0d``, not a typo."""
    root = fe.batched_corpus(tmp_path)
    facts = fx.load_facts(root)[1]
    absent = [r for r in schema.REASONS if not query.select(facts, [(schema.REASON_DIM, r)])]
    assert absent and len(absent) < len(schema.REASONS)  # vacuity guard: one is carried
    for reason in absent:
        code, out, err = fx.run_cli("context", "--root", str(root), "%s=%s" % (schema.REASON_DIM, reason))
        assert code == 0, err
        assert fx.headline(out) == "%s: 0 of the 1,150-token average call · 0 changes in 0 of 1 window, 2 calls" % (
            reason)
        assert "\nin view: 1 window*, " in out and render.ALSO not in out  # no fact: no table to offer
    assert render.ALSO in fx.run_cli("context", "--root", str(root))[1]  # vacuity guard
    code, out, err = fx.run_cli("context", "--root", str(root), "%s=bogus" % schema.REASON_DIM)
    assert code == 2 and not out and "unknown %s" % schema.REASON_DIM in err  # a typo is still refused


def test_root_must_be_an_existing_directory(tmp_path):
    """A mistyped root is a refusal, never a zero headline; an empty
    population is only ever reached through a filter (``--since 0d``, below)."""
    root = fx.cli_corpus(tmp_path)
    for typo in (root.parent / "typo", root / "proj-a" / "sess-0001.jsonl"):
        code, out, err = fx.run_cli("context", "--root", str(typo))
        assert code == 2 and not out and "no such directory: %s" % typo in err
    _answers(*fx.run_cli("context", "--root", str(root)))  # vacuity guard


def test_since_selects_files_by_mtime_and_zero_days_selects_none(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--since", "0d")
    assert code == 0, err
    assert "read: 0 files from the last 0d under " in out and "\nin view: 0 windows*, 0 changes" in out
    code, out, err = fx.run_cli("context", "--root", str(root), "--since", "1d")
    assert code == 0, err
    assert "read: 4 files from the last 1d under " in out and "\nin view: 3 windows*, " in out
    code, out, err = fx.run_cli("context", "--root", str(root), "--since=-1d")
    assert code == 2 and not out and "number of days" in err


def test_since_excludes_a_parent_before_dedup_so_its_continuation_owns_the_replayed_prefix(tmp_path):
    """Dedup runs over the kept files only: once the parent is too old, the
    continuation's replayed prefix is live and its window is booked from its
    first record (occupancy 1,000), not from its first unshared one (1,500,
    of which 1,300 inherited)."""
    original = fx.stamped(fx.window_records(), 0)  # runs longest, so it owns the shared prefix
    continuation = fx.stamped(fx.window_records()[:5], 0) + fx.stamped(fx.window_records("c-")[5:10], 5)
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": original, "proj-a/sess-0002.jsonl": continuation})
    args = ("context", "--root", str(root), "--since", "1d", "%s=%s" % (CAUSE, schema.STARTING_CONTEXT),
            "by", "change")
    headline = " · %s in %s, %s"
    first, second = "proj-a/sess-0001.jsonl", "proj-a/sess-0002.jsonl"

    def heads(out):  # each starting context's raw tokens (the leaves' second column) under its file
        found, file = [], None
        for line in out.splitlines():
            if re.match(r"^\S+\.jsonl  ", line):
                file = line.split()[0]
            elif fx.LEAF.match(line):
                found.append((int(line.split()[1].replace(",", "")), file))
        return sorted(found)
    code, out, err = fx.run_cli(*args)  # vacuity guard: both kept, the prefix is duplicate
    assert code == 0, err
    # 200: the continuation's head less what it inherited (1,300, in its inherited change)
    assert heads(out) == [(200, second), (1000, first)]
    assert "%s=%s" % (schema.STARTED_BY_DIM, schema.REPLAYED) in out  # the continuation's window header
    assert headline % ("2 changes", "2 windows", "10 calls") in fx.headline(out)
    assert "read: 2 files from the last 1d under " in out and "; 0 lines skipped, 5 duplicates\n" in out
    stale = time.time() - 2 * corpus.DAY
    os.utime(root / "proj-a" / "sess-0001.jsonl", (stale, stale))
    code, out, err = fx.run_cli(*args)
    assert code == 0, err
    assert heads(out) == [(1000, second)]  # booked from its first record now
    assert headline % ("1 change", "1 window", "5 calls") in fx.headline(out)
    assert "read: 1 file from the last 1d under " in out and "; 0 lines skipped, 0 duplicates\n" in out
    facts = fx.load_facts(root, 1)[1]
    assert {f.dims[schema.STARTED_BY_DIM] for f in facts} == {schema.SESSION_START}


@pytest.mark.parametrize("old,new", [(("--where", "%s=Bash" % TOOL), ("%s=Bash" % TOOL,)),
                                     (("--by", TOOL), (grammar.BY, TOOL)), (("--limit", "1"), ())])
def test_a_retired_flag_is_refused_naming_what_replaced_it(tmp_path, old, new):
    """UX_PRINCIPLES 1: a mistake answers with the nearest valid input."""
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), *old)
    assert code == 2 and not out and len(err.splitlines()) <= 2
    assert "%s is retired: %s" % (old[0], grammar.RETIRED[old[0]]) in err
    _answers(*fx.run_cli("context", "--root", str(root), *new))  # vacuity guard: its replacement runs
