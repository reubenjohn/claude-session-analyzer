"""``sa context`` and ``sa spend``: parse the arguments, select the facts,
print the view, exit 1 if the reconciliation did not hold.

Every figure prints with the population it was counted over, every table
shows its residual and signed rows, and the ``context`` view ends with the
reconciliation that proves the increments telescope to the windows' final
occupancy. A mismatch there is an exit status of 1, not a footnote.

Filters: ``--since`` selects FILES by modification time before reading, so
dedup runs over the selected files only; ``--where`` selects facts after
dedup. A ``--where`` on a window dimension (project, session, agent) keeps
whole windows; any other dimension is a drill, and the reconciliation and
the single-call peak then apply to the whole-window population they are
printed for.
"""
import argparse
import time
from pathlib import Path
from typing import List, Optional, Tuple

from . import corpus, query, render, schema, walk
from .render import VIEWS, Selection


def _days(text: str) -> float:
    if not text.endswith("d") or not text[:-1].replace(".", "", 1).isdigit():
        raise argparse.ArgumentTypeError("expected a number of days like 7d")
    return float(text[:-1])


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
        sub.add_argument("--root", type=Path, default=corpus.default_root(),
                         help="corpus root (default: ~/.claude/projects)")
        sub.add_argument("--since", type=_days, metavar="Nd",
                         help="files modified within the last N days")
        sub.add_argument("--where", action="append", default=[], type=_pair,
                         metavar="DIM=VALUE", help="repeatable; dims: %s"
                         % ", ".join(schema.DIMENSIONS))
        sub.add_argument("--by", metavar="DIM|fact",
                         help="one dimension's table, or 'fact' for leaf facts")
        sub.add_argument("--limit", type=_rows, default=10, help="rows per table (at least 1)")
    args = parser.parse_args(argv)
    carrier = schema.metric(VIEWS[args.view].metric).carrier
    try:
        for dim, value in args.where:
            schema.check_value(schema.check_dimension(dim, carrier), value)
        if args.by and args.by != "fact":
            schema.check_dimension(args.by, carrier)
    except schema.SchemaError as error:
        parser.error(error.args[0])
    return args


def _modified_within(days: Optional[float]) -> Optional[corpus.Keep]:
    """A file filter on modification time, or ``None`` for no filter."""
    if days is None:
        return None
    cutoff = time.time() - days * 86400
    return lambda path: path.stat().st_mtime >= cutoff


def _select(root: Path, since: Optional[float], where: List[Tuple[str, str]],
            metric: str) -> Selection:
    loaded = corpus.load(root, _modified_within(since))
    facts = [f for source in loaded.files for f in walk.walk(source)]
    whole = [p for p in where if p[0] in schema.WINDOW_DIMENSIONS]
    window_facts = query.select(facts, whole)
    kept = query.select(window_facts, where)
    return Selection(root, since, where, loaded, window_facts, kept, query.total(kept, metric))


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    view = VIEWS[args.view]
    sel = _select(args.root, args.since, args.where, view.metric)
    lines, holds = render.report(view, sel, args.by, args.limit)
    print("\n".join(lines))
    return 0 if holds else 1
