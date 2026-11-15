"""What a first-time reader meets: the scope line first and the default
window, the help that teaches the workflow, the glossary behind ``sa
explain`` and the key, the reading order of the sections, colour only on a
TTY, and home printed as ``~``. Terms come from ``schema.GLOSSARY``."""
import os
import re
import time

import pytest

import fixtures as fx
from sa import cli, corpus, render, schema, tables

CONTEXT = cli.VIEWS["context"]


def _age(path, days):
    stale = time.time() - days * corpus.DAY
    os.utime(path, (stale, stale))


def test_the_first_line_names_the_files_the_default_window_and_the_root(tmp_path):
    """Seven days unless ``--since`` says otherwise; ``all`` reads every
    file, however old. An explicit 7d is not called the default."""
    root = fx.cli_corpus(tmp_path)
    old = sorted(root.rglob("*.jsonl"))[0]
    _age(old, 30)
    n = len(list(root.rglob("*.jsonl")))
    out = fx.run_cli("context", "--root", str(root))[1]
    assert out.splitlines()[0] == "read: %d files modified in the last %gd (default) under %s" % (
        n - 1, cli.DEFAULT_DAYS, root)
    out = fx.run_cli("context", "--root", str(root), "--since", cli.ALL)[1]
    assert out.splitlines()[0] == "read: %d files of any age under %s" % (n, root)
    out = fx.run_cli("context", "--root", str(root), "--since", "%gd" % cli.DEFAULT_DAYS)[1]
    assert out.splitlines()[0] == "read: %d files modified in the last %gd under %s" % (
        n - 1, cli.DEFAULT_DAYS, root)
    code, out, err = fx.run_cli("context", "--root", str(root), "--since", "every")
    assert code == 2 and not out and cli.ALL in err  # the refusal names the escape hatch


def test_home_prints_as_a_tilde(tmp_path, monkeypatch, capsys):
    root = fx.cli_corpus(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cli.main(["context", "--root", str(root)]) == 0
    first = capsys.readouterr().out.splitlines()[0]
    assert first.endswith(" under ~/%s" % root.relative_to(tmp_path).as_posix())
    assert str(tmp_path) not in first
    assert tables.tilde(tmp_path.parent) == str(tmp_path.parent)  # vacuity guard: only under home
    assert tables.tilde(tmp_path) == "~"


def test_sections_read_scope_answer_tables_key_checks(tmp_path):
    root = fx.cli_corpus(tmp_path)
    sections = fx.sections(fx.run_cli("context", "--root", str(root))[1])
    firsts = [s[0] for s in sections]
    assert firsts[0].startswith("read: ") and sections[0][-1].startswith("kept: ")
    assert firsts[1].startswith(CONTEXT.metric + ": ")
    tables_at = [i for i, line in enumerate(firsts) if line.startswith("by ")]
    assert tables_at == list(range(2, 2 + len(CONTEXT.tables)))
    assert firsts[-2].startswith("key (") and firsts[-1].startswith(tables.OK_MARK + " checks: ")
    assert len(sections) == 4 + len(CONTEXT.tables)
    for section in sections[2:-2]:  # no note inside a table: every one is in the key
        assert all(not line.startswith(tables.RESIDUAL_LABEL + ":") for line in section)


def test_the_key_prints_each_note_once_and_marks_the_irreducible_terms(tmp_path):
    root = fx.cli_corpus(tmp_path)
    keyed = fx.key(fx.run_cli("context", "--root", str(root))[1])
    labels = [label for label, _ in keyed]
    assert len(labels) == len(set(labels)) and labels  # vacuity guard: there is a key
    marked = [t for t, e in schema.GLOSSARY.items() if e.marked]
    assert schema.WINDOW_HEAD in marked and schema.RESIDUAL_LABEL in marked
    for label in labels:  # every label opens with a marked term, marked
        term = label.split()[0]
        assert term.endswith(schema.MARKER) and term[:-1] in marked, label


def test_the_share_column_names_its_base(tmp_path):
    """The total when every row has a value; the tokens added when shrink is
    taken out; those with a value when the residual row is too."""
    root = fx.cli_corpus(tmp_path)
    out = fx.run_cli("context", "--root", str(root), "--where", "%s=proj-a" % schema.PROJECT_DIM,
                     "--by", schema.SESSION_DIM)[1]
    assert re.search(r"^by %s\s.*share of [\d,]+ added$" % schema.SESSION_DIM, out, re.M)
    out = fx.run_cli("spend", "--root", str(root), "--by", schema.SESSION_DIM)[1]
    assert re.search(r"^by %s\s.*share of total$" % schema.SESSION_DIM, out, re.M)
    out = fx.run_cli("spend", "--root", str(root), "--by", schema.AGENT_DIM)[1]
    assert re.search(r"^by %s\s.*share of [\d,]+ with an %s$" % (schema.AGENT_DIM, schema.AGENT_DIM),
                     out, re.M)


def test_colour_only_on_a_tty_with_no_color_unset(tmp_path, monkeypatch, capsys):
    root = fx.cli_corpus(tmp_path)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    assert cli._colour()
    cli.main(["context", "--root", str(root)])
    coloured = capsys.readouterr().out
    assert "\033[%sm" % tables.BOLD in coloured and "\033[%sm" % tables.DIM in coloured
    assert "\033[%sm" % tables.GOOD in coloured
    monkeypatch.setenv("NO_COLOR", "1")
    assert not cli._colour()
    cli.main(["context", "--root", str(root)])
    assert "\033[" not in capsys.readouterr().out
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    assert not cli._colour()
    assert "\033[" not in fx.run_cli("context", "--root", str(root))[1]  # a pipe is no TTY
    assert tables.paint("plain") == "plain" and tables.paint(tables.styled("x", tables.DIM)) != "x"


def test_every_declared_term_has_a_glossary_entry_with_a_surprise():
    declared = (list(schema.METRICS) + list(schema.KINDS) + list(schema.DIMENSIONS)
                + list(schema.CAUSES) + list(schema.REASONS)
                + [schema.RESIDUAL_LABEL, schema.EXACT, schema.DRILL])
    assert len(declared) > 20  # vacuity guard
    missing = [t for t in declared if t not in schema.GLOSSARY]
    assert not missing, missing
    for term, entry in schema.GLOSSARY.items():
        assert entry.meaning and entry.surprise, term


def test_explain_prints_one_term_or_all_and_refuses_an_unknown_one():
    code, out, err = fx.run_cli("explain", schema.WINDOW_HEAD + schema.MARKER)  # copied with its marker
    entry = schema.GLOSSARY[schema.WINDOW_HEAD]
    assert code == 0, err
    assert out.splitlines() == ["%s: %s" % (tables.marked(schema.WINDOW_HEAD), entry.meaning),
                                "  surprise: " + entry.surprise]
    code, out, err = fx.run_cli("explain")
    assert code == 0 and len(out.splitlines()) == 2 * len(schema.GLOSSARY)
    code, out, err = fx.run_cli("explain", "bogus")
    assert code == 2 and not out and "unknown term 'bogus'" in err and schema.WINDOW_HEAD in err


def test_top_level_help_teaches_the_views_the_workflow_and_the_flags():
    code, out, err = fx.run_cli("-h")
    assert code == 0, err
    for view, question in cli.QUESTIONS.items():
        assert view in out and question.split(":")[0].split()[0] in out
    workflow = [set(line.split()) for line in out.splitlines() if line.startswith("  sa context")]
    assert len(workflow) == 3  # overview, then --where, then --by
    assert [("--where" in w, "--by" in w) for w in workflow] == [(False, False), (True, False), (True, True)]
    for flag in ("--since", "--where", "--by", "--limit", "--root"):
        assert re.search(r"^  %s " % flag, out, re.M), flag
    assert "sa context --help" in out and "sa explain TERM" in out
    for term in (t for t, e in schema.GLOSSARY.items() if e.marked):
        assert term in out  # the marked terms are named where the marker is explained


@pytest.mark.parametrize("view", list(cli.VIEWS))
def test_view_help_names_each_dimension_with_its_glossary_meaning(view):
    code, out, err = fx.run_cli(view, "-h")
    assert code == 0, err
    for dim in schema.DIMENSIONS:
        assert re.search(r"^  %s\s+%s$" % (dim, re.escape(schema.GLOSSARY[dim].meaning)), out, re.M), dim
    assert render.FACT in out and cli.ALL in out
