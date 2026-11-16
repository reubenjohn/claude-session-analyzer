"""The screens on ``corpora.realistic``, a real week's shape (UX_PRINCIPLES):
what a default screen leaves out is named (2), the front door takes the
global flags (1), one identity style for sessions (1), and a fact list
says what it cut and how to see it (3). Corpora and helpers are
``test_screen_budgets``'s."""
import re
import shlex

import fixtures as fx
from sa import checks, grammar, render, schema
from test_screen_budgets import (CONTEXT, ERROR_LINES, MORE, PROG, homes, ok, parsed_tables,  # noqa: F401
                                 sa)


def test_the_realistic_corpus_is_wide_on_every_dimension(homes):
    """Vacuity guard for the budget above: the realistic default screen
    cuts its tables and names more dimensions than it prints."""
    out = ok(homes["realistic"], CONTEXT)
    assert len([l for l in out.splitlines() if MORE.match(re.split(r"\s{2,}", l)[0])]) >= 2, out
    also = fx.also(out)
    for dim in (schema.SUBAGENT_DIM, schema.SESSION_DIM, schema.PROJECT_DIM, schema.PEAK_DIM):
        assert dim in also, also
        table = dict(parsed_tables(ok(homes["realistic"], CONTEXT, grammar.BY, dim)))[dim]
        assert len(table) > (len(schema.BANDS) if dim == schema.PEAK_DIM else render.LIMIT), (dim, table)


def test_global_flags_alone_open_the_front_door(homes):
    """P1: ``--color never`` with no command prints the orientation, exit 0;
    a bad flag value is still a two-line refusal."""
    assert ok(homes["fixture"], "--color", "never") == ok(homes["fixture"], "-h")
    assert ok(homes["fixture"], "--color", "never", CONTEXT).startswith("read: ")  # flags first, command after
    code, out, err = sa(homes["fixture"], "--color", "nope")
    assert code == 2 and not out and 0 < len(err.splitlines()) <= ERROR_LINES


def test_a_session_prints_as_8_hex_and_pins_by_any_unique_prefix(homes):
    home = homes["realistic"]
    labels = [l for l in dict(parsed_tables(ok(home, CONTEXT, grammar.BY, schema.SESSION_DIM)))[schema.SESSION_DIM]
              if re.match(r"^[0-9a-f]+$", l)]
    assert len(labels) > render.LIMIT and all(len(l) == 8 for l in labels), labels  # one identity style
    unique = next(k for k in range(1, 9) if sum(l.startswith(labels[0][:k]) for l in labels) == 1)
    pin = "%s=%s" % (schema.SESSION_DIM, labels[0][:unique])  # a unique prefix: the printed label back
    assert "%s=%s" % (schema.SESSION_DIM, labels[0]) in ok(home, CONTEXT, pin).splitlines()[1]
    shared = labels[0][:1]  # every session's, here
    assert all(l.startswith(shared) for l in labels)  # vacuity guard: the prefix is ambiguous
    code, out, err = sa(home, CONTEXT, "%s=%s" % (schema.SESSION_DIM, shared))
    assert code == 2 and len(err.splitlines()) <= ERROR_LINES, err
    for word in re.findall(r"e\.g\. (\S+)", err):  # the nearest valid input, verbatim
        assert sa(home, CONTEXT, word)[0] == 0, err


def test_by_change_says_what_it_cut_and_how_to_see_it(homes):
    """P3: a fact list over many windows prints the largest ``render.LIMIT``,
    each its largest changes; every cut ends with the command that lists it."""
    home = homes["realistic"]
    out = ok(home, CONTEXT, grammar.BY, grammar.FACTS[CONTEXT])
    cuts = re.findall(r"^\s*\+([\d,]+) more (\w+), .*?: (%s .+)$" % re.escape(PROG), out, re.M)
    assert len(cuts) > render.LIMIT, out  # vacuity guard: windows and changes both cut
    for n, what, command in cuts:
        shown = ok(home, *shlex.split(command)[len(PROG.split()):])
        if what == "windows":
            rows = dict(parsed_tables(shown))[schema.WINDOW_DIM]
            assert len([r for r in rows if re.match(r"^[0-9a-f]{8}$", r)]) == render.LIMIT + int(n), rows
        else:
            assert "more %s" % what not in shown  # one window lists every change


def test_the_checks_say_what_is_checked_and_material_uncertainty_its_own(homes):
    """P2/P3: ALWAYS one ✓ line saying what is checked, then the ambiguous
    share of the average (what could not be traced, with its base); ON
    TRIGGER (that share at or over ``checks.AMBIGUOUS_MATERIAL``) a ``!``
    line whose command shows those changes; ON REQUEST (-v) the worked
    equation. Spend's one line is its own sum, in its numbers."""
    for corpus, material in (("fixture", False), ("realistic", True)):
        last = ok(homes[corpus], CONTEXT).rstrip("\n").split("\n\n")[-1].splitlines()
        assert last[0].startswith(checks.OK) and "average call" in last[0] and "window sizes" in last[0]
        share = float(re.match(r"^  %s\*?: ([\d.]+)%% of the average call" % schema.AMBIGUOUS, last[1]).group(1))
        flagged = [l for l in last[2:] if l.lstrip().startswith("!")]
        assert bool(flagged) is material is (share >= 100 * checks.AMBIGUOUS_MATERIAL) and len(last) == 2 + len(
            flagged), last
        for line in flagged:
            command = line[line.index(PROG):]
            assert "%s=%s" % (schema.CAUSE_DIM, schema.AMBIGUOUS) in command and grammar.BY not in command
            assert ok(homes[corpus], *shlex.split(command)[len(PROG.split()):])  # a short screen: its tables
    spent = ok(homes["fixture"], grammar.VIEWS[0]).splitlines()
    assert re.match(r"^%s: = 100%% [\d,]+ \+ .+ = %s ([\d,]+)$" % (checks.OK, schema.SPEND), spent[-1]), spent[-1]


def test_a_pinned_cause_prints_no_trigger_command(homes):
    """F8: the screen the trigger would point at is this one."""
    out = ok(homes["realistic"], CONTEXT, "%s=%s" % (schema.CAUSE_DIM, schema.AMBIGUOUS))
    assert "ambiguous" in out.rstrip("\n").split("\n\n")[-1] and "!" not in out.rstrip("\n").split("\n\n")[-1]
    assert "!" in ok(homes["realistic"], CONTEXT).rstrip("\n").split("\n\n")[-1]  # vacuity guard
