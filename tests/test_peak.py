"""The ``peak`` table and its hint end to end (D-PEAK-BAND, D-PEAK-DEFAULT):
a band opens a table or a hint only when the windows in view carry more
than one, the bands print fullest first in every view, and its count
columns count each band's windows and their calls."""
import re

import fixtures as fx
from sa import grammar, query, render, schema, tables

PEAK = schema.PEAK_DIM


def _rows(out, dim=PEAK):
    """The table's body lines: from its header to the next blank line."""
    lines = out.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(tables.title(dim) + " "))
    end = next((i for i in range(start, len(lines)) if not lines[i]), len(lines))
    return lines[start + 1:end]


def test_one_band_opens_no_peak_table_and_no_peak_hint(tmp_path):
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": fx.window_records(),
                                "proj-a/sess-0002.jsonl": fx.window_records("b-", session="sess-0002")})
    facts = fx.load_facts(root)[1]
    assert len({f.window for f in facts}) == 2 and len({f.dims[PEAK] for f in facts}) == 1  # one band
    code, out, err = fx.run_cli("context", "--root", str(root))
    assert code == 0, err
    also = next(l for l in out.splitlines() if l.startswith(render.ALSO))[len(render.ALSO):].split(", ")
    assert "%s=" % PEAK not in out and PEAK not in also
    hint = [line for line in out.splitlines() if line.startswith(render.NEXT)]
    assert hint == [render.NEXT + grammar.Invocation("context", root=str(root)).command(
        add=[(schema.TOOL_DIM, "Bash")])]  # the levers next
    several = fx.run_cli("context", "--root", str(fx.cli_corpus(tmp_path / "cli")))[1]  # vacuity guard
    assert PEAK in next(l for l in several.splitlines() if l.startswith(render.ALSO))
    assert " %s=%s " % (PEAK, schema.BANDS[-1]) in several  # the next command, before its --root


def test_bands_print_fullest_first_in_every_view(tmp_path):
    """A property of the dimension (``schema.ORDERED``), not of the view or of mass."""
    every, cli_root = str(fx.every_corpus(tmp_path)), fx.cli_corpus(tmp_path / "cli")
    drill = ("%s=%s" % (schema.CAUSE_DIM, schema.REPLIES),)
    for name, args in (("context", ("--root", every)), ("spend", ("--root", every)),
                       ("context", ("--root", str(cli_root)) + drill)):
        code, out, err = fx.run_cli(name, "--since", "all", "by", PEAK, *args)
        assert code == 0, err
        bands = [line.split()[0] for line in _rows(out) if line.split()[0] in schema.BANDS]
        assert bands == [b for b in schema.ORDERED[PEAK] if b in bands] and len(bands) > 1, name
    sel = query.selection(fx.load_facts(cli_root)[1], [drill[0].split("=")], fx.DELTA, True)
    by_mass = [r.value for r in query.group(sel.facts, PEAK, fx.DELTA).rows if r.kind == query.REGULAR]
    assert by_mass != [b for b in schema.ORDERED[PEAK] if b in by_mass]  # guard: not the mass order


def test_the_peak_table_counts_each_bands_windows_and_calls(tmp_path):
    root = fx.every_corpus(tmp_path)
    facts = fx.load_facts(root)[1]
    want = {b: ({f.window for f in facts if f.dims[PEAK] == b},
                sum(f.kind == schema.CALL and f.dims[PEAK] == b for f in facts)) for b in schema.BANDS}
    out = fx.run_cli("context", "--root", str(root), "--since", "all", "by", PEAK)[1]
    rows = {line.split()[0].rstrip("*"): line.split() for line in _rows(out)}
    assert set(schema.BANDS) <= set(rows)  # vacuity guard: every band has a row
    for band, (windows, calls) in want.items():
        assert rows[band][2:4] == [tables.num(len(windows)), tables.num(calls)], band
    assert rows[schema.SHRINK][3:6] == ["-", "-", "-"]  # the signed row counts no window
    assert rows[tables.BASE_LABEL.split()[0]][3:5] == [  # the columns add up
        tables.num(sum(len(w) for w, _ in want.values())), tables.num(sum(c for _, c in want.values()))]


def test_under_a_drill_the_peak_counts_say_they_are_whole_windows(tmp_path):
    root = fx.cli_corpus(tmp_path)
    out = fx.run_cli("context", "--root", str(root), "%s=%s" % (schema.CAUSE_DIM, schema.REPLIES),
                     "by", PEAK)[1]
    assert render.WHOLE_WINDOWS in out
    assert render.WHOLE_WINDOWS not in fx.run_cli("context", "--root", str(root), "by", PEAK)[1]  # guard


def _cells(line):
    return re.split(r"\s{2,}", line.strip())


def test_a_window_rows_avg_call_is_its_own_average_when_pinned(tmp_path):
    """Every window dimension of a per-call view (D-PER-CALL, second
    opinion): a row's ``avg call`` is the headline average its pin prints,
    not its part of the average, which divides by every call in view."""
    root, checked = fx.every_corpus(tmp_path), 0
    facts = fx.load_facts(root)[1]
    for dim in schema.WINDOW_DIMENSIONS:
        values = {f.dims[dim] for f in facts if dim in f.dims}
        if len(values) < 2:
            continue
        out = fx.run_cli("context", "--root", str(root), "--since", "all", "by", dim)[1]
        lines = out.splitlines()
        header = next(line for line in lines if line.startswith(tables.title(dim) + " "))
        at = _cells(header).index(tables.AVG_CALL)
        for row in (_cells(line) for line in _rows(out, dim)):
            value = row[0].rstrip("*")
            if value not in values:
                continue
            pinned = fx.run_cli("context", "--root", str(root), "--since", "all", "%s=%s" % (dim, value))[1]
            assert fx.average(pinned)[0].split()[4] == row[at], (dim, value)
            checked += 1
            assert row[1] != row[at]  # the part is not the own average
    assert checked >= 6  # vacuity guard: several dimensions, several rows each
    spend = fx.run_cli("spend", "--root", str(root), "--since", "all", "by", schema.SESSION_DIM)[1]
    assert tables.AVG_CALL not in spend and tables.title(schema.SESSION_DIM) in spend  # context only
