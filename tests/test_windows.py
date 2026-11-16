"""Context windows (D-CONTEXT-WINDOW, D-START-CAUSE, D-FORK-INHERITED,
D-INHERITED-ONCE): cut after dedup, keyed by (file, start line), every one
telescoping, inherited mass counted once. The corpus is
``fixtures.window_corpus``, whose arithmetic is written out there."""
import json
import os
import re
import time

import fixtures as fx
from sa import corpus, glossary, query, render, schema, tables, walk, windows
from sa.schema import CALL, INCREMENT, WindowKey

CAUSE = schema.CAUSE_DIM


def _facts(tmp_path, keep=None):
    return fx.load_facts(fx.window_corpus(tmp_path), keep)


def _per_window(facts, key=lambda f: f.window):
    booked, final = {}, {}
    for f in facts:
        if f.kind == INCREMENT:
            booked[key(f)] = booked.get(key(f), 0) + f.metrics[fx.DELTA]
        else:
            final[key(f)] = f.metrics[fx.PEAK]
    return booked, final


def _sel(facts, *where):
    return query.selection(facts, list(where), fx.DELTA, True)


def _pin(name, line=1):
    return (schema.WINDOW_DIM, fx.window_value(name, line))


def test_every_window_telescopes_and_a_file_keyed_reconcile_fails_on_a_split_file(tmp_path):
    loaded, facts = _facts(tmp_path)
    booked, final = _per_window(facts)
    assert final == {WindowKey(*k): v for k, v in fx.W_FINALS.items()}
    assert booked == final  # every window telescopes, the inherited increment included
    r = query.reconcile(facts)
    assert r.holds and r.windows == len(fx.W_FINALS) and query.window_count(facts) == r.windows
    by_file = [f._replace(window=WindowKey(f.locator.file, 1)) for f in facts]
    assert len({f.window for f in by_file}) < r.windows  # vacuity guard: a file holds two windows
    assert not query.reconcile(by_file).holds


def test_each_window_carries_one_declared_start_and_its_hashed_key(tmp_path):
    loaded, facts = _facts(tmp_path)
    starts = {}
    for f in facts:
        starts.setdefault(f.window, set()).add(f.dims[schema.STARTED_BY_DIM])
        assert f.dims[schema.WINDOW_DIM] == schema.window_value(f.window)
    assert starts == {WindowKey(*k): {v} for k, v in fx.W_STARTS.items()}
    assert set(schema.STARTS) <= set(fx.W_STARTS.values())  # the corpus carries every start


def test_the_population_line_counts_the_unpriced_compactions(tmp_path):
    root = fx.window_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root))
    assert code == 0, err
    assert "\n      2 compactions unpriced: 1 started a window%s, 1 ended their file\n" % glossary.MARKER in out
    assert "\nin view: %d windows, " % len(fx.W_FINALS) in out  # marked on the line above
    code, out, err = fx.run_cli("context", "--root", str(fx.cli_corpus(tmp_path / "plain")))
    assert code == 0, err
    assert "compaction" not in sections_text(out, 0)  # none read: no line


def sections_text(out, k):
    return "\n".join(fx.sections(out)[k])


def test_a_message_id_split_across_a_marker_is_one_call_in_its_first_window(tmp_path):
    first = fx.assistant("uuid-0001", "msg-0001", fx.usage(1000, 50),
                         [fx.tool_use("toolu_0001", "Bash", command="ls")])
    later = fx.assistant("uuid-0003", "msg-0001", fx.usage(1000, 60))
    tail = [later, fx.tool_result("uuid-0004", "toolu_0001"),
            fx.assistant("uuid-0005", "msg-0002", fx.usage(1200, 0))]
    split = fx.load_facts(fx.corpus(tmp_path / "split", {
        "proj-a/sess-0001.jsonl": [first, fx.marker("uuid-0002")] + tail}))[1]
    whole = fx.load_facts(fx.corpus(tmp_path / "whole", {
        "proj-a/sess-0001.jsonl": [first, fx.user_text("uuid-0002")] + tail}))[1]
    calls = [f for f in split if f.kind == CALL]
    assert [f.locator.line for f in calls] == [1, 5] and len({f.window for f in calls}) == 2
    assert calls[0].metrics["output_tokens"] == 60  # max-merged across the marker
    for name, spec in schema.METRICS.items():
        if spec.carrier == CALL and spec.aggregation == schema.ADDITIVE:
            assert query.total(split, name) == query.total(whole, name), name
    assert query.reconcile(split).holds and query.window_count(whole) == 1  # vacuity guard


def test_a_fork_with_its_parent_in_scope_counts_the_inherited_mass_once(tmp_path):
    loaded, facts = _facts(tmp_path)
    inherited = {f.locator.file: f for f in facts if f.dims.get(CAUSE) == schema.INHERITED}
    assert {k: f.metrics[fx.DELTA] for k, f in inherited.items()} == fx.W_INHERITED
    whole = _sel(facts)
    assert whole.total == sum(fx.W_FINALS.values()) - sum(fx.W_INHERITED.values())
    assert whole.reconciliation.booked == sum(fx.W_FINALS.values())  # each window's own includes it
    assert not [f for f in whole.facts if f.dims.get(CAUSE) == schema.INHERITED]
    parent, fork = _pin(fx.W_PARENT), _pin(fx.W_FORK)
    both = _sel(facts, (schema.SESSION_DIM, "sess-0101"))  # the parent's two windows and the fork
    alone = _sel(facts, parent).total + _sel(facts, _pin(fx.W_PARENT, 8)).total + _sel(facts, fork).total
    assert alone - both.total == fx.W_INHERITED[fx.W_FORK]  # out of scope: counted in full
    assert _sel(facts, fork).total == fx.W_FINALS[(fx.W_FORK, 1)] and not _sel(facts, fork).inherited
    assert sum(f.metrics[fx.DELTA] for f in both.inherited) == fx.W_INHERITED[fx.W_FORK]
    # Nothing counted twice: no fork fact sits in the parent's file, nor re-minted from it.
    fork_facts = [f for f in facts if f.locator.file == fx.W_FORK]
    assert fork_facts and not [f for f in fork_facts if f.window.file != fx.W_FORK]


def test_the_inherited_breakdown_is_the_parent_window_through_the_branch_call(tmp_path):
    loaded, facts = _facts(tmp_path)
    for name, mass in fx.W_INHERITED.items():
        (inc,) = [f for f in facts if f.locator.file == name and f.dims.get(CAUSE) == schema.INHERITED]
        parent, branch = inc.evidence[schema.PARENT_WINDOW], inc.evidence[schema.BRANCH_CALL]
        assert parent == WindowKey(fx.W_PARENT, 1) and branch.file == fx.W_PARENT
        part = query.through(facts, parent, branch)
        assert part and {f.window for f in part} == {parent}
        assert sum(f.metrics[fx.DELTA] for f in part if f.kind == INCREMENT) == mass
        assert part[-1].kind == INCREMENT and query.through(facts, parent, inc.locator) == []  # guard


def test_the_cli_states_inherited_once_on_the_total_row_and_the_footer(tmp_path):
    root = fx.window_corpus(tmp_path)
    label, mass = render.INHERITED_LABEL, format(sum(fx.W_INHERITED.values()), ",d")
    code, out, err = fx.run_cli("context", "--root", str(root), "--limit", "1")
    assert code == 0, err
    assert re.search(r"^%s .* final window sizes less %s %s$" % (tables.TOTAL_LABEL, mass, re.escape(label)),
                     out, re.M)
    assert re.search(r"^%s: %s .* in 2 windows" % (re.escape(label), mass), out, re.M)  # --limit 1
    assert not re.search(r"^%s\s+[\d,]+\s" % schema.INHERITED, out, re.M)  # not a row: never in a share
    code, out, err = fx.run_cli("context", "--root", str(root), "--where", "=".join(_pin(fx.W_FORK)))
    assert code == 0, err
    assert label not in out  # the parent is out of scope: counted in full, as a row
    assert re.search(r"^%s\s+1,500\s+1\s" % schema.INHERITED, out, re.M)
    assert fx.headline(out).split("; ")[1].endswith(" + %s 1,500" % schema.INHERITED)  # its own term



def test_a_pinned_fork_shows_its_copy_as_the_parent_breakdown_by_tool(tmp_path):
    """Under a ``--where window=`` pin, each inherited increment prints its
    parent window's breakdown by tool through the branch call, found by
    reference; the parts sum to the inherited mass. Unpinned, never."""
    root = fx.window_corpus(tmp_path)
    facts = fx.load_facts(root)[1]
    for name, mass in fx.W_INHERITED.items():
        out = fx.run_cli("context", "--root", str(root), "--where", "=".join(_pin(name)))[1]
        (line,) = [l for l in fx.sections(out)[1] if l.lstrip().startswith(schema.INHERITED + " ")]
        assert line.startswith("    %s %s copied from %s=%s through " % (
            schema.INHERITED, format(mass, ",d"), schema.WINDOW_DIM, fx.window_value(fx.W_PARENT)))
        parts = [part.rsplit(" ", 1) for part in line.split(", by %s: " % schema.TOOL_DIM)[1].split(", ")]
        assert parts and sum(int(n.replace(",", "")) for _, n in parts) == mass, line
        assert "Bash" in dict(parts)  # vacuity guard: a real tool, not the residual alone
    unpinned = fx.run_cli("context", "--root", str(root))[1]
    assert " copied from " not in unpinned and schema.INHERITED in unpinned  # guard: inherited is there

def test_a_window_value_selects_and_an_unknown_one_exits_2_naming_those_present(tmp_path):
    root = fx.window_corpus(tmp_path)
    code, out, err = fx.run_cli("context", "--root", str(root), "--where", "%s=0000zzzz" % schema.WINDOW_DIM)
    assert code == 2 and not out and "no %s carry window=0000zzzz; present: " % schema.PLURAL[INCREMENT] in err
    assert fx.window_value(fx.W_PARENT, 8) in err
    code, out, err = fx.run_cli("context", "--root", str(root), "--where", "=".join(_pin(fx.W_PARENT, 8)))
    assert code == 0 and re.search(r"\nin view where %s: 1 window\*?, " % "=".join(_pin(fx.W_PARENT, 8)), out)


def test_window_keys_are_the_same_whatever_the_since_window(tmp_path):
    root = fx.window_corpus(tmp_path)
    stale = time.time() - 30 * corpus.DAY
    os.utime(root / fx.W_PARENT, (stale, stale))
    recent, every = (walk.forest(corpus.load(root, keep)) for keep in (7.0, None))
    keys = lambda facts: {(f.locator.file, f.window, f.dims[schema.WINDOW_DIM]) for f in facts}
    files = {f.locator.file for f in recent}
    assert fx.W_FORK in files and fx.W_PARENT not in files  # vacuity guard: the parent is out
    assert keys(recent) == {k for k in keys(every) if k[0] in files}
    # The facts differ, the keys do not: without the parent the fork's copy is live and owns
    # the prefix, so the fork inherits nothing and the replayed window inherits from the fork.
    inherits = lambda facts: {f.locator.file: f.evidence[schema.PARENT_WINDOW].file for f in facts
                              if f.dims.get(CAUSE) == schema.INHERITED}
    assert inherits(every) == {fx.W_FORK: fx.W_PARENT, fx.W_REPLAY: fx.W_PARENT}
    assert inherits(recent) == {fx.W_REPLAY: fx.W_FORK}


def test_a_forced_key_collision_causes_no_false_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(schema, "window_value", lambda key: "deadbeef")
    loaded, facts = _facts(tmp_path)
    assert {f.dims[schema.WINDOW_DIM] for f in facts} == {"deadbeef"}  # every window collides
    r = query.reconcile(facts)
    assert r.holds and r.windows == len(fx.W_FINALS)
    by_value = [f._replace(window=WindowKey(f.dims[schema.WINDOW_DIM], 0)) for f in facts]
    assert not query.reconcile(by_value).holds  # vacuity guard: keyed on the value, it would fail


def test_no_peak_is_summed_across_the_segments_of_one_file(tmp_path):
    loaded, facts = _facts(tmp_path)
    mine = [f for f in facts if f.locator.file == fx.W_PARENT]
    peaks = {}
    for f in mine:
        if f.kind == CALL:
            peaks[f.window] = max(peaks.get(f.window, 0), f.metrics[fx.PEAK])
    assert len(peaks) == 2  # vacuity guard: the file is two windows
    top = query.largest(mine, fx.PEAK)
    assert top.metrics[fx.PEAK] == max(peaks.values()) != sum(peaks.values())
    code, out, err = fx.run_cli("context", "--root", str(fx.window_corpus(tmp_path / "cli")),
                                "--where", "%s=sess-0101" % schema.SESSION_DIM)
    assert code == 0, err
    (average,) = fx.average(out)  # over the session's calls, never a sum of their peaks
    mean, calls = query.mean(query.select(facts, [(schema.SESSION_DIM, "sess-0101")]), fx.PEAK)
    assert average.startswith("%s%s %s, over %d calls" % (fx.AVERAGE, tables.num(mean), fx.unit(fx.PEAK), calls))
    for key, peak in peaks.items():  # each window's band is its own largest call's
        assert {f.dims[schema.PEAK_DIM] for f in mine if f.window == key} == {schema.band(peak)}


def test_a_window_peak_band_includes_its_lower_edge_and_is_whole_window(tmp_path):
    """D-PEAK-BAND: a call of exactly an edge is in the band above it; a
    window's band is its largest call's, on every fact of the window, its
    first small calls too, and the bands are declared in order."""
    assert [schema.band(e) for e in schema.BAND_EDGES] == list(schema.BANDS)
    assert [schema.band(e - 1) for e in schema.BAND_EDGES[1:]] == list(schema.BANDS[:-1])
    _, facts = fx.load_facts(fx.every_corpus(tmp_path))
    assert {f.dims[schema.PEAK_DIM] for f in facts} == set(schema.BANDS)  # vacuity guard: every band
    for key in {f.window for f in facts}:
        mine = [f for f in facts if f.window == key]
        top = max(f.metrics[fx.PEAK] for f in mine if f.kind == CALL)
        assert {f.dims[schema.PEAK_DIM] for f in mine} == {schema.band(top)}


def test_segmenting_leaves_the_duplicate_count_unchanged(tmp_path):
    root = fx.window_corpus(tmp_path / "cut")
    flat = {}
    for path in root.rglob("*.jsonl"):
        flat[path.relative_to(root).as_posix()] = [
            line.replace('"compact_boundary"', '"not_a_marker"') for line in path.read_text().splitlines()]
    uncut = corpus.load(fx.corpus(tmp_path / "flat", flat))
    cut = corpus.load(root)
    assert cut.duplicate_records == uncut.duplicate_records == fx.W_DUPLICATES
    assert query.window_count(walk.forest(cut)) > query.window_count(walk.forest(uncut))  # guard


def _fork_alone(tmp_path, marked):
    """The window corpus's fork, its parent file absent, with and without
    the api-request record a fork writes (``windows.marked_fork``)."""
    lines = (fx.window_corpus(tmp_path / "all") / fx.W_FORK).read_text(encoding="utf-8").splitlines()
    mark = [{"type": "api-request", "querySource": windows.FORK_SOURCE, "agentId": "agent-fork1"}]
    return fx.corpus(tmp_path / "alone", {fx.W_FORK: [json.loads(l) for l in lines] + mark * marked})


def test_a_marked_fork_without_its_parent_is_counted_and_named_on_the_scope(tmp_path):
    """D-MISSING-PARENT: the copy is not detected; the fork keeps its label
    and the scope says how many forks count their copy as their own."""
    warning = "1 fork whose parent is missing: its copy counts as its own"
    root = _fork_alone(tmp_path, True)
    _, facts = fx.load_facts(root)
    assert {f.dims[schema.STARTED_BY_DIM] for f in facts} == {schema.FORK}
    assert query.orphan_forks(facts) == 1 and not [f for f in facts if f.dims.get(schema.CAUSE_DIM) == schema.INHERITED]
    code, out, err = fx.run_cli("context", "--root", str(root))
    assert code == 0, err
    assert fx.sections(out)[0][-1] == " " * len("in view: ") + warning
    unmarked = fx.load_facts(_fork_alone(tmp_path / "bare", False))[1]  # the limitation: no mark, no fork
    assert {f.dims[schema.STARTED_BY_DIM] for f in unmarked} == {schema.SUBAGENT_START}
    whole = fx.window_corpus(tmp_path / "whole")  # vacuity guard: with its parent, no warning
    _, facts = fx.load_facts(whole)
    assert query.orphan_forks(facts) == 0 and [f for f in facts if f.dims.get(schema.STARTED_BY_DIM) == schema.FORK]
    assert "missing" not in fx.run_cli("context", "--root", str(whole), "--since", "all")[1]
