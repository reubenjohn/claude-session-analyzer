"""``sa context`` and ``sa spend``: parse the arguments, select the facts,
print the view, exit 1 if the reconciliation did not hold.

Every figure prints with the population it was counted over, every table
shows its residual and signed rows, and the ``context`` view ends with the
reconciliation of the increments against the windows' final occupancy. It
is a regression guard: ``walk`` books every interval's whole delta, so it
holds by construction, and a MISMATCH is a bug in this tool, exit status 1.

Filters: ``--root`` must be an existing directory (a typo is a refusal,
never a zero headline); ``--since`` selects FILES by modification time
before reading, 7 days unless given (``all`` reads every file), so dedup
runs over the selected files only, and a day count that keeps no file is a
legitimate empty population; ``--where`` selects facts after dedup. A
``--where`` on a window dimension (project, session, agent, window, start)
keeps whole windows; any other dimension is a drill, and the reconciliation and
the single-call peak then apply to the whole-window population they are
printed for. What ``query`` refuses (an unknown name, an undeclared value,
an open-vocabulary value no fact carries) is exit status 2 with its
message; nothing is checked twice.

``sa explain [TERM]`` prints the glossary (``schema.GLOSSARY``); an unknown
term is exit status 2. Colour only when stdout is a TTY and ``NO_COLOR`` is
unset or empty; a progress line goes to stderr only when it is a TTY.
"""
import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from . import corpus, query, render, schema, tables, walk
from .render import View

DEFAULT_DAYS = 7.0
ALL = "all"

SPEND_NOTE = ("spend is paid per call; context shares are not cost shares. What put"
              " the tokens there is answered by `sa context` (--by tool, --by head).")

# ``window`` is one row per context window: a drill target (--by, --where), never a default table.
VIEWS = {"context": View(metric=schema.CONTEXT_DELTA,
                         tables=(schema.CAUSE_DIM, schema.TOOL_DIM, schema.HEAD_DIM,
                                 schema.AGENT_DIM, schema.SESSION_DIM, schema.PROJECT_DIM),
                         levers=(schema.TOOL_DIM, schema.HEAD_DIM),
                         reconciles=True, notes=(), starts=schema.START_DIM),
         "spend": View(metric=schema.SPEND,
                       tables=(schema.PROJECT_DIM, schema.SESSION_DIM, schema.AGENT_DIM),
                       levers=(schema.AGENT_DIM,),
                       reconciles=False, notes=(SPEND_NOTE,))}


def _days(text: str) -> float:
    if text == ALL:
        return float("inf")
    if not text.endswith("d") or not text[:-1].replace(".", "", 1).isdigit():
        raise argparse.ArgumentTypeError("expected a number of days like 7d, or %s" % ALL)
    return float(text[:-1])


def _directory(text: str) -> Path:
    path = Path(text)
    if not path.is_dir():
        raise argparse.ArgumentTypeError("no such directory: %s" % text)
    return path


def _pair(text: str) -> Tuple[str, str]:
    dim, sep, value = text.partition("=")
    if not sep:
        raise argparse.ArgumentTypeError("expected DIM=VALUE")
    return dim, tables.unhome(value)  # a label printed with ~ for home selects as printed


def _by(text: str) -> str:
    if text != render.FACT and text not in schema.DIMENSIONS:
        raise argparse.ArgumentTypeError("expected %s or a dimension: %s"
                                         % (render.FACT, ", ".join(schema.DIMENSIONS)))
    return text


def _rows(text: str) -> int:
    if not text.isdigit() or int(text) < 1:
        raise argparse.ArgumentTypeError("expected a positive number of rows")
    return int(text)


QUESTIONS = {"context": "what filled your context windows: by cause, tool, command, agent,"
                       " session, project",
             "spend": "what the calls cost, by project, session, agent (never dollars)"}

TOP_HELP = """\
Where did my Claude Code context go, and what did it cost? Reads the
transcripts under ~/.claude/projects, the last 7 days unless --since.

Each table splits one total by one dimension (a cause, a tool, a command);
the row %(residual)s is the part with no value for it. Narrow with
--where DIM=VALUE (any row label), then show one table whole with --by DIM:

  sa context                                 the overview
  sa context --where tool=Bash               narrow to one row
  sa context --where tool=Bash --by head     that row, by command

Flags (sa context --help or sa spend --help for all):
  --since 30d|all       files modified in the last N days (default 7d)
  --where DIM=VALUE     keep one value; repeatable
  --by DIM|fact         one table with whole labels, or the largest facts
  --limit N             rows per table (default 10)
  --root DIR            transcript root (default ~/.claude/projects)

Marked %(marker)s in the output: %(marked)s.
sa explain TERM says what any term means.""" % {
    "residual": schema.RESIDUAL_LABEL, "marker": schema.MARKER,
    "marked": ", ".join(t for t, e in schema.GLOSSARY.items() if e.marked)}


def _dimensions_help() -> str:
    """The dimensions, each with its glossary meaning: what a table and a
    ``--where`` split by."""
    width = max(map(len, schema.DIMENSIONS))
    return "dimensions (--where DIM=VALUE, --by DIM):\n" + "\n".join(
        "  %-*s  %s" % (width, d, schema.GLOSSARY[d].meaning) for d in schema.DIMENSIONS)


def parse_args(argv: Optional[List[str]]) -> argparse.Namespace:
    raw = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(prog="sa", description=TOP_HELP, formatter_class=raw)
    views = parser.add_subparsers(dest="view", metavar="|".join(list(VIEWS) + ["explain"]))
    views.required = True
    for name, view in VIEWS.items():
        sub = views.add_parser(name, help=QUESTIONS[name], description=QUESTIONS[name] + ".",
                               epilog=_dimensions_help(), formatter_class=raw)
        sub.add_argument("--root", type=_directory, default=str(corpus.default_root()),
                         help="corpus root, an existing directory (default: ~/.claude/projects)")
        sub.add_argument("--since", type=_days, metavar="Nd|all",
                         help="select files modified within the last N days, before dedup"
                              " (default: 7d; all: every file)")
        sub.add_argument("--where", action="append", default=[], type=_pair,
                         metavar="DIM=VALUE", help="keep facts with that value; repeatable")
        sub.add_argument("--by", type=_by, metavar="DIM|" + render.FACT,
                         help="one dimension's table, or '%s' for leaf facts" % render.FACT)
        sub.add_argument("--limit", type=_rows, default=10, help="rows per table (at least 1)")
    explain = views.add_parser("explain", help="what a term in the output means",
                               description="What a term in the output means, and why its"
                                           " number might surprise you.")
    explain.add_argument("term", nargs="?", help="one term; all of them when omitted")
    return parser.parse_args(argv)


def explain(term: Optional[str]) -> List[str]:
    """One glossary entry, or every one, each with why it might surprise."""
    terms = [term.rstrip(schema.MARKER)] if term else list(schema.GLOSSARY)
    lines = []
    for name in terms:
        entry = schema.explain(name)
        lines += ["%s: %s" % (tables.marked(name), entry.meaning),
                  "  surprise: " + entry.surprise]
    return lines


def _colour() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.view == "explain":
        try:
            print("\n".join(explain(args.term)))
        except schema.SchemaError as error:
            print("sa explain: error: %s" % tables.home_text(str(error)), file=sys.stderr)
            return 2
        return 0
    view = VIEWS[args.view]
    days = DEFAULT_DAYS if args.since is None else args.since
    since = None if days == float("inf") else days
    if sys.stderr.isatty():
        n = sum(1 for _ in corpus.find_files(Path(args.root), since))
        print("reading %d files under %s ..." % (n, tables.tilde(Path(args.root))),
              end="\r", file=sys.stderr, flush=True)
    loaded = corpus.load(Path(args.root), since)
    if sys.stderr.isatty():
        print("\033[K", end="", file=sys.stderr, flush=True)
    try:
        forest = walk.forest(loaded)
        sel = query.selection(forest, args.where, view.metric, view.reconciles)
        lines = render.report(view, sel, loaded, args.by, args.limit,
                              since_default=args.since is None, forest=forest)
    except schema.SchemaError as error:
        print("sa %s: error: %s" % (args.view, tables.home_text(str(error))), file=sys.stderr)
        return 2
    paint = tables.paint if _colour() else str
    print("\n".join(paint(line) for line in lines))
    return 0 if not view.reconciles or sel.reconciliation.holds else 1
