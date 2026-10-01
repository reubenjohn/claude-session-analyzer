"""What ``python3 -m sa`` refuses and how it narrows: every refusal is exit
status 2 with nothing on stdout, and sits beside the accepted form of the
same argument so the refusal is never vacuous."""
import re

import pytest

import fixtures as fx
from sa import cli, schema

CONTEXT = cli.VIEWS["context"]
CAUSE, TOOL = schema.CAUSE_DIM, schema.TOOL_DIM


def _where(pairs):
    return [arg for pair in pairs for arg in ("--where", pair)]


def _answers(code, out, err):
    assert code == 0, err
    assert re.search(r"^%s: [1-9]" % CONTEXT.metric, out)


@pytest.mark.parametrize("flag,value", [("--where", "%s=Bash" % TOOL), ("--by", CAUSE)])
def test_spend_refuses_a_dimension_its_carrier_never_has(tmp_path, flag, value):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("spend", "--root", str(root), flag, value)
    assert code == 2 and not out
    assert "'%s' is never carried by call facts" % value.split("=")[0] in err
    _answers(*fx.run_cli("context", "--root", str(root), flag, value))  # vacuity guard


def test_unknown_dimension_is_refused(tmp_path):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--where", "colour=red")
    assert code == 2 and not out and "unknown dimension" in err


@pytest.mark.parametrize("dim,value", [(dim, value) for dim in sorted(schema.VOCABULARY)
                                       for value in schema.VOCABULARY[dim]])
def test_unknown_value_of_a_closed_vocabulary_dimension_is_refused(tmp_path, dim, value):
    """Every declared value is accepted (the fixture carries each one), and
    the undeclared one beside it is refused naming the vocabulary."""
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--where", "%s=bogus" % dim)
    assert code == 2 and not out
    assert "unknown %s 'bogus'; declared: %s" % (dim, ", ".join(schema.VOCABULARY[dim])) in err
    code, out, err = fx.run_cli("context", "--root", str(root), "--where", "%s=%s" % (dim, value))
    assert code == 0, err  # vacuity guard
    assert re.search(r"^%s: -?[1-9]" % CONTEXT.metric, out)  # shrink's total is negative


@pytest.mark.parametrize("bogus,message,good", [
    (["%s=bash" % TOOL], "%s=bash; present: Bash" % TOOL, ["%s=Bash" % TOOL]),
    (["%s=proj-c" % schema.PROJECT_DIM], "%s=proj-c; present: proj-a, proj-b" % schema.PROJECT_DIM,
     ["%s=proj-a" % schema.PROJECT_DIM]),
    # Narrowed pair by pair: project b has no agent window, project a has one.
    (["%s=proj-b" % schema.PROJECT_DIM, "%s=agent-fake1" % schema.AGENT_DIM],
     "%s=agent-fake1; present: none" % schema.AGENT_DIM,
     ["%s=proj-a" % schema.PROJECT_DIM, "%s=agent-fake1" % schema.AGENT_DIM]),
])
def test_a_value_no_fact_carries_is_refused_naming_the_values_present(tmp_path, bogus, message, good):
    """An open-vocabulary filter that matches nothing is the same confident
    zero as a misspelt cause; the data's values, by mass, are the vocabulary."""
    assert not {pair.split("=")[0] for pair in bogus} & set(schema.VOCABULARY)
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), *_where(bogus))
    assert code == 2 and not out
    assert "no facts carry %s\n" % message in err
    _answers(*fx.run_cli("context", "--root", str(root), *_where(good)))  # vacuity guard


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
    assert ", 0 files (modified within 0d), " in out and "\nkept: 0 windows, 0 call facts" in out
    code, out, err = fx.run_cli("context", "--root", str(root), "--since", "1d")
    assert code == 0, err
    assert ", 4 files (modified within 1d), " in out and "\nkept: 3 windows, " in out
    code, out, err = fx.run_cli("context", "--root", str(root), "--since=-1d")
    assert code == 2 and not out and "number of days" in err


@pytest.mark.parametrize("limit", ["0", "-1"])
def test_limit_must_be_positive(tmp_path, limit):
    root = fx.cli_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--limit", limit)
    assert code == 2 and not out and "positive number of rows" in err
    assert fx.run_cli("context", "--root", str(root), "--limit", "1")[0] == 0  # vacuity guard
