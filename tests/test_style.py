"""The styling layer (``sa.style``): colour only when asked for, painting
only ever adds escape codes to the plain contract, a tool keeps one hue
wherever it prints, and the rows a table never hides are never dimmed."""
import re

import pytest

import fixtures as fx
from sa import cli, style

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
    tool = next(line for line in style.plain(out).splitlines() if line.startswith("by tool"))
    first = style.plain(out).splitlines()[style.plain(out).splitlines().index(tool) + 1].split()[0]
    headline = [line for line in out.splitlines() if "tool=" in line]
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
    assert not set(style.TOOL_HUES) & {style.GREEN[0], style.RED[0]}  # the checks' colours


def test_rows_a_table_never_hides_are_never_dimmed(tmp_path):
    """``∅`` and the signed rows print italic, whatever their share; only a
    regular row under ``COLD`` is dimmed, and one at ``HOT`` has its share
    bold."""
    root = str(fx.cli_corpus(tmp_path))
    out = fx.run_cli("context", "--root", root, "--color", style.ALWAYS)[1].splitlines()
    kept = [line for line in out if re.match(r"(\033\[\d+m)?(∅|shrink \(signed\))\s", line)]
    assert kept  # vacuity guard
    faint, italic = "%s%sm" % (ESC, style.FAINT[0]), "%s%sm" % (ESC, style.ITALIC[0])
    assert all(line.startswith(italic) and faint not in line for line in kept)
    painter = style.Painter()
    cold = style.tag("x  1  0.5%", style.ROW, style.COLD / 2)
    hot = style.tag("x  9  50.0%", style.ROW, style.HOT * 2)
    assert painter.paint(cold).startswith(faint)
    assert painter.paint(hot).endswith(style.sgr("50.0%", style.BOLD))
