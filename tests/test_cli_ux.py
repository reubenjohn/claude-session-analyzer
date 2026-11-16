"""What a first-time reader meets: the scope line first and the default
window, the help that teaches the workflow, the glossary behind ``-v``,
the reading order of the sections (colour: ``test_style``),
and home printed as ``~``. Terms come from ``glossary.GLOSSARY``."""
import os
import re
import time
from pathlib import Path

import pytest

import fixtures as fx
from sa import checks, cli, corpus, glossary, grammar, headline, notes, render, schema, tables

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
    out = fx.joined(fx.run_cli("context", "--root", str(root))[1])  # a long root: its own line
    rest = "; 1 with no call"  # the one read line: the file with no call is said, it is no window
    assert out.splitlines()[0] == "read: %d files from the last %gd (default) under %s%s" % (
        n - 1, grammar.DEFAULT_SINCE, root, rest)
    out = fx.joined(fx.run_cli("context", "--root", str(root), "--since", grammar.ALL)[1])
    assert out.splitlines()[0] == "read: %d files of any age under %s%s" % (n, root, rest)
    out = fx.joined(fx.run_cli("context", "--root", str(root), "--since", "%gd" % grammar.DEFAULT_SINCE)[1])
    assert out.splitlines()[0] == "read: %d files from the last %gd under %s%s" % (
        n - 1, grammar.DEFAULT_SINCE, root, rest)
    code, out, err = fx.run_cli("context", "--root", str(root), "--since", "every")
    assert code == 2 and not out and grammar.ALL in err  # the refusal names the escape hatch


def test_home_prints_as_a_tilde(tmp_path, monkeypatch, capsys):
    root = fx.cli_corpus(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cli.main(["context", "--root", str(root)]) == 0
    out = capsys.readouterr().out
    assert " under ~/%s;" % root.relative_to(tmp_path).as_posix() in out.splitlines()[0]
    assert str(tmp_path) not in out  # the next command's --root too
    assert " --root ~/%s" % root.relative_to(tmp_path).as_posix() in out
    assert tables.tilde(tmp_path.parent) == str(tmp_path.parent)  # vacuity guard: only under home
    assert tables.tilde(tmp_path) == "~"


def test_sections_read_scope_answer_tables_also_footer_checks(tmp_path):
    root = fx.cli_corpus(tmp_path)
    out = fx.run_cli("context", "--root", str(root))[1]
    sections = fx.sections(fx.joined(out))
    firsts = [s[0] for s in sections]
    assert firsts[0].startswith("read: ") and sections[0][1].startswith("in view: ")
    assert firsts[1].startswith(fx.total_line(CONTEXT.metric)) and fx.hint(out)
    assert fx.joined("\n".join(sections[1])).splitlines()[-1] == fx.hint(out)  # the answer ends with the next step
    tables_at = [i for i, line in enumerate(firsts) if line.startswith("by ")]
    assert tables_at == list(range(2, 2 + len(tables_at))) and tables_at  # contiguous, non-empty
    for dim in CONTEXT.tables:  # each printed, or relabelled under the table it repeats
        assert re.search(r"^by (?:[\w /]+, )*%s[\s:,]" % dim, "\n".join(sum(sections[2:2 + len(tables_at)], [])), re.M), dim
    last = fx.joined("\n".join(sections[-1])).splitlines()  # the ways deeper as commands, then the checks
    at = next(i for i, l in enumerate(last) if l.startswith(checks.OK))
    commands = [l for l in last[:at] if l.startswith(grammar.PROG)]
    assert len(commands) == 2 and fx.also(out) and commands[1] == fx.pointer_v(out).split("  ")[0]
    assert len(sections) == 3 + len(tables_at)
    assert all(len(line) <= tables.WIDTH for section in sections for line in section
               if "/pytest-" not in line)  # the read line and the next command name this test's root


def test_the_v_footer_says_what_v_prints_and_v_prints_it_in_its_place(tmp_path):
    """The footer counts the figures, the marked words and the lines ``-v``
    adds; ``-v`` prints exactly that block where the footer was. Each
    marked word is a glossary term, printed bare, once."""
    root = fx.cli_corpus(tmp_path)
    out = fx.run_cli("context", "--root", str(root))[1]
    verbose = fx.run_cli("context", "--root", str(root), "-v")[1]
    footer = fx.pointer_v(out)
    m = re.match(r"^%s -v +how it's computed and checked, what \* marks \(\+(\d+) lines\)$" % (
        re.escape(grammar.run("context", "--root", str(root)))), footer)
    lines = int(m.group(1))
    block, worked = fx.verbose(verbose), fx.worked(verbose)
    assert len(verbose.splitlines()) - len(out.splitlines()) == lines  # what it costs, exactly
    assert len(block) + worked.count("\n") > lines and footer not in verbose and worked  # less the pointer
    ways = fx.sections(out)[-1]  # the ways deeper, then the checks
    ways = ways[:next(i for i, l in enumerate(ways) if l.startswith(checks.OK))]
    raw = "\n".join(ways[max(i for i, l in enumerate(ways) if l.startswith(grammar.PROG)):])  # as printed
    assert verbose.replace("\n".join(block), raw).replace(worked, "") == out  # in place, then the checks worked
    heads = [i for i, l in enumerate(block) if l.startswith(notes.HEAD)]
    assert len(heads) == 2  # how the figures are computed; what the marked words mean
    entries = [l for l in block if not l.startswith((notes.HEAD, notes.INDENT))]  # each opens an entry
    figures = len([l for l in block[:heads[1]] if not l.startswith((notes.HEAD, notes.INDENT))])
    words = len([l for l in entries[figures:] if "(%s " % grammar.BY not in l])
    keyed = fx.key(verbose)
    terms = [label for label, _ in keyed[figures:] if "(%s " % grammar.BY not in label]
    assert len(terms) == words == len(set(terms)) and terms  # vacuity guard: there are words
    assert all(glossary.key_of(t) in glossary.GLOSSARY and glossary.MARKER not in t for t in terms)
    assert all(glossary.MARKER + " " not in l for l in block)


def test_the_share_column_base_is_on_screen(tmp_path):
    """Every table with a share prints its ``= 100%`` row, the sum of its
    rows in a share: per call, before shrink; without the catch-all row."""
    root = fx.cli_corpus(tmp_path)
    for args in (("context", "%s=proj-a" % schema.PROJECT_DIM, "by", schema.SESSION_DIM),
                 ("context", "%s=Bash" % schema.TOOL_DIM, "by", schema.SESSION_DIM),
                 ("spend", "by", schema.SESSION_DIM), ("spend", "by", schema.SUBAGENT_DIM),
                 ("context", "by", schema.TOOL_DIM)):
        out = fx.run_cli(args[0], "--root", str(root), *args[1:])[1]
        table = fx.sections(out)[2]
        assert table[0].startswith("by %s" % args[-1]) and table[0].endswith(" share"), args
        rows = [l.split() for l in table[1:] if re.match(r"^\S+\s+[\d,]+\s.*%$", l)]
        (base,) = [l for l in table if l.startswith(tables.BASE_LABEL)]
        mass = int(base[len(tables.BASE_LABEL):].split()[0].replace(",", ""))
        assert rows and abs(sum(int(r[1].replace(",", "")) for r in rows) - mass) <= len(rows), args


def test_every_declared_term_has_a_glossary_entry_with_a_surprise():
    declared = (list(schema.METRICS) + list(schema.KINDS) + list(schema.DIMENSIONS)
                + list(schema.CAUSES) + list(schema.REASONS))
    assert len(declared) > 20  # vacuity guard
    missing = [t for t in declared if t not in glossary.GLOSSARY]
    assert not missing, missing
    for term, entry in glossary.GLOSSARY.items():
        assert entry.meaning and entry.surprise, term


def test_v_defines_a_marked_word_from_the_glossary_and_explain_is_refused_naming_v(tmp_path):
    root = fx.cli_corpus(tmp_path)
    out = fx.run_cli("context", "--root", str(root), "-v")[1]
    entry = glossary.GLOSSARY[schema.STARTING_CONTEXT]
    text = dict(fx.key(out))[glossary.printed(schema.STARTING_CONTEXT).replace("_", " ")]
    assert text == "%s %s" % (entry.meaning, entry.surprise)  # the sentence, then its edge cases
    assert all(len(l) <= tables.WIDTH for l in fx.verbose(out))
    code, said, err = fx.run_cli("explain", schema.STARTING_CONTEXT)
    assert code == 2 and not said and grammar.RETIRED["explain"] in err and len(err.splitlines()) <= 2


def test_top_level_help_teaches_the_views_the_workflow_and_the_flags():
    """-h layers: the two questions, spend first, then context with its
    premise (cost aside); the broad-to-narrow path, a pin defined at its
    first use; a few flags. No arguments prints it too."""
    code, out, err = fx.run_cli("-h")
    assert code == 0, err
    assert out.rstrip("\n") == grammar.HELP and fx.run_cli()[1] == out
    questions = [re.search(r"^  (%s)  .+\?" % v, out, re.M) for v in grammar.VIEWS]
    assert all(questions) and len(questions) == len(cli.VIEWS) == 2  # vacuity guard: both asked
    assert [q.group(1) for q in sorted(questions, key=lambda q: q.start())] == ["spend", "context"]
    asked = {q.group(1): q.group(0) for q in questions}
    assert "Cost aside" in asked["context"] and "aside" not in asked["spend"]  # the premise is context's
    assert "(DIM=VALUE)" in out  # pin is defined at its first use
    assert "%s context %s=Bash %s=Bash:" % (cli.PROG, schema.TOOL_DIM, schema.COMMAND_DIM) in out  # the levers
    assert "by %s" % grammar.FACTS["context"] in out and " -v " in out
    for flag in ("--since", "--root", "--color", "-v"):
        assert flag in out, flag
    for retired in grammar.RETIRED:
        assert retired not in out, retired
    assert len(out.splitlines()) <= 25  # UX_PRINCIPLES budget


@pytest.mark.parametrize("view", list(cli.VIEWS))
def test_view_help_is_the_one_help(view):
    code, out, err = fx.run_cli(view, "-h")
    assert code == 0 and out == fx.run_cli("-h")[1], err


def test_an_encoded_home_prints_as_a_tilde_and_selects_as_printed(tmp_path, monkeypatch, capsys):
    """A project directory and locator start with home as Claude Code
    encodes it; both print it as ``~``, and a pin takes the label."""
    monkeypatch.setenv("HOME", str(tmp_path))
    encoded = tables._encoded_home() + "-work"
    root = fx.corpus(tmp_path, {encoded + "/sess-0001.jsonl": fx.window_records()})
    assert cli.main(["context", "--root", str(root), "by", schema.PROJECT_DIM]) == 0
    out = capsys.readouterr().out
    assert encoded in "".join(p.name for p in root.iterdir())  # vacuity guard: the name is encoded
    assert encoded not in out and re.search(r"^~-work\s", out, re.M)
    assert out.count(tables.HOME_NOTE) == 1  # J6: the ~ read once, where it prints
    assert cli.main(["context", "--root", str(root), "by", grammar.FACTS["context"]]) == 0
    out = capsys.readouterr().out  # a file prints as on disk, under the directory named once: it opens
    (listed,) = fx.listed(out)  # the directory as deep as its line holds, the rest on the path: it opens
    assert Path(listed.replace("~", str(tmp_path), 1)).resolve() == (root / encoded / "sess-0001.jsonl").resolve()
    assert not listed.lstrip().startswith("-")  # however deep the split, never read as a flag
    assert cli.main(["context", "--root", str(root), "%s=~-work" % schema.PROJECT_DIM]) == 0
    assert "\nin view where %s=~-work: " % schema.PROJECT_DIM in capsys.readouterr().out
    # A refusal names the nearest value with home as ~ too.
    assert cli.main(["context", "--root", str(root), "%s=~-wrk" % schema.PROJECT_DIM]) == 2
    err = capsys.readouterr().err
    assert "nearest: %s" % grammar.quote("%s=~-work" % schema.PROJECT_DIM) in err and encoded not in err and str(tmp_path) not in err


def test_the_answer_and_checks_words_each_explain(tmp_path):
    """Unmarked words a reader meets in the default output are explained
    where they print or under ``-v``: a cause's gloss beside its row, the
    checks' calls by their working; growth keeps its glossary entry."""
    root = fx.cli_corpus(tmp_path)
    out = fx.run_cli("context", "--root", str(root))[1]
    for word in (glossary.GROWTH, schema.REPLIES):
        assert re.search(r"(?<![\w_])%s(?![\w_])" % re.escape(word), out), word  # vacuity guard: printed
    assert re.search(r"^%s\s.*%%  %s$" % (schema.REPLIES, re.escape(render.GLOSSES[schema.REPLIES])), out, re.M)
    verbose = fx.run_cli("context", "--root", str(root), "-v")[1]
    assert "\n  18 calls after their window's first = 21 calls - 3 windows, " in fx.worked(verbose)
    assert headline.WITHIN in out and "(of which)" in glossary.GLOSSARY[glossary.GROWTH].meaning


def test_the_peak_guidance_says_where_to_start_with_no_verdict_number():
    """D-NO-VERDICT: no rot threshold is measured, so the guidance has no figure."""
    assert glossary.FULLEST in glossary.GLOSSARY[schema.PEAK_DIM].surprise
    assert glossary.FULLEST and not re.search(r"\d", glossary.FULLEST)


def test_v_says_how_to_pin_a_window(tmp_path):
    root = fx.cli_corpus(tmp_path)
    value = next(f.dims[schema.WINDOW_DIM] for f in fx.load_facts(root)[1])
    assert len(value) == 8 and int(value, 16) >= 0  # vacuity guard: the value is 8 hex characters
    out = fx.run_cli("context", "--root", str(root), "-v")[1]
    assert re.search(r"\b%s=[0-9a-f]{8}\b" % schema.WINDOW_DIM, dict(fx.key(out))[schema.WINDOW_DIM])