"""The ``*`` footnotes and the next-step hint: every term the body marks is
in the key, every key term is marked once in the body, and the hint follows
the headline's levers down to ``--by fact``."""
import re
from types import SimpleNamespace

import pytest

import fixtures as fx
from sa import cli, glossary, render, residual, schema, tables

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
    keyed = [re.match(r"^  (\S+(?: \S+)*?)%s +=" % STAR, line).group(1) for line in key]
    known = {glossary.printed(t) for t in glossary.GLOSSARY}
    spelt = sorted(known | {t.replace("_", " ") for t in known}, key=len, reverse=True)  # as printed
    marked = re.findall(r"(?<![\w-])(%s)s?%s" % ("|".join(map(re.escape, spelt)), STAR), "\n".join(body))
    assert keyed and marked  # vacuity guard
    assert len(re.findall(STAR, "\n".join(body))) == len(marked)  # every marker is on a term
    assert set(marked) == set(keyed) and len(keyed) == len(set(keyed))
    assert all(glossary.key_of(t) in glossary.GLOSSARY for t in keyed)
    once = [t for t in keyed if t != tables.RESIDUAL_LABEL]  # every table labels its residual row
    assert all(len(re.findall(r"(?<!\w)%ss?%s" % (t, STAR), "\n".join(body))) == 1 for t in once)
    assert re.search(r"explain %s$" % re.escape(keyed[0]), next(
        line for line in out.splitlines() if line.startswith(tables.KEY_TITLE)))


@pytest.mark.parametrize("args, hint", [
    (("context",), "--where %s=%s" % (schema.PEAK_DIM, schema.BANDS[-1])),  # the fullest band first
    (("context", "--where", "peak=0-50K"), "--where %s=Bash" % schema.TOOL_DIM),  # one band: no lead
    (("context", "--where", "tool=Bash"), "--by fact"),  # past a drill pin, no band: its command is implied
    (("context", "--where", "command=Bash:pytest"), "--by fact"),  # a command pinned: the leaves next
    (("context", "--where", "peak=200K+", "--where", "tool=Bash"), "--by fact"),  # its command is implied
    (("context", "--where", "peak=200K+", "--where", "command=Bash:pytest"), "--by fact"),
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
                          where=[(schema.TOOL_DIM, "Bash")], drill=[(schema.TOOL_DIM, "Bash")])
    assert render.next_step(cli.VIEWS["context"], sel, None) == [render.NEXT + "--where command=Bash:sed"]


def test_explain_unassigned_says_what_it_holds_in_each_table():
    code, out, err = fx.run_cli("explain", tables.RESIDUAL_LABEL)
    assert code == 0, err
    for dim in residual.RESIDUAL_NOTES:
        assert "  by %s: %s" % (dim, residual.residual_cases(dim)) in out.splitlines()


def test_a_value_named_like_a_term_is_never_marked(tmp_path):
    """Projects named ``unassigned`` and ``ambiguous`` are values: their
    rows take no marker, while the term ``ambiguous`` is still marked
    where the checks print it, and the key holds only what is marked."""
    root = fx.cli_corpus(tmp_path, projects=(tables.RESIDUAL_LABEL, schema.AMBIGUOUS))
    out = fx.run_cli("context", "--root", str(root), "--by", schema.PROJECT_DIM)[1]
    rows = [line for line in out.splitlines()
            if line.split()[:1] in ([tables.RESIDUAL_LABEL], [schema.AMBIGUOUS])]
    assert len(rows) == 2 and not any(glossary.MARKER in row for row in rows)  # vacuity guard: both print
    assert glossary.marked(schema.AMBIGUOUS) in out.splitlines()[-1]  # the term, where it is one
    keyed = [label for label, _ in fx.key(out)]
    assert schema.AMBIGUOUS in keyed and tables.RESIDUAL_LABEL not in keyed
