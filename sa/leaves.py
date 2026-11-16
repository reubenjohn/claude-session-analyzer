"""``by change`` (context) and ``by call`` (spend): the facts a figure
sums, every one, grouped under the window they belong to, each row with
what its figure needs to be recomputed (UX_PRINCIPLES 3): under a
per-call metric a change's ``tokens`` and ``held`` (the calls that held
it), whose product over the calls in view is its part of the average.
The list closes with a Σ line reconciled to the headline, ``✓`` only
when that arithmetic, redone from the printed operands, holds.

A row stays within the line budget: the window's file and dimensions
print once above its rows, the locator is ``:line`` in it (a physical
line is unique in its file, so no uuid), and a row's dimensions print as
the pins they are (UX_PRINCIPLES 1), each one the fact has but a pin's:
one layout whatever is pinned, nothing a row has left unsaid."""
import posixpath
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Tuple

from . import glossary, grammar, query, schema, style
from .schema import Fact
from .tables import OK_MARK, BAD_MARK, WIDTH, command_lines, count, num, value

HELD = "calls held"  # the column of the calls that held a change
DIMENSIONS = "dimensions"  # a row's own, as pins: every one but those pinned, so each pastes as printed
# The window's own dimensions, named on its header when they vary; the
# file names its project, session and subagent.
HEADER_DIMS = (schema.WINDOW_DIM, schema.STARTED_BY_DIM, schema.PEAK_DIM)
ROW_DIMS = (schema.CAUSE_DIM, schema.REASON_DIM, schema.TOOL_DIM, schema.COMMAND_DIM)


def held(f: Fact) -> Optional[int]:
    """The calls that held a change: its held tokens over its tokens; None
    for a change of no tokens, which no call's size counts."""
    delta = f.metrics.get(schema.CONTEXT_DELTA)
    return int(round(f.metrics[schema.CONTEXT_HELD] / delta)) if delta else None


def _varying(facts: Sequence[Fact], dims: Sequence[str], pinned: Sequence[str]) -> List[str]:
    """The window dimensions its header names: those that vary, unpinned."""
    return [d for d in dims if d not in pinned and len({f.dims.get(d) for f in facts}) > 1]


def leaves(facts: List[Fact], metric: str, calls: Optional[int], total: float,
           pinned: Sequence[str] = (), names: Optional[Dict[str, str]] = None,
           limit: Optional[int] = None, more: Optional[Callable[[Optional[str]], str]] = None,
           root: str = "") -> List[str]:
    """Every carrier fact under its window's header, windows by their
    facts' |figure| summed, largest first, and within one the largest
    |figure| first (a shrink is as large as its size); evidence indented
    under its row. Past ``limit`` windows, the rest fold into one ``+N
    more windows`` line, their facts and figure summed, with ``more(None)``,
    the command that lists every window; while several windows print, each
    lists its ``2 × limit`` largest facts, the rest folded alike with
    ``more(window)``, the command that lists them all. Then the Σ line,
    over every fact, against ``total``, the headline's. The directory the
    windows' files share, under ``root``, prints once; each file under it
    as it is on disk, so ``cd`` there and it opens as printed."""
    spec = schema.metric(metric)
    per_call = spec.aggregation == schema.PER_CALL
    divisor = query.per(metric, calls)  # a per-call metric without its population raises
    carried = [f for f in facts if f.kind == spec.carrier]
    by_window: Dict[schema.WindowKey, List[Fact]] = {}
    for f in carried:
        by_window.setdefault(f.window, []).append(f)
    order = sorted(by_window, key=lambda k: -sum(abs(f.metrics[metric]) for f in by_window[k]))
    heads = _varying(carried, HEADER_DIMS, pinned)
    if schema.WINDOW_DIM not in heads:
        heads.insert(0, schema.WINDOW_DIM)
    dims = [d for d in ROW_DIMS if d not in pinned] if spec.carrier == schema.INCREMENT else []
    names_ = [glossary.printed(metric)] + (["tokens", HELD] if per_call else []) + ["line"]

    def figures(f: Fact) -> List[str]:
        n = held(f) if per_call else None
        return [num(f.metrics[metric] / divisor)] + (
            [num(f.metrics[schema.CONTEXT_DELTA]), "-" if n is None else num(n)] if per_call else []) + [
            ":%d" % f.locator.line]
    rows = {id(f): figures(f) + [" ".join(grammar.quote("%s=%s" % (d, value(d, f.dims[d], names)))
                                          for d in dims if d in f.dims)] for f in carried}
    header = names_ + ([DIMENSIONS] if dims else [])
    widths = [max([len(h)] + [len(r[i]) for r in rows.values()]) for i, h in enumerate(names_)]
    lead, figs = 2, len(names_) - 1

    def line(cells: List[str]) -> str:  # the figures right-aligned, the line left, the dimensions as pins
        return (" " * lead + "  ".join("%*s" % (w, c) for w, c in zip(widths[:figs], cells[:figs]))
                + "  " + "  ".join(["%-*s" % (widths[figs], cells[figs])] + cells[len(names_):])).rstrip()
    hidden = order[limit:] if limit is not None else []
    shown = order[:len(order) - len(hidden)]
    title = "by %s" % ("change" if spec.carrier == schema.INCREMENT else "call")
    common, head = _under(title, root, [k.file for k in shown])
    lines = [style.tag(h, style.HEADER) for h in head] + [style.tag(line(header), style.HEADER)]
    said: List[str] = []  # the candidates' order is said once
    noun = schema.PLURAL[spec.carrier]

    def folded(rest: List[Fact], what: str, command: str) -> List[str]:
        text = "%s, %s %s: " % (what, glossary.printed(metric), num(sum(f.metrics[metric] for f in rest) / divisor))
        return [text + command] if len(text + command) <= WIDTH else [text.rstrip(": ") + ":"] + command_lines(
            "    ", command)
    for key in shown:
        mine = sorted(by_window[key], key=lambda f: -abs(f.metrics[metric]))
        cut = mine[2 * limit:] if limit is not None and len(order) > 1 and more else []
        mine = mine[:len(mine) - len(cut)]
        dims_of = mine[0].dims
        tags = "  ".join("%s=%s" % (d, schema.window_value(key) if d == schema.WINDOW_DIM else dims_of.get(d))
                         for d in heads)
        path = posixpath.relpath(key.file, common or ".")
        lines += _window_head("./" + path if path.startswith("-") else path, tags)  # never read as a flag
        for f in mine:
            text = line(rows[id(f)])
            for part in _fit(text, lead + sum(w + 2 for w in widths[:len(names_)])):
                lines.append(style.tag(part, "", values=((0, len(part)),)))
            lines += list(_evidence(f.evidence, key.file, said))
        if cut:
            lines += folded(cut, "  +%s more %s" % (format(len(cut), ",d"), noun), more(schema.window_value(key)))
    if hidden and more:
        rest = [f for k in hidden for f in by_window[k]]
        lines += folded(rest, "+%s more windows, %s" % (format(len(hidden), ",d"), count(len(rest), noun[:-1], noun)),
                        more(None))
    return lines + [_sigma(carried, metric, calls, total)]


def _under(title: str, root: str, files: List[str]) -> Tuple[str, List[str]]:
    """The directory the files share, under ``root``, as deep as the title
    line holds (the rest stays on each file's path, so both open as
    printed), and the title's lines: the root on its own when even it
    overflows, broken after a ``/`` past the budget."""
    shared = posixpath.commonpath([posixpath.dirname(f) for f in files]) if files else ""
    if not root:
        return shared, [title]
    parts = [p for p in shared.split("/") if p]
    for k in range(len(parts), -1, -1):
        under = posixpath.join(root, *(parts[:k] + [""]))
        if len(title) + len(FILES_IN) + len(under) <= WIDTH:
            return posixpath.join(*parts[:k]) if k else "", [title + FILES_IN + under]
    return "", [title + FILES_IN.rstrip()] + [p.rstrip() for p in broken("  " + posixpath.join(root, ""))]


FILES_IN = ", files in "


def broken(path: str) -> List[str]:
    """A path within the line budget, broken after a ``/`` (a locator is
    never cut short), each continuation indented."""
    parts = []
    while len(path) > WIDTH:
        cut = path.rfind("/", 0, WIDTH) + 1 or WIDTH
        parts.append(path[:cut])
        path = "  " + path[cut:]
    return parts + [path]


def _window_head(path: str, tags: str) -> List[str]:
    """A window's file and dimensions, within the line budget: the tags
    on their own line when both overflow it, a long path broken after a
    ``/`` (a locator is never cut short)."""
    if len(path) + 2 + len(tags) <= WIDTH:
        return [style.tag("%s  %s" % (path, tags), "", values=((0, len(path)),))]
    return [style.tag(p, "", values=((0, len(p)),)) for p in broken(path)] + ["  " + tags]


def _fit(text: str, indent: int) -> List[str]:
    """A row within the line budget: what overflows wraps at a space,
    indented past its figures."""
    out = []
    while len(text) > WIDTH:
        cut = text.rfind(" ", indent + 1, WIDTH)
        if cut <= indent:
            break
        out.append(text[:cut].rstrip())
        text = " " * indent + text[cut:].lstrip()
    return out + [text]


def _sigma(carried: List[Fact], metric: str, calls: Optional[int], total: float) -> str:
    """``Σ 33 changes: 1,778,890 tokens × held ÷ 21 calls = 84,709 ✓``: the
    rows' figures summed from their printed operands, against the
    headline's; ``✗`` when they differ."""
    noun = schema.PLURAL[schema.metric(metric).carrier]
    n = count(len(carried), noun[:-1], noun)
    if schema.metric(metric).aggregation == schema.PER_CALL:
        product = sum(f.metrics[schema.CONTEXT_DELTA] * (held(f) or 0) for f in carried)
        figure = product / max(calls, 1)
        text = "Σ %s: %s tokens × held ÷ %s = %s" % (n, num(product), count(calls, "call"), num(figure))
    else:
        figure = sum(f.metrics[metric] for f in carried)
        text = "Σ %s: %s %s" % (n, glossary.printed(metric), num(figure))
    ok = num(figure) == num(total)
    return style.tag("%s %s the headline's %s" % (text, OK_MARK if ok else BAD_MARK + " not", num(total)),
                     style.GOOD if ok else style.BAD)


def recorded(candidate: schema.Candidate) -> str:
    """``1,204 characters`` (``+ 1 non-text`` when an image came too):
    characters as the transcript records them, never converted to tokens;
    nothing when the size is unknown."""
    if candidate.chars is None:
        return ""
    other = " + %s non-text" % num(candidate.other) if candidate.other else ""
    return "%s characters%s" % (num(candidate.chars), other)


HEAVIEST = "largest first, in characters as recorded"  # the candidates line: which one is heavy
PAD = " " * 6


def _at(locator: schema.Locator, file: str) -> str:
    """A locator in this window's file as ``:line``, elsewhere whole."""
    return (":%d" % locator.line) if locator.file == file else "%s:%d" % (locator.file, locator.line)


def _evidence(evidence: dict, file: str, said: List[str]) -> Iterator[str]:
    """Each key once; the candidates one per line under theirs, largest
    recorded size first (an unknown size last), each with its line, its
    size as recorded (``recorded``) and the tool and command it would have
    booked: the order says which is heavy, the change stays undivided."""
    for key, val in evidence.items():
        if key == schema.CANDIDATES:
            how = HEAVIEST if any(c.chars for c in val) else ("" if val else "none")
            if how not in said:  # said once a screen: the lines under it read alike
                yield ("%s%s: %s" % (PAD, key, how)).rstrip()
                said.append(how)
            for c in sorted(val, key=lambda c: -(c.chars or -1)):
                tags = " ".join("%s=%s" % (d, c.dims[d]) for d in ROW_DIMS if d in c.dims)
                yield ("%s└ %s  %s  %s" % (PAD, _at(c.locator, file), recorded(c), tags)).rstrip()
        elif isinstance(val, schema.WindowKey):  # a parent window: its pin
            yield "%s%s: %s=%s" % (PAD, key, schema.WINDOW_DIM, schema.window_value(val))
        elif isinstance(val, schema.Locator):
            yield "%s%s: %s" % (PAD, key, _at(val, file))
        else:
            yield "%s%s: %s" % (PAD, key, val)


def figure_names(metric: str) -> List[Tuple[str, str, str]]:
    """The fact list's own figures and how each is computed, for ``-v``:
    the list's Σ line works them in this run's numbers."""
    if schema.metric(metric).aggregation != schema.PER_CALL:
        return [("Σ", "the rows' %s summed" % glossary.printed(metric), "the Σ line: the headline's figure")]
    return [(HELD, "the calls of its window from the one it entered at to the window's end", "a row's held column"),
            (glossary.printed(metric), "tokens × held ÷ the calls in view", "the Σ line: the rows, = the headline")]
