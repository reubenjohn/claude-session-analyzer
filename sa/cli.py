"""``sa context`` and ``sa spend``: parse the arguments, select the facts,
print the view, exit 1 if the reconciliation did not hold.

Every figure prints with the population it was counted over, every table
shows its residual and signed rows, and the ``context`` view ends with the
reconciliation of the increments against the windows' final occupancy. It
is a regression guard: ``walk`` books every interval's whole delta, so it
holds by construction, and a MISMATCH is a bug in this tool, exit status 1.

Filters: ``--root`` must be an existing directory (a typo is a refusal,
never a zero headline); ``--since`` selects FILES by modification time
before reading, so dedup runs over the selected files only, and a day
count that keeps no file is a legitimate empty population; ``--where``
selects facts after dedup. A ``--where`` on a window dimension (project, session, agent,
window) keeps whole windows; any other dimension is a drill, and the
reconciliation and the single-call peak then apply to the whole-window
population they are printed for. What ``query`` refuses (an unknown name,
an undeclared value, a pair no fact carries) is exit status 2 with its
message; nothing is checked twice.
"""
import argparse
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

from . import corpus, query, render, schema, walk
from .render import View

SPEND_NOTE = ("spend is paid per call; context shares are not cost shares. What put"
              " the tokens there is answered by `sa context` (--by tool, --by head).")

# ``window`` is one row per file: a drill target (--by, --where), never a default table.
VIEWS = {"context": View(metric=schema.CONTEXT_DELTA,
                         tables=(schema.CAUSE_DIM, schema.TOOL_DIM, schema.HEAD_DIM,
                                 schema.AGENT_DIM, schema.SESSION_DIM, schema.PROJECT_DIM),
                         levers=(schema.TOOL_DIM, schema.HEAD_DIM),
                         reconciles=True, notes=()),
         "spend": View(metric=schema.SPEND,
                       tables=(schema.PROJECT_DIM, schema.SESSION_DIM, schema.AGENT_DIM),
                       levers=(schema.AGENT_DIM,),
                       reconciles=False, notes=(SPEND_NOTE,))}


def _days(text: str) -> float:
    if not text.endswith("d") or not text[:-1].replace(".", "", 1).isdigit():
        raise argparse.ArgumentTypeError("expected a number of days like 7d")
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
    return dim, value


def _rows(text: str) -> int:
    if not text.isdigit() or int(text) < 1:
        raise argparse.ArgumentTypeError("expected a positive number of rows")
    return int(text)


def parse_args(argv: Optional[List[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sa", description="Where did my context go, and what did it cost.")
    views = parser.add_subparsers(dest="view", metavar="|".join(VIEWS))
    views.required = True
    for name, view in VIEWS.items():
        sub = views.add_parser(name, help="total %s by every dimension" % view.metric)
        sub.add_argument("--root", type=_directory, default=str(corpus.default_root()),
                         help="corpus root, an existing directory (default: ~/.claude/projects)")
        sub.add_argument("--since", type=_days, metavar="Nd",
                         help="files modified within the last N days")
        sub.add_argument("--where", action="append", default=[], type=_pair,
                         metavar="DIM=VALUE", help="repeatable; dims: %s"
                         % ", ".join(schema.DIMENSIONS))
        sub.add_argument("--by", metavar="DIM|fact",
                         help="one dimension's table, or 'fact' for leaf facts")
        sub.add_argument("--limit", type=_rows, default=10, help="rows per table (at least 1)")
    return parser.parse_args(argv)


def _modified_within(days: Optional[float]) -> Optional[corpus.Keep]:
    """A file filter on modification time, or ``None`` for no filter."""
    if days is None:
        return None
    cutoff = time.time() - days * 86400
    return lambda path: path.stat().st_mtime >= cutoff


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    view = VIEWS[args.view]
    loaded = corpus.load(args.root, _modified_within(args.since))
    try:
        sel = query.selection(walk.forest(loaded), args.where, view.metric)
        lines = render.report(view, sel, render.population(view, sel, loaded, args.root, args.since),
                              args.by, args.limit)
    except schema.SchemaError as error:
        print("sa %s: error: %s" % (args.view, error.args[0]), file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0 if not view.reconciles or sel.reconciliation.holds else 1
