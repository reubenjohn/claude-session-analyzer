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
from typing import Iterator, List, NamedTuple, Optional, Tuple

from . import corpus, query, schema, walk
from .schema import Fact


class View(NamedTuple):
    metric: str
    tables: Tuple[str, ...]  # printed by default; the first one not pinned by --where leads


VIEWS = {"context": View("context_delta", ("cause", "tool", "head", "agent", "session", "project")),
         "spend": View("spend", schema.WINDOW_DIMENSIONS)}

SPEND_NOTE = ("spend is paid per call; context shares are not cost shares. What put"
              " the tokens there is answered by `sa context` (--by tool, --by head).")

# Printed under a table whose row needs saying what it is.
NOTES = {schema.WINDOW_HEAD: "first call's context: boot prompt + first message, or"
                             " inherited parent context for a fork; not splittable by"
                             " content"}


def _days(text: str) -> float:
    if not text.endswith("d"):
        raise argparse.ArgumentTypeError("expected a number of days like 7d")
    return float(text[:-1])


def _pair(text: str) -> Tuple[str, str]:
    dim, sep, value = text.partition("=")
    if not sep:
        raise argparse.ArgumentTypeError("expected DIM=VALUE")
    return dim, value


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


def _num(value: float) -> str:
    return format(int(round(value)), ",d")


def _pct(share: Optional[float]) -> str:
    return "-" if share is None else "%.1f%%" % (100 * share)


def _status(holds: bool) -> str:
    return "OK" if holds else "MISMATCH"


def _at(locator: schema.Locator) -> str:
    return "%s:%d" % (locator.file, locator.line)


def _modified_within(days: Optional[float]) -> Optional[corpus.Keep]:
    """A file filter on modification time, or ``None`` for no filter."""
    if days is None:
        return None
    cutoff = time.time() - days * 86400
    return lambda path, project: path.stat().st_mtime >= cutoff


class Selection(NamedTuple):
    loaded: corpus.Corpus
    windows: List[Fact]             # whole windows kept by the window-dimension filters
    facts: List[Fact]               # the windows' facts kept by the drill filters too
    drill: List[Tuple[str, str]]    # the --where pairs that are not window dimensions

    @property
    def n_windows(self) -> int:
        return len({f.locator.file for f in self.windows})


def _select(args: argparse.Namespace) -> Selection:
    loaded = corpus.load(args.root, _modified_within(args.since))
    facts = [f for source in loaded.files for f in walk.walk(source)]
    whole = [p for p in args.where if p[0] in schema.WINDOW_DIMENSIONS]
    drill = [p for p in args.where if p[0] not in schema.WINDOW_DIMENSIONS]
    windows = query.select(facts, whole)
    return Selection(loaded, windows, query.select(windows, drill), drill)


def _headline_dimension(args: argparse.Namespace, view: View) -> Optional[str]:
    """The dimension the headline names: ``--by`` when it is one, else the
    first default table not pinned by ``--where`` (whose top row would be
    the filter itself)."""
    if args.by and args.by != "fact":
        return args.by
    pinned = {dim for dim, _ in args.where}
    return next((dim for dim in view.tables if dim not in pinned), None)


def _headline(args: argparse.Namespace, view: View, sel: Selection) -> List[str]:
    spec = schema.metric(view.metric)
    carried = [f for f in sel.facts if f.kind == spec.carrier]
    total = "%s: %s %s" % (view.metric, _num(sum(f.metrics[view.metric] for f in carried)),
                           spec.unit)
    if args.view == "context" and not sel.drill:
        total += " = the %d windows' final occupancies summed" % sel.n_windows
    else:
        total += " over %d %s facts in %d windows" % (len(carried), spec.carrier, sel.n_windows)
    dim = _headline_dimension(args, view)
    if dim:
        top = next((r for r in query.group(sel.facts, dim, view.metric)
                    if r.kind == query.REGULAR), None)
        if top:
            total += "; top %s=%s %s" % (dim, top.value, _pct(top.share))
    lines = [total]
    if args.view == "context":
        lines += _peaks(sel.windows)
    else:
        lines.append(SPEND_NOTE)
    return lines


def _peaks(facts: List[Fact]) -> List[str]:
    """Every peak metric as the single call where it happened: a peak reports
    no value at a node and is never summed."""
    lines = []
    for name, spec in schema.METRICS.items():
        if spec.aggregation == schema.PEAK:
            top = query.largest(facts, name)
            if top is not None:
                lines.append("single-call peak %s: %s %s at %s"
                             % (name, _num(top.metrics[name]), spec.unit, _at(top.locator)))
    return lines


def _population(args: argparse.Namespace, sel: Selection) -> str:
    return ("population: root %s; %d files read%s, %d windows, %d call facts, %d increment"
            " facts; %d lines skipped, %d duplicate records excluded%s"
            % (args.root, len(sel.loaded.files),
               "" if args.since is None else " (modified within %gd)" % args.since,
               sel.n_windows, sum(f.kind == schema.CALL for f in sel.windows),
               sum(f.kind == schema.INCREMENT for f in sel.windows),
               sel.loaded.skipped_lines, sel.loaded.duplicate_records,
               "".join("; where %s=%s" % p for p in args.where)))


def _table(title: str, rows: List[query.Row], unit: str, limit: int) -> List[str]:
    """The top ``limit`` regular rows, one line for the rest so the column
    still adds up, then the residual and signed rows, which are never hidden.
    Shares are of the regular rows' mass, printed once in the header; a
    table with no regular rows has no base and its header says just "share"."""
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
    share = "share of %s" % _num(base) if base else "share"
    lines = ["%-*s  %16s  %7s  %s" % (width, title, unit, "count", share)]
    for label, r in zip(labels, shown):
        lines.append("%-*s  %16s  %7d  %*s"
                     % (width, label, _num(r.mass), r.count, len(share), _pct(r.share)))
    lines += ["%s: %s" % (r.value, NOTES[r.value]) for r in shown if r.value in NOTES]
    return lines


def _tables(args: argparse.Namespace, view: View, sel: Selection) -> List[str]:
    unit = schema.metric(view.metric).unit
    if args.by == "fact":
        return _leaves(sel.facts, view.metric, args.limit)
    lines = []
    for dim in [args.by] if args.by else view.tables:
        rows = query.group(sel.facts, dim, view.metric)
        if rows:
            lines += _table("by " + dim, rows, unit, args.limit) + [""]
    return lines


def _leaves(facts: List[Fact], metric: str, limit: int) -> List[str]:
    """The ``limit`` largest facts, each with its dimensions and, indented
    under it, its evidence: the candidate contributors of an ambiguous
    increment, the parent of a fork's window head."""
    spec = schema.metric(metric)
    leaves = sorted((f for f in facts if f.kind == spec.carrier),
                    key=lambda f: -f.metrics[metric])[:limit]
    lines = ["%16s  file:line  uuid  dimensions" % spec.unit]
    for f in leaves:
        tags = " ".join("%s=%s" % (d, f.dims[d]) for d in schema.DIMENSIONS if d in f.dims)
        lines.append("%16s  %s  %s  %s" % (_num(f.metrics[metric]), _at(f.locator),
                                           f.locator.uuid, tags))
        lines += list(_evidence(f.evidence))
    return lines


def _evidence(evidence: dict) -> Iterator[str]:
    for key, value in evidence.items():
        for item in value if isinstance(value, list) else [value]:
            shown = "%s %s" % (_at(item), item.uuid) if isinstance(item, schema.Locator) else item
            yield "%18s%s: %s" % ("", key, shown)


def _reconciliation(r: query.Reconciliation) -> List[str]:
    terms = " + ".join("%s %s" % (c, _num(r.by_cause[c])) for c in schema.CAUSES)
    reasons = ", ".join("%s %d" % (k, v) for k, v in r.by_reason.items() if v)

    def rate(n: int) -> str:
        return "%d (%.1f%%)" % (n, 100.0 * n / r.intervals) if r.intervals else "0"
    return [
        "reconciliation over %d windows: %s = %s; final occupancy %s: %s"
        % (r.windows, terms, _num(r.booked), _num(r.final_occupancy),
           _status(r.mass_holds)),
        "intervals %d (= %d calls - %d windows): exact %s + ambiguous %s [%s] + shrink %s: %s"
        % (r.intervals, r.calls, r.windows, rate(r.exact), rate(r.ambiguous),
           reasons or "none", rate(r.shrink), _status(r.count_holds)),
        "exact: the interval's one token-relevant contributor (a tool_result or user"
        " text) after subtracting the previous call's output. Exact given the"
        " feed-forward model; bookkeeping attachments are folded into the single"
        " contributor's remainder.",
    ]


def _call_totals(facts: List[Fact], headline_metric: str) -> List[str]:
    """Every other call-carried metric: additive ones as totals, peaks as
    the single largest call."""
    lines = []
    for name, spec in schema.METRICS.items():
        if spec.carrier == schema.CALL and spec.aggregation == schema.ADDITIVE \
                and name != headline_metric:
            total = sum(f.metrics[name] for f in facts if f.kind == schema.CALL)
            lines.append("%s: %s %s" % (name, _num(total), spec.unit))
    return lines + _peaks(facts)


def _footer(args: argparse.Namespace, view: View, sel: Selection) -> Tuple[List[str], bool]:
    """The closing lines and whether the reconciliation held."""
    if args.view != "context":
        return _call_totals(sel.facts, view.metric), True
    reconciliation = query.reconcile(sel.windows)
    if sel.drill:
        return ["reconciliation: applies to the %d whole windows above, not to this"
                " drill: %s" % (sel.n_windows, _status(reconciliation.holds))], \
               reconciliation.holds
    return _reconciliation(reconciliation), reconciliation.holds


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    view = VIEWS[args.view]
    sel = _select(args)
    footer, holds = _footer(args, view, sel)
    print("\n".join(_headline(args, view, sel) + [_population(args, sel), ""]
                    + _tables(args, view, sel) + footer))
    return 0 if holds else 1
