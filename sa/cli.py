"""``sa context`` and ``sa spend``: plain-text views over the fact list.

Every figure prints with the population it was counted over, every table
shows its residual and signed rows, and the ``context`` view ends with the
reconciliation that proves the increments telescope to the windows' final
occupancy. A mismatch there is an exit status of 1, not a footnote.
"""
import argparse
import sys
import time
from pathlib import Path
from typing import List, NamedTuple, Tuple

from . import corpus, query, schema, walk


class View(NamedTuple):
    metric: str
    lead: str  # the dimension whose top row the headline names


VIEWS = {"context": View("context_delta", "cause"),
         "spend": View("spend", "project")}


def _days(text):
    # type: (str) -> float
    if not text.endswith("d"):
        raise argparse.ArgumentTypeError("expected a number of days like 7d")
    return float(text[:-1])


def _pair(text):
    # type: (str) -> Tuple[str, str]
    dim, sep, value = text.partition("=")
    if not sep:
        raise argparse.ArgumentTypeError("expected DIM=VALUE")
    try:
        return schema.check_dimension(dim), value
    except schema.SchemaError as error:
        raise argparse.ArgumentTypeError(error.args[0])


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="sa", description="Where did my context go, and what did it cost.")
    views = parser.add_subparsers(dest="view", metavar="|".join(VIEWS))
    views.required = True
    for name, view in VIEWS.items():
        sub = views.add_parser(name, help="total %s by every dimension" % view.metric)
        sub.add_argument("--root", type=Path, default=corpus.default_root(),
                         help="corpus root (default: ~/.claude/projects)")
        sub.add_argument("--since", type=_days, metavar="Nd",
                         help="only files modified in the last N days")
        sub.add_argument("--project", metavar="SUBSTR",
                         help="only projects whose directory name contains SUBSTR")
        sub.add_argument("--session", metavar="ID", help="only this sessionId")
        sub.add_argument("--where", action="append", default=[], type=_pair,
                         metavar="DIM=VALUE", help="repeatable; dims: %s"
                         % ", ".join(schema.DIMENSIONS))
        sub.add_argument("--by", metavar="DIM|fact",
                         help="one dimension's table, or 'fact' for leaf facts")
        sub.add_argument("--limit", type=int, default=10, help="rows per table")
    return parser.parse_args(argv)


def _file_filter(args):
    cutoff = time.time() - args.since * 86400 if args.since else None

    def keep(path, project):
        if args.project and args.project not in project:
            return False
        return cutoff is None or path.stat().st_mtime >= cutoff
    return keep


def _num(value):
    return format(int(round(value)), ",d")


def _pct(share):
    return "-" if share is None else "%.1f%%" % (100 * share)


def _table(title, rows, unit):
    # type: (str, List[query.Row], str) -> List[str]
    labels = [r.value + (" (signed)" if r.signed else "") for r in rows]
    width = max(len(label) for label in labels + [title])
    lines = ["%-*s  %16s  %7s  %6s" % (width, title, unit, "count", "share")]
    for label, r in zip(labels, rows):
        lines.append("%-*s  %16s  %7d  %6s"
                     % (width, label, _num(r.mass), r.count, _pct(r.share)))
    return lines


def _limited(rows, limit):
    # type: (List[query.Row], int) -> List[query.Row]
    """The top ``limit`` regular rows; the residual and signed rows always stay."""
    regular = [r for r in rows if r.share is not None]
    return regular[:limit] + rows[len(regular):]


def _leaves(facts, metric, limit):
    # type: (List[schema.Fact], str, int) -> List[str]
    carrier = schema.metric(metric).carrier
    leaves = sorted((f for f in facts if f.kind == carrier),
                    key=lambda f: -f.metrics[metric])[:limit]
    lines = []
    for f in leaves:
        tags = " ".join("%s=%s" % (d, f.dims[d]) for d in schema.DIMENSIONS
                        if d in f.dims and d not in schema.WINDOW_DIMENSIONS)
        lines.append("%16s  %s:%d  %s  %s" % (_num(f.metrics[metric]), f.locator.file,
                                              f.locator.line, f.locator.uuid, tags))
    return lines


def _reconciliation(r):
    # type: (query.Reconciliation) -> List[str]
    terms = " + ".join("%s %s" % (c, _num(r.by_cause[c])) for c in schema.CAUSES)
    reasons = ", ".join("%s %d" % (k, v) for k, v in r.by_reason.items() if v)

    def rate(n):
        return "%d (%.1f%%)" % (n, 100.0 * n / r.intervals) if r.intervals else "0"
    return [
        "reconciliation over %d windows: %s = %s; final occupancy %s: %s"
        % (r.windows, terms, _num(r.booked), _num(r.final_occupancy),
           "OK" if r.holds else "MISMATCH"),
        "intervals %d: exact %s, ambiguous %s [%s], shrink %s"
        % (r.intervals, rate(r.exact), rate(r.ambiguous), reasons or "none",
           rate(r.shrink)),
    ]


def _call_totals(windows, headline_metric):
    # type: (List[schema.Fact], str) -> List[str]
    """Every other call-carried metric: additive ones as totals, peaks as
    the single largest window."""
    lines = []
    for name, spec in schema.METRICS.items():
        if spec.carrier != schema.CALL or name == headline_metric:
            continue
        if spec.aggregation == schema.PEAK:
            top = query.largest(windows, name)
            if top is not None:
                lines.append("%s: largest single window %s %s, in %s"
                             % (name, _num(top.metrics[name]), spec.unit,
                                top.locator.file))
        else:
            total = sum(f.metrics[name] for f in windows if f.kind == schema.CALL)
            lines.append("%s: %s %s" % (name, _num(total), spec.unit))
    return lines


def main(argv=None):
    args = parse_args(argv)
    view = VIEWS[args.view]
    loaded = corpus.load(args.root, _file_filter(args))
    facts = [f for source in loaded.files for f in walk.walk(source)]
    where = list(args.where) + ([("session", args.session)] if args.session else [])
    windows = query.select(facts, [p for p in where if p[0] in schema.WINDOW_DIMENSIONS])
    selected = query.select(windows, where)
    spec = schema.metric(view.metric)
    carried = [f for f in selected if f.kind == spec.carrier]
    rows = query.group(selected, view.lead, view.metric)

    out = ["%s: %s %s" % (view.metric, _num(sum(f.metrics[view.metric] for f in carried)),
                          spec.unit)]
    if rows and rows[0].share is not None:
        out[0] += "; top %s=%s %s" % (view.lead, rows[0].value, _pct(rows[0].share))
    out.append("population: %d files read, %d windows, %d call facts, %d increment "
               "facts; %d lines skipped, %d duplicate records dropped"
               % (len(loaded.files), len({f.locator.file for f in windows}),
                  sum(f.kind == schema.CALL for f in windows),
                  sum(f.kind == schema.INCREMENT for f in windows),
                  loaded.skipped_lines, loaded.duplicate_records))
    if where:
        out.append("where: " + " ".join("%s=%s" % p for p in where))
    out.append("")
    if args.by == "fact":
        out += _leaves(selected, view.metric, args.limit)
    else:
        for dim in [args.by] if args.by else schema.DIMENSIONS:
            rows = query.group(selected, dim, view.metric)
            if any(r.share is not None for r in rows):
                out += _table("by " + dim, _limited(rows, args.limit), spec.unit)
                out.append("")
    holds = True
    if args.view == "context":
        reconciliation = query.reconcile(windows)
        holds = reconciliation.holds
        out += _reconciliation(reconciliation)
    else:
        out += _call_totals(windows, view.metric)
    print("\n".join(out))
    return 0 if holds else 1
