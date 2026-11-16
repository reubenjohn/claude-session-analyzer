"""The ``*`` footnotes and the next-step hint: every term the body marks is
defined under ``-v``, every term ``-v`` defines is marked once in the body,
and the hint follows the headline's levers down to ``by change``."""
import re
from types import SimpleNamespace

import pytest

import fixtures as fx
from sa import cli, glossary, grammar, notes, render, residual, schema

STAR = re.escape(glossary.MARKER)
CATCH_ALL = re.compile(r" \(%s \w+\)$" % grammar.BY)  # a catch-all row's entry: ``no tool (by tool)``


def _split(out):
    """The body and the ``-v`` block's marked words, as -v prints them."""
    block = fx.verbose(out)
    body = out.replace("\n".join(block), "")
    at = [i for i, line in enumerate(block) if line.startswith(notes.HEAD)][-1]
    words = fx.key("\n".join(block[at:]))
    return body, [label for label, _ in words if not CATCH_ALL.search(label)]


@pytest.mark.parametrize("args", [("context",), ("spend",), ("context", "tool=Bash"),
                                  ("context", "by", "change"), ("spend", "by", "subagent")])
def test_the_marked_terms_and_the_defined_terms_are_one_set(tmp_path, args):
    out = fx.run_cli(*args, "--root", str(fx.cli_corpus(tmp_path)), "-v")[1]
    body, keyed = _split(out)
    known = {glossary.printed(t) for t in glossary.GLOSSARY}
    spelt = sorted(known | {t.replace("_", " ") for t in known}, key=len, reverse=True)  # as printed
    marked = re.findall(r"(?<![\w-])(%s)s?%s" % ("|".join(map(re.escape, spelt)), STAR), body)
    assert keyed and marked  # vacuity guard
    assert len(re.findall(STAR, body)) == len(marked)  # every marker is on a term
    assert set(marked) == set(keyed) and len(keyed) == len(set(keyed))
    assert all(glossary.key_of(t) in glossary.GLOSSARY for t in keyed)
    assert all(len(re.findall(r"(?<!\w)%ss?%s" % (re.escape(t), STAR), body)) == 1 for t in keyed)


def _next(view, root, by=None, add=(), pins=()):
    return render.NEXT + grammar.Invocation(view, tuple(pins), None, str(root)).command(by=by, add=add)


CHANGE = grammar.FACTS["context"]


@pytest.mark.parametrize("args, by, add", [
    (("context",), None, [(schema.TOOL_DIM, "Bash")]),  # the headline's own walk: its top tool
    (("context", "peak=0-50K"), None, [(schema.TOOL_DIM, "Bash")]),
    (("context", "tool=Bash"), CHANGE, []),  # past a drill pin, no band: its command is implied
    (("context", "command=Bash:pytest"), CHANGE, []),  # a command pinned: the leaves next
    (("context", "peak=200K+", "tool=Bash"), CHANGE, []),  # its command is implied
    (("context", "peak=200K+", "command=Bash:pytest"), CHANGE, []),
    (("spend",), None, [(schema.SUBAGENT_DIM, "agent-fake1")]),
    (("spend", "subagent=agent-fake1"), grammar.FACTS["spend"], []),
    (("context", "by", CHANGE), CHANGE, [(schema.WINDOW_DIM, "first")]),  # the window printed first
    (("context", "by", CHANGE, "window=%s" % fx.window_value("proj-a/sess-0001.jsonl")), None, None)])
def test_the_hint_follows_the_headline_levers(tmp_path, args, by, add):
    """The headline's walk, then the facts, then the window printed first;
    one window's facts are the end of the path."""
    root = fx.cli_corpus(tmp_path)
    out = fx.run_cli(*args, "--root", str(root))[1]
    hint = fx.hint(out)
    pins = [tuple(a.split("=", 1)) for a in args[1:] if "=" in a]
    if add and add[0][1] == "first":
        add = [(schema.WINDOW_DIM, re.search(r"^\S+\.jsonl  %s=(\w+)" % schema.WINDOW_DIM, out, re.M).group(1))]
    assert hint == (_next(args[0], root, by, add, pins) if add is not None else None)
    if add is not None:  # the last line of the answer, before the tables; it pastes and runs
        assert fx.joined("\n".join(fx.sections(out)[1])).splitlines()[-1] == hint
        assert fx.run_cli(*hint[len(render.NEXT + grammar.PROG) + 1:].split())[0] == 0


def test_the_help_path_is_the_hint_chain():
    """The -h path pins what each hint pins, in order: the view's levers,
    then the facts."""
    view = cli.VIEWS["context"]
    path = [line.split("  ")[1] for line in grammar.HELP.splitlines()
            if line.startswith("  %s context" % grammar.PROG)]
    pinned = []
    for step in path:
        pinned += [w.split("=")[0] for w in step.split() if "=" in w and w.split("=")[0] not in pinned]
    chain = list(view.levers)
    assert len(pinned) >= 2 and pinned == chain[:len(pinned)]  # vacuity guard: the path pins
    assert any("%s %s" % (grammar.BY, CHANGE) in step for step in path)


def test_under_a_pinned_tool_the_hint_names_its_top_command():
    def fact(command, mass):
        return schema.Fact(schema.INCREMENT, {schema.TOOL_DIM: "Bash", schema.COMMAND_DIM: command},
                           {cli.VIEWS["context"].metric: mass}, None, {}, None)
    sel = SimpleNamespace(facts=[fact("Bash:sed", 30), fact("Bash:cat", 20), fact("Bash:sed", 5)],
                          where=[(schema.TOOL_DIM, "Bash")], drill=[(schema.TOOL_DIM, "Bash")], calls=1)
    inv = grammar.Invocation("context", ((schema.TOOL_DIM, "Bash"),))
    assert render.next_step(cli.VIEWS["context"], sel, None, inv) == [
        render.NEXT + inv.command(add=[(schema.COMMAND_DIM, "Bash:sed")])]


@pytest.mark.parametrize("dim", [d for d, (_, cases) in residual.RESIDUAL_NOTES.items() if cases])
def test_v_says_what_a_catch_all_row_can_hold(tmp_path, dim):
    out = fx.run_cli("context", "--root", str(fx.cli_corpus(tmp_path)), grammar.BY, dim, "-v")[1]
    assert re.search(r"^%s%s?\s" % (re.escape(residual.label(dim)), STAR), out, re.M)  # vacuity guard: it prints
    assert dict(fx.key(out))["%s (%s %s)" % (residual.label(dim), grammar.BY, dim)] == residual.residual_cases(dim)


def test_a_value_named_like_a_term_is_never_marked(tmp_path):
    """Projects named ``window`` and ``ambiguous`` are values: their rows
    take no marker, while the term ``ambiguous`` is still marked where the
    cause table prints it."""
    root = fx.cli_corpus(tmp_path, projects=(schema.WINDOW_DIM, schema.AMBIGUOUS))
    out = fx.run_cli("context", "--root", str(root), grammar.BY, schema.PROJECT_DIM, "-v")[1]
    rows = [line for line in out.splitlines()
            if line.split()[:1] in ([schema.WINDOW_DIM], [schema.AMBIGUOUS])]
    assert len(rows) == 2 and not any(glossary.MARKER in row for row in rows)  # vacuity guard: both print
    default = fx.run_cli("context", "--root", str(root))[1]
    assert re.search(r"^%s\s" % re.escape(glossary.marked(schema.AMBIGUOUS)), default, re.M)  # the term, a cause
