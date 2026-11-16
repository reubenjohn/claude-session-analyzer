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
``--where`` pin on a window dimension (project, session, subagent, window,
started_by) keeps whole windows; any other dimension is a drill, and the reconciliation and
the single-call peak then apply to the whole-window population they are
printed for. What ``query`` refuses (an unknown name, an undeclared value,
an open-vocabulary value no fact carries) is exit status 2 with its
message; nothing is checked twice.

``sa explain [TERM]`` prints the glossary (``glossary.GLOSSARY``); an unknown
term is exit status 2. ``--color`` (``style.enabled``): auto, the default,
colours only when stdout is a TTY or ``FORCE_COLOR`` is set, never while
``NO_COLOR`` is; a progress line goes to stderr only when it is a TTY.
"""
import argparse
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from . import corpus, glossary, query, render, schema, style, tables, walk
from .render import View

DEFAULT_DAYS = 7.0
DEFAULT_LIMIT = 5  # rows per table
ALL = "all"

PROG = glossary.PROG
SPEND_NOTE = "paid per call, so no context share is a cost share; what filled it: %s context" % PROG

# ``window`` is one row per context window: a drill target (--by, --where), never a default table.
VIEWS = {"context": View(metric=schema.CONTEXT_DELTA,
                         tables=(schema.CAUSE_DIM, schema.TOOL_DIM, schema.COMMAND_DIM,
                                 schema.SUBAGENT_DIM, schema.SESSION_DIM, schema.PROJECT_DIM),
                         levers=(schema.TOOL_DIM, schema.COMMAND_DIM),
                         reconciles=True, notes=(), starts=schema.STARTED_BY_DIM),
         "spend": View(metric=schema.SPEND,
                       tables=(schema.PROJECT_DIM, schema.SESSION_DIM, schema.SUBAGENT_DIM),
                       levers=(schema.SUBAGENT_DIM,),
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


QUESTIONS = {"context": "what filled your context windows: by cause, tool, command, subagent,"
                       " session, project",
             "spend": "what the calls cost, by project, session, subagent (never dollars)"}

TOP_HELP = """\
Where did my Claude Code context go, and what did it cost? Reads the
transcripts under ~/.claude/projects, the last 7 days unless --since.

Subcommands: context, spend, explain. Each table splits one total by one
dimension (a cause, a tool, a command); the row %(residual)s is the part with
no value for it. Pin a row with --where DIM=VALUE (any row label), then
show one table whole with --by DIM:

  %(prog)s context                                   the overview
  %(prog)s context --where tool=Bash                 pin one row
  %(prog)s context --where tool=Bash --by command    that row, by command

Flags (all: %(prog)s context --help, %(prog)s spend --help):
  --since 30d|all       files modified in the last N days (default 7d)
  --where DIM=VALUE     pin one value; repeatable
  --by DIM|fact         one table whole; fact: individual changes, one per row
  --limit N             rows per table (default %(limit)d; causes print whole)
  --root DIR            transcript root (default ~/.claude/projects)

Marked %(marker)s in the output: %(marked)s.
%(prog)s explain TERM says what any term means.""" % {"prog": PROG,
    "residual": glossary.RESIDUAL_LABEL, "marker": glossary.MARKER, "limit": DEFAULT_LIMIT,
    "marked": ", ".join(glossary.printed(t) for t, e in glossary.GLOSSARY.items() if e.marked)}


def _dimensions_help() -> str:
    """The dimensions, each with its glossary meaning: what a table and a
    ``--where`` split by."""
    width = max(map(len, schema.DIMENSIONS))
    return "dimensions (--where DIM=VALUE, --by DIM):\n" + "\n".join(
        "  %-*s  %s" % (width, d, glossary.GLOSSARY[d].meaning) for d in schema.DIMENSIONS)


def parse_args(argv: Optional[List[str]]) -> argparse.Namespace:
    raw = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(prog=PROG, description=TOP_HELP, formatter_class=raw)
    views = parser.add_subparsers(dest="view", title="subcommands",
                                  metavar="|".join(list(VIEWS) + ["explain"]))
    views.required = True
    for name, view in VIEWS.items():
        sub = views.add_parser(name, help=QUESTIONS[name], description=QUESTIONS[name] + ".",
                               epilog=_dimensions_help(), formatter_class=raw)
        sub.add_argument("--root", type=_directory, default=str(corpus.default_root()),
                         help="transcript root (default: ~/.claude/projects)")
        sub.add_argument("--since", type=_days, metavar="Nd|all",
                         help="files modified in the last N days, before dedup (default 7d;"
                              " all: any age)")
        sub.add_argument("--where", action="append", default=[], type=_pair,
                         metavar="DIM=VALUE", help="pin a value; repeatable")
        sub.add_argument("--by", type=_by, metavar="DIM|" + render.FACT,
                         help="a dimension's table, or '%s': individual %s, one per row,"
                              " with locators" % (render.FACT, schema.PLURAL[schema.metric(view.metric).carrier]))
        sub.add_argument("--limit", type=_rows, default=DEFAULT_LIMIT,
                         help="rows per table (default %d); the cause table, unassigned and"
                              " rows that can be negative (shrink) always show" % DEFAULT_LIMIT)
        sub.add_argument("--color", choices=(style.AUTO, style.ALWAYS, style.NEVER), default=style.AUTO,
                         help="auto (default): on a terminal, unless NO_COLOR is set")
    explain = views.add_parser("explain", help="what a term in the output means",
                               description="What a term in the output means, and why its"
                                           " number might surprise you.")
    explain.add_argument("term", nargs="?", help="one term; all of them when omitted")
    return parser.parse_args(argv)


def explain(term: Optional[str]) -> List[str]:
    """One glossary entry, or every one, each with why it might surprise."""
    terms = [glossary.key_of(term)] if term else list(glossary.GLOSSARY)
    lines = []
    for name in terms:
        entry = glossary.explain(name)
        lines += ["%s: %s" % (glossary.marked(name), entry.meaning),
                  "  surprise: " + entry.surprise]
        if name == glossary.RESIDUAL_LABEL:  # what it holds in each table
            lines += ["  by %s: %s" % (d, tables.residual_cases(d)) for d in tables.RESIDUAL_NOTES]
    return lines


def _colour(choice: str = style.AUTO) -> bool:
    return style.enabled(choice, sys.stdout.isatty())


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.view == "explain":
        try:
            print("\n".join(explain(args.term)))
        except schema.SchemaError as error:
            print("%s explain: error: %s" % (PROG, tables.home_text(str(error))), file=sys.stderr)
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
        names = render.subagent_names(loaded.agent_types, forest)
        printed = {label: id_ for id_, label in names.items()}  # a subagent pins by its name or id
        where = [(d, printed.get(v, v) if d == schema.SUBAGENT_DIM else v) for d, v in args.where]
        sel = query.selection(forest, where, view.metric, view.reconciles)
        lines = render.report(view, sel, loaded, args.by, args.limit,
                              since_default=args.since is None, forest=forest, names=names)
    except schema.SchemaError as error:
        print("%s %s: error: %s" % (PROG, args.view, tables.home_text(str(error))), file=sys.stderr)
        return 2
    paint = style.Painter(render.tools(view, sel), style.depth()).paint if _colour(args.color) else str
    print("\n".join(paint(line) for line in lines))
    return 0 if not view.reconciles or sel.reconciliation.holds else 1
