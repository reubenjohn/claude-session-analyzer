"""The per-screen budgets of ``references/UX_PRINCIPLES.md`` (principle 2,
Legible: attention is the budget) and mechanical instances of principle 1
(Learnable: whatever the output names is valid input, verbatim).

Budgets, hard gates: the default ``context`` on the fixture corpus (46 lines,
3,228 chars: D-OUTPUT-CAP, ``test_examples``), ``-h`` (25 lines), one term's
``-v`` explanation (6 lines), an error (2 lines), any line (100 columns), and
no line printed whatever is asked. P1: every suggested command runs, every
row label pins, every ``+N more`` command shows N more rows.

Three corpora under throwaway HOMEs, so the root prints as ``~``: the
README's fixture (``scripts/resync_examples.build``), ``corpora.wide``, whose
default tables are cut, and ``corpora.realistic``, a real week's shape, on
which the default screens are held to the same budget."""
import importlib.util
import re
import shlex
import subprocess
import sys
from functools import lru_cache

import pytest

import corpora
import fixtures as fx
import test_examples
from sa import glossary, grammar, notes, render, residual, schema, tables

PROG = glossary.PROG
CONTEXT, SPEND = grammar.VIEWS[1], grammar.VIEWS[0]
HELP_LINES, TERM_LINES, ERROR_LINES = 25, 6, 2
FOOTER = re.compile(r"\(\+(\d+) lines?\)")
HEADER = re.compile(r"^%s (\w+)  " % grammar.BY)  # a table's header: ``by DIM``, then its columns
FIGURE = re.compile(r"^(-?[\d,]+|-)$")
MORE = re.compile(r"^\+([\d,]+) more$")
SHRINK = schema.SHRINK


def _load_resync():
    spec = importlib.util.spec_from_file_location("resync_examples", str(test_examples.SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def homes(tmp_path_factory):
    fixture = tmp_path_factory.mktemp("fixture").resolve()
    _load_resync().build(fixture)
    homes = {"fixture": str(fixture)}
    for name in ("wide", "realistic"):
        home = tmp_path_factory.mktemp(name).resolve()
        getattr(corpora, name)(home)
        homes[name] = str(home)
    return homes


@lru_cache(maxsize=None)
def sa(home, *args):
    """``python3 -m sa ARGS`` with HOME at ``home``: (exit, stdout, stderr)."""
    done = subprocess.run([sys.executable, "-m", "sa"] + list(args), cwd=str(fx.REPO),
                          env={"HOME": home, "PATH": "/usr/bin:/bin"},
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return done.returncode, done.stdout, done.stderr


def ok(home, *args):
    code, out, err = sa(home, *args)
    assert code == 0, (args, out, err)
    return out


def sections(out):
    return [s.splitlines() for s in out.rstrip("\n").split("\n\n")]


def parsed_tables(out):
    """Every table on screen: (dim, [row label, ...]), every row: its text up
    to the first run of two spaces, then a figure (a table's note lines
    carry none)."""
    found = []
    for section in sections(out):
        for i, line in enumerate(section):
            m = HEADER.match(line)
            if m and m.group(1) in schema.DIMENSIONS:
                labels = []
                for row in section[i + 1:]:
                    if HEADER.match(row):
                        break
                    cells = re.split(r"\s{2,}", row)
                    if not row.startswith(" ") and len(cells) > 1 and FIGURE.match(cells[1]):
                        labels.append(cells[0])
                found.append((m.group(1), labels))
    return found


def suggested(text):
    """Every command a screen suggests: from ``python3 -m sa`` to the line's
    end or its next run of two spaces (the ``-h`` examples' gloss)."""
    lines = [ERROR_HEAD.sub("", line) for line in text.splitlines() if not line.startswith("usage:")]
    return [re.split(r"\s{2,}", line[line.index(PROG):])[0] for line in lines if PROG in line]


ERROR_HEAD = re.compile(r"^%s( \w+)?: error: " % re.escape(PROG))  # ``cli.refuse``'s, no command


def runs(home, command):
    words = shlex.split(command)
    assert words[:len(PROG.split())] == PROG.split(), command
    return sa(home, *words[len(PROG.split()):])


# Every screen of the matrix: the default views, pins, every table, the facts, -v.
def matrix():
    every = [(v,) for v in grammar.VIEWS] + [(v, "-v") for v in grammar.VIEWS]
    for view in grammar.VIEWS:
        carried = schema.KIND_DIMENSIONS[grammar.carrier(view)]
        every += [(view, grammar.BY, dim) for dim in carried]
        every += [(view, grammar.BY, grammar.FACTS[view]), (view, grammar.BY, grammar.FACTS[view], "-v")]
    every += [(CONTEXT, "%s=%s" % (schema.PEAK_DIM, schema.BANDS[-1])),
              (CONTEXT, "%s=Bash" % schema.TOOL_DIM), (CONTEXT, "%s=Bash" % schema.TOOL_DIM, "-v"),
              (CONTEXT, "%s=%s" % (schema.TOOL_DIM, residual.label(schema.TOOL_DIM))),
              (SPEND, "%s=%s" % (schema.SUBAGENT_DIM, residual.label(schema.SUBAGENT_DIM)))]
    return every


SCREENS = [(corpus, args) for corpus in ("fixture", "wide", "realistic") for args in matrix()]


@pytest.mark.parametrize("corpus", ["fixture", "realistic"])
@pytest.mark.parametrize("view", grammar.VIEWS)
def test_the_default_screen_stays_within_its_budget(homes, corpus, view):
    """On the fixture and on a corpus shaped like a real week: the gate
    measures what users see, not only a thin fixture."""
    out = ok(homes[corpus], view)
    assert out.startswith("read: ") and render.NEXT in out  # vacuity guard: a full screen
    assert len(out.splitlines()) <= test_examples.CAP_LINES, (len(out.splitlines()), out)
    assert len(out) <= test_examples.CAP_CHARS, (len(out), out)


def test_help_fits_and_no_arguments_print_it_with_a_runnable_first_command(homes):
    code, bare, err = sa(homes["fixture"])
    assert code == 0 and not err and bare == ok(homes["fixture"], "-h")
    assert len(bare.splitlines()) <= HELP_LINES, len(bare.splitlines())
    first = [c for c in suggested(bare) if c.split()[len(PROG.split()):][:1] == [CONTEXT]]
    assert first, bare  # vacuity guard: the help names a command to start with
    assert runs(homes["fixture"], first[0])[0] == 0, first[0]


@pytest.mark.parametrize("view", grammar.VIEWS)
def test_neither_view_requires_a_flag(homes, view):
    assert ok(homes["fixture"], view).startswith("read: ")


@pytest.mark.parametrize("args", [a for a in matrix() if "-v" in a], ids=" ".join)
def test_v_adds_exactly_what_its_pointer_announces_and_six_lines_a_term(homes, args):
    plain = ok(homes["fixture"], *[a for a in args if a != "-v"])
    pointer = [line for line in plain.splitlines() if line.startswith(PROG) and FOOTER.search(line)]
    assert len(pointer) == 1, plain  # vacuity guard: the pointer is there to be read, a command
    assert shlex.split(pointer[0].split("  ")[0])[-1] == "-v"
    announced = int(FOOTER.search(pointer[0]).group(1))
    verbose = ok(homes["fixture"], *args).splitlines()
    assert len(verbose) - len(plain.splitlines()) == announced  # what it costs, exactly
    block = [line for line in verbose if line not in plain.splitlines() or line.startswith(notes.HEAD)]
    entries = []
    for line in block:
        if line.startswith(notes.INDENT) and entries:
            entries[-1].append(line)
        elif line.startswith("  ") and not line.startswith(notes.HEAD):
            entries.append([line])
    assert entries, block  # vacuity guard: something was explained
    assert max(len(e) for e in entries) <= TERM_LINES, max(entries, key=len)
    terms = [e for e in entries if re.match(r"^  [\w ]+: ", e[0])]
    assert all(len(e[0]) <= grammar.WIDTH and not e[0].startswith(notes.INDENT) for e in terms)  # one line first


def _mangled(word):
    return word[:-1] + ("x" if word[-1] != "x" else "y")


ERRORS = [(word,) for word in sorted(grammar.RETIRED)] + [(CONTEXT, word) for word in sorted(grammar.RETIRED)] + [
    (CONTEXT, "Bash"),                                                  # a bare word
    (CONTEXT, "nonsense"),
    (CONTEXT, grammar.BY, _mangled(schema.TOOL_DIM)),                   # an unknown dimension
    (CONTEXT, "%s=x" % _mangled(schema.TOOL_DIM)),
    (CONTEXT, "%s=NoSuchTool" % schema.TOOL_DIM),                       # a value no fact carries
    (CONTEXT, "%s=%s" % (schema.CAUSE_DIM, _mangled(schema.REPLIES))),  # a closed vocabulary's typo
    (CONTEXT, "%s=%s" % (schema.PEAK_DIM, "999K")),
    (SPEND, "%s=%s" % (schema.CAUSE_DIM, schema.REPLIES)),             # a dimension the view lacks
    (CONTEXT, "--since", "week"), (CONTEXT, schema.TOOL_DIM), (CONTEXT, grammar.BY)]


@pytest.mark.parametrize("args", ERRORS, ids=" ".join)
def test_an_error_is_two_lines_whose_suggestions_run(homes, args):
    code, out, err = sa(homes["fixture"], *args)
    assert code == 2 and not out and err.strip(), (code, out, err)
    assert len(err.splitlines()) <= ERROR_LINES, err
    for command in suggested(err):
        assert runs(homes["fixture"], command)[0] == 0, (command, err)
    for pin in re.findall(r"pin it as (\S+)", err):
        assert sa(homes["fixture"], args[0], *shlex.split(pin))[0] == 0, (pin, err)


@pytest.mark.parametrize("corpus,args", SCREENS, ids=lambda x: x if isinstance(x, str) else " ".join(x))
def test_every_line_fits_and_every_suggested_command_runs(homes, corpus, args):
    out = ok(homes[corpus], *args)
    assert out.strip()  # vacuity guard
    wide = [line for line in out.splitlines() if len(line) > grammar.WIDTH]
    assert not wide, wide
    for command in suggested(out):
        assert runs(homes[corpus], command)[0] == 0, command


def test_the_screens_do_suggest_commands(homes):
    """Vacuity guard for the test above: the matrix prints a ``→ next:`` and
    a ``+N more`` command, and ``suggested`` finds them."""
    found = [c for corpus, args in SCREENS for c in suggested(ok(homes[corpus], *args))]
    assert any(grammar.BY in shlex.split(c) for c in found) and any(
        grammar.BY not in shlex.split(c) for c in found), found


def test_no_line_prints_whatever_is_asked(homes):
    """Outside the scope and headline (sections 1 and 2, which name the
    population and so may repeat), no line is in every default run: the
    two views and a pinned one. The scope's own lines do repeat: the
    comparison sees repetition when it is there."""
    home = homes["fixture"]
    pin = "%s=%s" % (schema.PEAK_DIM, schema.BANDS[-1])
    runs_ = [sections(ok(home, *a)) for a in ((CONTEXT,), (SPEND,), (CONTEXT, pin))]
    scope = set.intersection(*(set(s[0]) for s in runs_))
    assert scope  # vacuity guard: the read line repeats, and is found
    body = [set(line for s in r[2:] for line in s) for r in runs_]
    assert all(body)
    assert not set.intersection(*body), set.intersection(*body)
    assert not body[0] & body[1], body[0] & body[1]  # the two views share no line


def _pinned(out, dim, label):
    head = "\n".join(sections(out)[0] + sections(out)[1])
    return "%s=%s" % (dim, label) in head or any(line.startswith(label + ":") for line in sections(out)[1])


@pytest.mark.parametrize("corpus", ["fixture", "wide", "realistic"])
def test_every_row_label_round_trips_as_a_pin(homes, corpus):
    home = homes[corpus]
    pins, catch_alls = 0, 0
    for view, (dim, labels) in [(v, t) for v in grammar.VIEWS for t in parsed_tables(ok(home, v))]:
        catch_alls += residual.label(dim) in labels
        for label in (l.rstrip(glossary.MARKER) for l in labels):
            if label in (tables.BASE_LABEL, tables.TOTAL_LABEL) or MORE.match(label) or (
                    label == SHRINK and dim != schema.CAUSE_DIM):  # a signed row: no value to pin
                continue
            out = ok(home, view, "%s=%s" % (dim, label))  # an argv word: as pasted, quoted
            assert _pinned(out, dim, label), (dim, label, out)
            pins += 1
    assert pins >= 4 and catch_alls  # vacuity guard: tables, their rows and a catch-all row pinned


def test_every_more_row_shows_that_many_more_rows(homes):
    home = homes["wide"]
    cut = 0
    for view in grammar.VIEWS:
        out = ok(home, view)
        for dim, labels in parsed_tables(out):
            more = [MORE.match(l) for l in labels if MORE.match(l)]
            if not more:
                continue
            cut += 1
            n = int(more[0].group(1).replace(",", ""))
            commands = [c for c in suggested(out) if grammar.BY in shlex.split(c) and
                        shlex.split(c)[shlex.split(c).index(grammar.BY) + 1] == dim]
            assert commands, (dim, out)
            full = dict(parsed_tables(runs(home, commands[0])[1]))[dim]
            regular = lambda ls: [l for l in ls[:ls.index(tables.BASE_LABEL)] if not MORE.match(l)]
            assert len(regular(full)) == len(regular(labels)) + n, (dim, labels, full)
            assert len(regular(labels)) == render.LIMIT
    assert cut  # vacuity guard: the wide corpus does cut a table

