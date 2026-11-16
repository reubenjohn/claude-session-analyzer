"""What a first-time reader meets: the scope line first and the default
window, the help that teaches the workflow, the glossary behind ``sa
explain`` and the key, the reading order of the sections (colour: ``test_style``),
and home printed as ``~``. Terms come from ``glossary.GLOSSARY``."""
import os
import re
import time

import pytest

import fixtures as fx
from sa import cli, corpus, glossary, render, residual, schema, tables

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
    rest = ", 0 lines skipped, 0 duplicates excluded"  # the one read line
    assert out.splitlines()[0] == "read: %d files modified in the last %gd (default) under %s%s" % (
        n - 1, cli.DEFAULT_DAYS, root, rest)
    out = fx.run_cli("context", "--root", str(root), "--since", cli.ALL)[1]
    assert out.splitlines()[0] == "read: %d files of any age under %s%s" % (n, root, rest)
    out = fx.run_cli("context", "--root", str(root), "--since", "%gd" % cli.DEFAULT_DAYS)[1]
    assert out.splitlines()[0] == "read: %d files modified in the last %gd under %s%s" % (
        n - 1, cli.DEFAULT_DAYS, root, rest)
    code, out, err = fx.run_cli("context", "--root", str(root), "--since", "every")
    assert code == 2 and not out and cli.ALL in err  # the refusal names the escape hatch


def test_home_prints_as_a_tilde(tmp_path, monkeypatch, capsys):
    root = fx.cli_corpus(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cli.main(["context", "--root", str(root)]) == 0
    first = capsys.readouterr().out.splitlines()[0]
    assert " under ~/%s, " % root.relative_to(tmp_path).as_posix() in first
    assert str(tmp_path) not in first
    assert tables.tilde(tmp_path.parent) == str(tmp_path.parent)  # vacuity guard: only under home
    assert tables.tilde(tmp_path) == "~"


def test_sections_read_scope_answer_tables_key_checks(tmp_path):
    root = fx.cli_corpus(tmp_path)
    sections = fx.sections(fx.run_cli("context", "--root", str(root))[1])
    firsts = [s[0] for s in sections]
    assert firsts[0].startswith("read: ") and sections[0][1].startswith("in view: ")
    assert firsts[1].startswith(fx.total_line(CONTEXT.metric))
    tables_at = [i for i, line in enumerate(firsts) if line.startswith("by ")]
    assert tables_at == list(range(2, 2 + len(tables_at))) and tables_at  # contiguous, non-empty
    for dim in CONTEXT.tables:  # each printed, or relabelled under the table it repeats
        assert re.search(r"^by (?:[\w /]+, )*%s[\s:,]" % dim, "\n".join(sum(sections[2:2 + len(tables_at)], [])), re.M), dim
    assert firsts[-2].startswith(tables.KEY_TITLE) and firsts[-1].startswith(tables.OK_MARK + " checks: ")
    assert len(sections) == 4 + len(tables_at)
    for section in sections[2:-2]:  # no note inside a table: every one is in the key
        assert all(not line.startswith(tables.RESIDUAL_LABEL + ":") for line in section)


def test_the_key_prints_each_note_once_and_names_the_command_for_its_first_term(tmp_path):
    """Each label opens with a glossary term, printed bare, aligned on `` = ``; the header's command explains the first."""
    root = fx.cli_corpus(tmp_path)
    out = fx.run_cli("context", "--root", str(root))[1]
    keyed = fx.key(out)
    labels = [label for label, _ in keyed]
    assert len(labels) == len(set(labels)) and labels  # vacuity guard: there is a key
    terms = labels
    assert all(glossary.key_of(t) in glossary.GLOSSARY and glossary.MARKER not in t for t in terms)
    head = next(line for line in out.splitlines() if line.startswith(tables.KEY_TITLE))
    command = head.split(": ", 1)[1]
    assert command == "%s explain %s" % (cli.PROG, terms[0])
    code, said, err = fx.run_cli(*command.split()[3:])
    assert code == 0 and said.startswith(glossary.marked(glossary.key_of(terms[0])) + ": "), err
    key = next(sec for sec in fx.sections(out) if sec[0].startswith(tables.KEY_TITLE))[1:]
    assert len({line.index(" = ") for line in key}) == 1 and len(key) > 1


def test_the_share_column_names_its_base(tmp_path):
    """The total (per call, the average) when every row has a value; per
    call, the average before shrink when shrink is taken out; those with a
    value when the residual row is too."""
    root = fx.cli_corpus(tmp_path)
    out = fx.run_cli("context", "--root", str(root), "--where", "%s=proj-a" % schema.PROJECT_DIM,
                     "--by", schema.SESSION_DIM)[1]
    assert re.search(r"^by %s\s.*share of [\d,]+ before shrink$" % schema.SESSION_DIM, out, re.M)
    out = fx.run_cli("context", "--root", str(root), "--where", "%s=Bash" % schema.TOOL_DIM,
                     "--by", schema.SESSION_DIM)[1]
    assert re.search(r"^by %s\s.*share of average$" % schema.SESSION_DIM, out, re.M)
    out = fx.run_cli("spend", "--root", str(root), "--by", schema.SESSION_DIM)[1]
    assert re.search(r"^by %s\s.*share of total$" % schema.SESSION_DIM, out, re.M)
    out = fx.run_cli("spend", "--root", str(root), "--by", schema.SUBAGENT_DIM)[1]
    assert re.search(r"^by %s\s.*share of [\d,]+ \(all but unassigned\)$" % schema.SUBAGENT_DIM,
                     out, re.M)


def test_every_declared_term_has_a_glossary_entry_with_a_surprise():
    declared = (list(schema.METRICS) + list(schema.KINDS) + list(schema.DIMENSIONS)
                + list(schema.CAUSES) + list(schema.REASONS)
                + [glossary.RESIDUAL_LABEL, glossary.EXACT, glossary.DRILL])
    assert len(declared) > 20  # vacuity guard
    missing = [t for t in declared if t not in glossary.GLOSSARY]
    assert not missing, missing
    for term, entry in glossary.GLOSSARY.items():
        assert entry.meaning and entry.surprise, term


def test_explain_prints_one_term_or_all_and_refuses_an_unknown_one():
    code, out, err = fx.run_cli("explain", schema.STARTING_CONTEXT + glossary.MARKER)  # copied with its marker
    entry = glossary.GLOSSARY[schema.STARTING_CONTEXT]
    assert code == 0, err
    assert out.splitlines() == ["%s: %s" % (tables.marked(schema.STARTING_CONTEXT), entry.meaning),
                                "  surprise: " + entry.surprise]
    code, out, err = fx.run_cli("explain")
    assert code == 0 and len(out.splitlines()) == 2 * len(glossary.GLOSSARY) + len(residual.RESIDUAL_NOTES)
    code, out, err = fx.run_cli("explain", "bogus")
    assert code == 2 and not out and "unknown term 'bogus'" in err and schema.STARTING_CONTEXT in err


def test_top_level_help_teaches_the_views_the_workflow_and_the_flags():
    code, out, err = fx.run_cli("-h")
    assert code == 0, err
    for view, question in cli.QUESTIONS.items():
        assert view in out and question.split(":")[0].split()[0] in out
    steps = [line.split(cli.PROG, 1)[1].split() for line in out.replace("\\\n", "").splitlines()
             if line.startswith("  ") and " %s context" % cli.PROG in line]
    workflow = [set(step) for step in steps]
    assert len(workflow) == 4  # is it a problem, what, where, what to fix
    assert [("--where" in w, "--by" in w) for w in workflow] == [(False, False), (True, False), (True, True),
                                                                (True, True)]
    pin = "%s=%s" % (schema.PEAK_DIM, schema.BANDS[-1])
    assert all(pin in w for w in workflow[1:]) and "%s=Bash:cat" % schema.COMMAND_DIM in workflow[-1]  # kept
    assert "--where %s=%s" % (schema.PEAK_DIM, schema.BANDS[-1]) in out  # the path leads with the fullest band
    for flag in ("--since", "--where", "--by", "--limit", "--root"):
        assert re.search(r"^  %s " % flag, out, re.M), flag
    assert "%s context --help" % cli.PROG in out and "%s explain TERM" % cli.PROG in out
    (named,) = [line for line in out.splitlines() if line.startswith("Marked %s" % glossary.MARKER)]
    marked = [t for t, e in glossary.GLOSSARY.items() if e.marked]
    starts = [t for t in marked if t in schema.STARTS]
    assert starts  # vacuity guard: a start value is a marked term, never named here as printed
    for term in marked:  # each as printed, spaces for underscores, as the key spells it
        spelt = glossary.printed(term).replace("_", " ")
        assert (re.search(r"[ :]%s[,;.]" % re.escape(spelt), named) is None) == (term in starts), term


@pytest.mark.parametrize("view", list(cli.VIEWS))
def test_view_help_names_each_dimension_with_its_glossary_meaning(view):
    code, out, err = fx.run_cli(view, "-h")
    assert code == 0, err
    for dim in schema.DIMENSIONS:
        assert re.search(r"^  %s\s+%s$" % (dim, re.escape(glossary.GLOSSARY[dim].meaning)), out, re.M), dim
    assert render.FACT in out and cli.ALL in out


def test_an_encoded_home_prints_as_a_tilde_and_selects_as_printed(tmp_path, monkeypatch, capsys):
    """A project directory and locator start with home as Claude Code
    encodes it; both print it as ``~``, and ``--where`` takes the label."""
    monkeypatch.setenv("HOME", str(tmp_path))
    encoded = tables._encoded_home() + "-work"
    root = fx.corpus(tmp_path, {encoded + "/sess-0001.jsonl": fx.window_records()})
    assert cli.main(["context", "--root", str(root), "--by", schema.PROJECT_DIM]) == 0
    out = capsys.readouterr().out
    assert encoded in "".join(p.name for p in root.iterdir())  # vacuity guard: the name is encoded
    assert encoded not in out and re.search(r"^~-work\s", out, re.M)
    leaves = fx.run_cli("context", "--root", str(root), "--by", "fact", "--limit", "1")[1]
    assert re.search(r"^\s+[\d,]+\s+[\d,]+  ~-work/sess-0001\.jsonl:\d+ ", leaves, re.M)
    assert cli.main(["context", "--root", str(root), "--where", "%s=~-work" % schema.PROJECT_DIM]) == 0
    assert "\nin view where %s=~-work: " % schema.PROJECT_DIM in capsys.readouterr().out
    # A refusal names the values present with home as ~ too.
    assert cli.main(["context", "--root", str(root), "--where", "%s=nope" % schema.PROJECT_DIM]) == 2
    err = capsys.readouterr().err
    assert "present: ~-work" in err and encoded not in err and str(tmp_path) not in err


def test_the_answer_and_checks_words_each_explain(tmp_path):
    """Unmarked words a reader meets in the default output still have an
    entry: growth (and its arrow), replies, the checks' gaps."""
    out = fx.run_cli("context", "--root", str(fx.cli_corpus(tmp_path)))[1]
    for word in (glossary.GROWTH, schema.REPLIES, glossary.printed(glossary.GAP)):
        assert re.search(r"(?<![\w_])%s(?![\w_])" % re.escape(word), out), word  # vacuity guard: printed
        code, said, err = fx.run_cli("explain", word)
        assert code == 0 and said.startswith(word + ":"), err
    assert " → " in out and "→" in glossary.GLOSSARY[glossary.GROWTH].meaning
