"""Depth, on request (UX_PRINCIPLES 2): the ``*`` that marks a coined
word where it first prints, and ``-v``, which explains ONLY what this
screen shows: each figure's working in the run's own numbers, and what
each marked word and catch-all row means. Narrowing first is how a user
aims it. The default screen prints ``-v`` as a command that pastes and
runs, with what it would add and what it costs in lines; ``-v`` prints that
block in the pointer's place. The table pointer beside it is the same
kind of line: the ``by DIM`` command for a table the screen left out.
``glossary.GLOSSARY`` is the one source of every definition."""
import re
import textwrap
from typing import Dict, List, Sequence, Tuple

from . import glossary, headline, leaves, query, residual, schema, style, tables
from .tables import WIDTH, count, num, pct, value

HEAD = "-v: "  # each part of the block opens with it
INDENT = "    "  # a wrapped line's continuation


def footnote(lines: List[str]) -> Tuple[List[str], List[str]]:
    """Each marked glossary term, at its first appearance in ``lines`` (a
    table's header aside: its rows carry the mark, the residual's always),
    takes the marker (a padded line gives up one space of its padding, so
    its columns hold); never inside a line's value spans: a project or a
    tool named like a term is a value, not the term. A term spelt with
    ``_`` is found spelt with a space too, and keyed as found. The terms
    marked, in the order they first appear."""
    found = []
    for term in (glossary.printed(t) for t, e in glossary.GLOSSARY.items() if e.marked):
        word = re.compile(r"(?<![\w=*-])%s(s?)(?![\w=-])" % re.escape(term).replace("_", "[_ ]"))
        for i, line in enumerate(lines):
            spans = getattr(line, "values", ())
            m = None if getattr(line, "role", "") in (style.HEADER, style.HINT) else next(
                (m for m in word.finditer(line) if not any(a <= m.start() < b for a, b in spans)), None)
            if m:
                found.append((i, m.start(), line[m.start():m.end() - len(m.group(1))]))
                if line[m.end():m.end() + 1] != glossary.MARKER:
                    end = m.end()
                    pad = line.find("  ", end)  # padding gives up a space: the columns hold
                    pad = len(line) if pad < 0 else pad
                    text = line[:end] + glossary.MARKER + line[end:pad] + line[pad + 1:]

                    def moved(at: int) -> int:
                        return at + (end <= at <= pad) if pad < len(line) else at + (at >= end)
                    lines[i] = style.retag(line, text, [(moved(a), moved(b)) for a, b in spans])
                break
    return lines, [term for _, _, term in sorted(found)]



def _wrapped(text: str, first: str = "  ") -> List[str]:
    return textwrap.wrap(text, WIDTH, initial_indent=first, subsequent_indent=INDENT,
                         break_on_hyphens=False)


def define(term: str, note: str = "") -> List[str]:
    """A marked word as this screen spells it: what it means, in one
    sentence on its own line, then the edge cases, why its number might
    surprise (or the view's own ``note`` on it), under it."""
    entry = glossary.GLOSSARY[glossary.key_of(term)]
    return _wrapped("%s: %s" % (term, entry.meaning)) + _wrapped(note or entry.surprise, INDENT)


def block(figures: Sequence[Tuple[str, str, str]], terms: Sequence[str],
          catch_alls: Sequence[str] = (), view_notes: Dict[str, Sequence[str]] = None) -> List[str]:
    """The ``-v`` block: each figure's working, then each marked word's
    definition and each catch-all row's cases (``residual``)."""
    lines = []
    if figures:
        lines.append(HEAD + "how the figures are computed, in this run's numbers")
        for name, how, working in figures:  # the formula, then this run's numbers on a line of their own
            lines += _wrapped("%s = %s" % (name, how)) + _wrapped(working, INDENT)
    if terms or catch_alls:
        lines.append(HEAD + "what the marked words and the catch-all rows mean")
        for term in terms:
            lines += define(term, "; ".join((view_notes or {}).get(term, ())))
        for dim in (d for d in catch_alls if residual.RESIDUAL_NOTES.get(d, ("", []))[1]):
            lines += _wrapped("%s (by %s): %s" % (residual.label(dim), dim, residual.residual_cases(dim)))
    return [style.tag(line, style.KEY) for line in lines]


def footer(words: bool, lines: int) -> str:
    """What ``-v`` adds to this screen, and what it costs, in lines."""
    return "how it's computed and checked%s (+%s)" % (", * words" if words else "",
                                                                count(lines, "line"))


def figures(view, sel: query.Selection, shown: Sequence[Tuple[query.Table, object]],
            facts: bool, names: Dict[str, str] = None) -> List[Tuple[str, str, str]]:
    """Each kind of figure on this screen and its working, in this run's
    numbers, the first row of the first table that prints it as the
    example: the headline's figure, a row's part of the average and its
    share, a window row's own average call;
    under ``by change``/``by call``, the list's own columns."""
    spec = schema.metric(view.metric)
    carried = [f for f in sel.facts if f.kind == spec.carrier]
    out = []
    if spec.aggregation == schema.PER_CALL:
        mass = sum(f.metrics[view.metric] for f in carried)
        what = glossary.printed(glossary.AVERAGE).replace("_", " ") if not sel.drill else (
            "the pinned part, %s" % ", ".join("%s=%s" % (d, residual.label(d) if v is None else value(d, v, names))
                                              for d, v in sel.drill))
        out.append((what, "its changes' tokens × held, summed, ÷ the calls in view",
                    "%s ÷ %s = %s" % (num(mass), num(sel.calls), num(sel.total))))
    else:
        out.append((glossary.printed(view.metric), "input + cache reads × 0.1 + 5m cache writes × 1.25 + 1h"
                    " cache writes × 2.0, a call's", "summed over the %s: %s" % (count(len(carried), "call"),
                                                                           num(sel.total))))
        others = [n for n, m in schema.METRICS.items()
                  if m.carrier == schema.CALL and m.aggregation == schema.ADDITIVE and n != view.metric]
        out.append(("other call totals", "output, not in %s; the cache writes it weighs" % view.metric,
                    ", ".join("%s %s" % (n, num(query.total(carried, n))) for n in others)))
    if facts:
        return out + leaves.figure_names(view.metric)
    first = next(((t, c) for t, c in shown if any(r.kind == query.REGULAR for r in t.rows)), None)
    if first:
        grouped, _ = first
        top = next(r for r in grouped.rows if r.kind == query.REGULAR)
        if spec.aggregation == schema.PER_CALL:
            out.append((glossary.printed(view.metric), "a row's changes' tokens × held, summed, ÷ the calls"
                        " in view", "%s: %s ÷ %s = %s" % (value(grouped.dim, top.value, names),
                                                          num(top.mass * sel.calls), num(sel.calls), num(top.mass))))
        out.append(("share", "a row ÷ its table's = 100% row", "%s: %s ÷ %s = %s" % (
            value(grouped.dim, top.value, names), num(top.mass), num(grouped.base), pct(grouped.share(top.mass)))))
    windowed = next(((t, c) for t, c in shown if c and any(r.kind == query.REGULAR for r in t.rows)), None)
    if windowed:
        grouped, _ = windowed
        top = next(r for r in grouped.rows if r.kind == query.REGULAR)
        mine = [f.metrics[schema.CONTEXT_TOKENS] for f in sel.window_facts
                if f.kind == schema.CALL and f.dims.get(grouped.dim) == top.value]
        out.append((glossary.printed(glossary.AVG_CALL), "a window row's calls' sizes summed ÷ its own calls",
                    "%s: %s ÷ %s = %s" % (value(grouped.dim, top.value, names), num(sum(mine)), num(len(mine)),
                                          num(sum(mine) / max(len(mine), 1)))))
    return out


def pointer(command: str, gloss: str, pad: int = 0) -> List[str]:
    """A way deeper as a command that pastes and runs, its gloss beside it
    where the line has room, else under it."""
    first = tables.command_lines("", command)
    if gloss and len(first) == 1 and len(command) + 2 + len(gloss) <= tables.WIDTH:  # aligned where it fits
        first = [command.ljust(pad if pad + 2 + len(gloss) <= tables.WIDTH else 0) + "  " + gloss]
    elif gloss:
        first += ["    " + gloss]
    return [style.tag(line, style.KEY, values=((0, len(command)),) if glossary.PROG in line else ()) for line in first]


ALSO = "also by "  # the table pointer's gloss: the other tables, each by DIM away


def also_by(sel: query.Selection, view, carrier: str, printed: List[str],
            inv) -> List[Tuple[str, str]]:
    """The tables a screen leaves out that would split its facts: the
    command for the first, its gloss ``also by`` the rest, each ``by DIM`` away."""
    order = list(view.also) + [d for d in schema.KIND_DIMENSIONS[carrier] if d not in view.also]
    rest = [d for d in headline.open_dims(sel, tuple(order), carrier) if d not in printed]
    if not rest:
        return []
    return [(inv.command(by=rest[0]), ALSO + ", ".join(rest[1:]) if rest[1:] else "")]
