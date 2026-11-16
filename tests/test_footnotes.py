"""The ``*`` footnotes and the next-step hint: every term the body marks is
in the key, every key term is marked once in the body, and the hint follows
the headline's levers down to ``--by fact``."""
import re
from types import SimpleNamespace

import pytest

import fixtures as fx
from sa import cli, glossary, render, schema, tables

STAR = re.escape(glossary.MARKER)


def _split(out):
    lines = out.splitlines()
    at = next(i for i, line in enumerate(lines) if line.startswith(tables.KEY_TITLE))
    end = lines.index("", at)
    return lines[:at] + lines[end:], lines[at + 1:end]


@pytest.mark.parametrize("args", [("context",), ("spend",), ("context", "--where", "tool=Bash"),
                                  ("context", "--by", "fact"), ("spend", "--by", "subagent")])
def test_the_marked_terms_and_the_key_terms_are_one_set(tmp_path, args):
    out = fx.run_cli(*args, "--root", str(fx.cli_corpus(tmp_path)))[1]
    body, key = _split(out)
    keyed = [re.match(r"^  (\S+)%s +=" % STAR, line).group(1) for line in key]
    known = {glossary.printed(t) for t in glossary.GLOSSARY}
    marked = [w if w in known else w[:-1] for w in re.findall(r"(\w+)%s" % STAR, "\n".join(body))]
    assert keyed and marked  # vacuity guard
    assert set(marked) == set(keyed) and len(keyed) == len(set(keyed))
    assert all(glossary.key_of(t) in glossary.GLOSSARY for t in keyed)
    once = [t for t in keyed if t != tables.RESIDUAL_LABEL]  # every table labels its residual row
    assert all(len(re.findall(r"(?<!\w)%ss?%s" % (t, STAR), "\n".join(body))) == 1 for t in once)
    assert re.search(r"explain %s$" % re.escape(keyed[0]), next(
        line for line in out.splitlines() if line.startswith(tables.KEY_TITLE)))


@pytest.mark.parametrize("args, hint", [
    (("context",), "--where %s=Bash" % schema.TOOL_DIM),
    (("context", "--where", "tool=Bash"), "--by fact"),  # its one command is implied: no lever left
    (("context", "--where", "command=Bash:pytest"), "--by fact"),
    (("spend",), "--where %s=agent-fake1" % schema.SUBAGENT_DIM),
    (("spend", "--where", "subagent=agent-fake1"), "--by fact"),
    (("context", "--by", "fact"), None)])
def test_the_hint_follows_the_headline_levers(tmp_path, args, hint):
    out = fx.run_cli(*args, "--root", str(fx.cli_corpus(tmp_path)))[1]
    hints = [line for line in out.splitlines() if line.startswith(render.NEXT)]
    assert hints == ([render.NEXT + hint] if hint else [])
    if hint:  # the last line of the answer, before the tables
        assert fx.sections(out)[1][-1] == hints[0]


def test_under_a_pinned_tool_the_hint_names_its_top_command():
    def fact(command, mass):
        return schema.Fact(schema.INCREMENT, {schema.TOOL_DIM: "Bash", schema.COMMAND_DIM: command},
                           {schema.CONTEXT_DELTA: mass}, None, {}, None)
    sel = SimpleNamespace(facts=[fact("Bash:sed", 30), fact("Bash:cat", 20), fact("Bash:sed", 5)],
                          where=[(schema.TOOL_DIM, "Bash")])
    assert render.next_step(cli.VIEWS["context"], sel, None) == [render.NEXT + "--where command=Bash:sed"]


def test_explain_unassigned_says_what_it_holds_in_each_table():
    code, out, err = fx.run_cli("explain", tables.RESIDUAL_LABEL)
    assert code == 0, err
    for dim in tables.RESIDUAL_NOTES:
        assert "  by %s: %s" % (dim, tables.residual_cases(dim)) in out.splitlines()
