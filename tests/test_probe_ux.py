"""``sa.probe_ux`` over the fixture corpus: every section of both probe
modules reports, so a split or a parser change cannot silently drop one."""
import fixtures as fx
from sa import corpus, probe_ux


def test_the_probe_reports_every_section(tmp_path):
    lines = probe_ux.report(corpus.load(fx.cli_corpus(tmp_path)))
    sections = {line.split("]")[0] + "]" for line in lines}
    assert len(lines) > len(sections) > 0  # vacuity guard: there are lines
    assert sections == {"[1 compaction]", "[2 segmented]", "[3 triggers]", "[4 inherited]",
                        "[5 head content]"}
    assert any("holds True" in line for line in lines if line.startswith("[2 segmented]"))


def test_the_window_model_probe_reports_over_the_window_corpus(tmp_path):
    from sa import probe_window_model
    lines = probe_window_model.report(corpus.load(fx.window_corpus(tmp_path)))
    assert {line.split("]")[0] + "]" for line in lines} == {"[1 files]", "[2 split]", "[2 spend]",
                                                           "[2 forks]"}
