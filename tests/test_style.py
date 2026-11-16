"""The styling layer (``sa.style``): colour only when asked for, painting
only ever adds escape codes to the plain contract, a tool keeps one hue
wherever it prints, and the rows a table never hides are never dimmed."""
import re

import pytest

import fixtures as fx
from sa import cli, render, style, tables

ESC = "\033["


@pytest.mark.parametrize("choice, env, tty, on", [
    (style.AUTO, {}, True, True),
    (style.AUTO, {}, False, False),                      # a pipe is no TTY
    (style.AUTO, {"NO_COLOR": "1"}, True, False),
    (style.AUTO, {"NO_COLOR": ""}, True, True),          # empty is unset
    (style.AUTO, {"FORCE_COLOR": "1"}, False, True),
    (style.AUTO, {"FORCE_COLOR": "0"}, False, False),
    (style.AUTO, {"NO_COLOR": "1", "FORCE_COLOR": "1"}, False, False),
    (style.ALWAYS, {"NO_COLOR": "1"}, False, True),
    (style.NEVER, {"FORCE_COLOR": "1"}, True, False),
])
def test_enabled_honours_the_choice_the_environment_and_the_tty(choice, env, tty, on):
    assert style.enabled(choice, tty, env) is on


def test_the_cli_colours_a_tty_and_nothing_else(tmp_path, monkeypatch, capsys):
    root = str(fx.cli_corpus(tmp_path))
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)

    def out(*args):
        cli.main(["context", "--root", root] + list(args))
        return capsys.readouterr().out
    assert ESC in out()
    assert ESC not in out("--color", style.NEVER)
    monkeypatch.setenv("NO_COLOR", "1")
    assert ESC not in out()
    assert ESC in out("--color", style.ALWAYS)
    assert ESC not in fx.run_cli("context", "--root", root)[1]  # a pipe is no TTY


@pytest.mark.parametrize("args", [("context",), ("spend",), ("context", "--by", "fact"),
                                  ("context", "--where", "tool=Bash", "--by", "command"),
                                  ("spend", "--by", "subagent")])
def test_painting_only_adds_escape_codes_to_the_plain_output(tmp_path, args):
    """The plain output is the contract: strip the codes and it is back,
    byte for byte, so styling can never carry what the text does not."""
    root = str(fx.cli_corpus(tmp_path))
    plain = fx.run_cli(*args, "--root", root, "--color", style.NEVER)
    coloured = fx.run_cli(*args, "--root", root, "--color", style.ALWAYS)
    assert ESC in coloured[1] and ESC not in plain[1]  # vacuity guard
    assert style.plain(coloured[1]) == plain[1] and coloured[0] == plain[0]


def _hues(text, name):
    """The SGR code right before each standalone occurrence of ``name``."""
    return re.findall(r"(?:\033\[(\d+)m|(?<![\w./~-]))%s(?!\w)" % re.escape(name), text)


def test_a_tool_keeps_one_hue_across_the_headline_and_the_tables(tmp_path):
    root = str(fx.cli_corpus(tmp_path))
    out = fx.run_cli("context", "--root", root, "--color", style.ALWAYS)[1]
    out = "\n".join(line for line in out.splitlines() if render.NEXT not in style.plain(line))  # cyan whole
    tool = next(line for line in style.plain(out).splitlines() if line.startswith("by tool"))
    first = style.plain(out).splitlines()[style.plain(out).splitlines().index(tool) + 1].split()[0]
    headline = [line for line in out.splitlines() if " from " in style.plain(line)]
    assert headline and first in style.plain(headline[0])  # vacuity guard: the walk names it
    assert set(_hues(out, first)) == {style.TOOL_HUES[0]}


def test_tools_take_distinct_hues_and_only_whole_names_are_painted():
    painter = style.Painter(["Bash", "Read"])
    lines = ["growth: tool=Bash 9 (90%), command=Bash:sed 5 (55% of Bash, 50%) under tool=Read",
             "Bash:cat   4", "Read:py   3", "project ~-x-Bash  Bashful  a/Read"]
    painted = "\n".join(painter.paint(line) for line in lines)
    assert set(_hues(painted, "Bash")) == {style.TOOL_HUES[0]}
    assert set(_hues(painted, "Read")) == {style.TOOL_HUES[1]}
    assert ESC not in painter.paint(lines[-1])  # inside a word, a path or a project: no hue
    assert len(style.Painter("ABCDEFG").hues) == len(style.TOOL_HUES)  # the rest print plain
    assert not set(style.TOOL_HUES) & {style.RED, style.YELLOW, style.GREEN}  # the heatmap's


def test_rows_a_table_never_hides_are_never_dimmed_nor_heated(tmp_path):
    """``unassigned``, ``+N more rows`` and the signed rows print italic, whatever
    their share, outside the heatmap; so does the total row."""
    root = str(fx.cli_corpus(tmp_path))
    out = fx.run_cli("context", "--root", root, "--color", style.ALWAYS)[1].splitlines()
    kept = [line for line in out
            if re.match(r"(unassigned\*?|shrink \(signed\)|\+\d+ more rows)\s", style.plain(line))]
    assert any(style.plain(line).startswith("unassigned") for line in kept)  # vacuity guard
    faint, italic = "%s%sm" % (ESC, style.FAINT[0]), "%s%sm" % (ESC, style.ITALIC[0])
    heated = re.compile(r"\033\[(%s)[;m]" % "|".join((style.RED, style.YELLOW, style.GREEN)))
    assert all(line.startswith(italic) and faint not in line and not heated.search(line)
               for line in kept)
    total = [line for line in out if style.plain(line).startswith(tables.TOTAL_LABEL)]
    assert total and not heated.search(total[0])  # vacuity guard, then the total row


@pytest.mark.parametrize("share, hue, bold, faint", [
    (0.9, style.RED, True, False), (style.HOT, style.RED, True, False),
    (0.2, style.YELLOW, False, False), (style.WARM, style.YELLOW, False, False),
    (0.02, style.GREEN, False, False), (0.005, style.GREEN, False, True)])
def test_the_heatmap_maps_a_share_to_a_hue_and_a_brightness(share, hue, bold, faint):
    """Red, yellow, green by share of the base, on the figures only; bold
    repeats red and dim the smallest, for a reader who cannot tell hues."""
    line = style.tag("Bash    1,000    3   %5.1f%%" % (100 * share), style.ROW, share, ((8, 13), (19, 25)))
    painted = style.Painter(["Bash"]).paint(line)
    assert style.plain(painted) == line
    on = "%s%s%sm" % (ESC, hue, ";1" if bold else "")
    assert painted.count(on) == 2  # the mass and the share cells
    assert ("%s1m" % ESC in painted or ";1m" in painted) is bold
    assert painted.startswith("%s%sm" % (ESC, style.FAINT[0])) is faint
    assert "%s%sm1,000" % (ESC, hue) in painted.replace(";1m", "m")  # the cell, not its padding
    assert style.heat(share)[0].split(";")[0] == hue


def test_the_checks_line_carries_no_heatmap_hue(tmp_path):
    """Red, yellow and green mean a share: the ✓ line prints plain."""
    root = str(fx.cli_corpus(tmp_path))
    out = fx.run_cli("context", "--root", root, "--color", style.ALWAYS)[1].splitlines()
    checks = [line for line in out if line.startswith("✓ checks")]
    assert checks and ESC not in checks[0]


def test_the_gradient_is_monotonic_on_a_log_scale_with_fallbacks():
    """Green to amber to red as the share grows: red never falls, green
    never rises; 1%, 5% and 25% differ; the 256-colour cube and the basic
    bands stand in when the terminal has fewer colours."""
    shares = [style.FLOOR * (style.CEILING / style.FLOOR) ** (i / 40) for i in range(41)]
    colours = [style.rgb(s) for s in shares]
    assert colours[0] == style.STOPS[0] and colours[-1] == style.STOPS[-1]
    assert all(a[0] <= b[0] and a[1] >= b[1] for a, b in zip(colours, colours[1:]))
    assert len({style.rgb(s) for s in (0.01, 0.05, 0.25)}) == 3
    assert style.rgb(0.001) == style.rgb(style.FLOOR) and style.rgb(1.0) == style.rgb(style.CEILING)
    assert style.heat(0.3, style.TRUE)[0] == "38;2;%d;%d;%d;1" % style.rgb(0.3)  # bold from HOT
    assert re.fullmatch(r"38;5;\d+", style.heat(0.05, style.CUBE)[0])
    assert style.heat(0.005, style.CUBE)[0] != style.heat(0.5, style.CUBE)[0].split(";1")[0]
    assert [style.heat(s, style.BASIC)[0] for s in (0.005, 0.05, 0.3)] == [
        style.GREEN, style.YELLOW, style.RED + ";1"]
    assert style.depth({"COLORTERM": "truecolor"}) == style.TRUE
    assert style.depth({"COLORTERM": "24bit", "TERM": "xterm"}) == style.TRUE
    assert style.depth({"TERM": "xterm-256color"}) == style.CUBE
    assert style.depth({"TERM": "xterm"}) == style.BASIC == style.depth({})
