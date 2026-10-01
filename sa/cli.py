"""``sa context`` and ``sa spend``: plain-text views over the fact list.

Every figure prints with the population it was counted over, every table
shows its residual and signed rows, and the ``context`` view ends with the
reconciliation that proves the increments telescope to the windows' final
occupancy. A mismatch there is an exit status of 1, not a footnote.

Filters: ``--since`` selects FILES by modification time before reading, so
dedup runs over the selected files only; ``--where`` selects facts after
dedup. A ``--where`` on a window dimension (project, session, agent) keeps
whole windows; any other dimension is a drill, and the reconciliation then
applies to the whole-window population it is printed for.
"""
import argparse
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
    return dim, value


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
                         help="only files modified in the last N days (0d: none)")
        sub.add_argument("--where", action="append", default=[], type=_pair,
                         metavar="DIM=VALUE", help="repeatable; dims: %s"
                         % ", ".join(schema.DIMENSIONS))
        sub.add_argument("--by", metavar="DIM|fact",
                         help="one dimension's table, or 'fact' for leaf facts")
        sub.add_argument("--limit", type=int, default=10, help="rows per table")
    args = parser.parse_args(argv)
    carrier = schema.metric(VIEWS[args.view].metric).carrier
    tables = [args.by] if args.by and args.by != "fact" else []
    for dim in [dim for dim, _ in args.where] + tables:
        try:
            schema.check_dimension(dim, carrier)
        except schema.SchemaError as error:
            parser.error(error.args[0])
    return args


def _num(value):
    return format(int(round(value)), ",d")


def _pct(share):
    return "-" if share is None else "%.1f%%" % (100 * share)


def _status(holds):
    return "OK" if holds else "MISMATCH"


def _modified_within(days):
    """A file filter on modification time, or ``None`` for no filter."""
    if days is None:
        return None
    cutoff = time.time() - days * 86400
    return lambda path, project: path.stat().st_mtime >= cutoff


def _table(title, rows, unit, limit):
    # type: (str, List[query.Row], str, int) -> List[str]
    """The top ``limit`` regular rows, one line for the rest so the column
    still adds up, then the residual and signed rows, which are never hidden.
    Shares are of the regular rows' mass, printed once in the header."""
    regular = [r for r in rows if r.kind == query.REGULAR]
    base = sum(r.mass for r in regular)
    shown = regular[:limit]
    hidden = regular[limit:]
    if hidden:
        shown.append(query.Row("+%d more rows" % len(hidden), sum(r.mass for r in hidden),
                               sum(r.count for r in hidden),
                               sum(r.share for r in hidden), query.REGULAR))
    shown += [r for r in rows if r.kind != query.REGULAR]
    labels = [r.value + (" (signed)" if r.kind == query.SIGNED else "") for r in shown]
    width = max(len(label) for label in labels + [title])
    share = "share of %s" % _num(base)
    lines = ["%-*s  %16s  %7s  %s" % (width, title, unit, "count", share)]
    for label, r in zip(labels, shown):
        lines.append("%-*s  %16s  %7d  %*s"
                     % (width, label, _num(r.mass), r.count, len(share), _pct(r.share)))
    return lines


def _leaves(facts, metric, limit):
    # type: (List[schema.Fact], str, int) -> List[str]
    spec = schema.metric(metric)
    leaves = sorted((f for f in facts if f.kind == spec.carrier),
                    key=lambda f: -f.metrics[metric])[:limit]
    lines = ["%16s  file:line  uuid  dimensions" % spec.unit]
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
           _status(r.mass_holds)),
        "intervals %d (= %d calls - %d windows): exact %s + ambiguous %s [%s] + shrink %s: %s"
        % (r.intervals, r.calls, r.windows, rate(r.exact), rate(r.ambiguous),
           reasons or "none", rate(r.shrink), _status(r.count_holds)),
        "exact: the interval's one token-relevant contributor (a tool_result or user"
        " text) after subtracting the previous call's output; bookkeeping attachments"
        " in the interval fold into its remainder [OPEN]",
    ]


def _call_totals(facts, headline_metric):
    # type: (List[schema.Fact], str) -> List[str]
    """Every other call-carried metric: additive ones as totals, peaks as
    the single largest call."""
    lines = []
    for name, spec in schema.METRICS.items():
        if spec.carrier != schema.CALL or name == headline_metric:
            continue
        if spec.aggregation == schema.PEAK:
            top = query.largest(facts, name)
            if top is not None:
                lines.append("%s: largest single call %s %s, at %s:%d"
                             % (name, _num(top.metrics[name]), spec.unit,
                                top.locator.file, top.locator.line))
        else:
            total = sum(f.metrics[name] for f in facts if f.kind == schema.CALL)
            lines.append("%s: %s %s" % (name, _num(total), spec.unit))
    return lines


def main(argv=None):
    args = parse_args(argv)
    view = VIEWS[args.view]
    spec = schema.metric(view.metric)
    loaded = corpus.load(args.root, _modified_within(args.since))
    facts = [f for source in loaded.files for f in walk.walk(source)]
    drill = [p for p in args.where if p[0] not in schema.WINDOW_DIMENSIONS]
    windows = query.select(facts, [p for p in args.where if p[0] in schema.WINDOW_DIMENSIONS])
    selected = query.select(windows, drill) if drill else windows
    carried = [f for f in selected if f.kind == spec.carrier]
    n_windows = len({f.locator.file for f in windows})
    rows = query.group(selected, view.lead, view.metric)

    total = "%s: %s %s" % (view.metric, _num(sum(f.metrics[view.metric] for f in carried)),
                           spec.unit)
    if args.view == "context" and not drill:
        total += " = the %d windows' final occupancies summed" % n_windows
    else:
        total += " over %d %s facts in %d windows" % (len(carried), spec.carrier, n_windows)
    if rows and rows[0].kind == query.REGULAR:
        total += "; top %s=%s %s" % (view.lead, rows[0].value, _pct(rows[0].share))
    population = "population: %d files read%s, %d windows, %d call facts, %d increment " \
                 "facts; %d lines skipped, %d duplicate records excluded%s" % (
                     len(loaded.files),
                     "" if args.since is None else " (modified within %gd)" % args.since,
                     n_windows, sum(f.kind == schema.CALL for f in windows),
                     sum(f.kind == schema.INCREMENT for f in windows),
                     loaded.skipped_lines, loaded.duplicate_records,
                     "".join("; where %s=%s" % p for p in args.where))
    out = [total, population, ""]
    if args.by == "fact":
        out += _leaves(selected, view.metric, args.limit)
    else:
        for dim in [args.by] if args.by else schema.KIND_DIMENSIONS[spec.carrier]:
            rows = query.group(selected, dim, view.metric)
            if any(r.kind == query.REGULAR for r in rows):
                out += _table("by " + dim, rows, spec.unit, args.limit)
                out.append("")
    holds = True
    if args.view == "context":
        reconciliation = query.reconcile(windows)
        holds = reconciliation.holds
        if drill:
            out.append("reconciliation: applies to the %d whole windows above, not to"
                       " this drill: %s" % (n_windows, _status(holds)))
        else:
            out += _reconciliation(reconciliation)
    else:
        out += _call_totals(selected, view.metric)
    print("\n".join(out))
    return 0 if holds else 1
