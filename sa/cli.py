"""``sa context`` and ``sa spend``: read the words (``grammar``), read
each pin against the facts (``resolve``: case-insensitive for a closed
vocabulary, a catch-all row's label, a subagent's printed name, ``~`` for
home; a word no row prints is refused with the nearest that does), select
the facts, print the view, exit 1 if the reconciliation did not hold.

Every figure prints with the population it was counted over, every table
shows its base, its catch-all and its signed rows, and the ``context``
view ends with the reconciliation of the increments against the windows'
final occupancy. It is a regression guard: ``walk`` books every interval's
whole delta, so it holds by construction, and a MISMATCH is a bug in this
tool, exit status 1.

Filters: ``--root`` must be an existing directory (a typo is a refusal,
never a zero headline); ``--since`` selects FILES by modification time
before reading, 7 days unless given (``all`` reads every file), so dedup
runs over the selected files only, and a day count that keeps no file is a
legitimate empty population; a pin selects facts after dedup. A pin on a
window dimension (project, session, subagent, window, started_by, peak)
keeps whole windows; any other dimension narrows within them, and the
reconciliation and the average call then apply to the whole-window
population they are printed for. A refusal (``grammar.UsageError``, or
what ``query`` refuses) is exit status 2: at most two lines on stderr.

``--color`` (``style.enabled``): auto, the default, colours only when
stdout is a TTY or ``FORCE_COLOR`` is set, never while ``NO_COLOR`` is; a
progress line goes to stderr only when it is a TTY. No arguments, or
``-h``, print ``grammar.HELP`` and exit 0.
"""
import difflib
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import corpus, glossary, grammar, query, render, schema, style, tables, walk
from .grammar import UsageError
from .render import View
from .tables import WIDTH

PROG = glossary.PROG
SPEND_NOTE = "paid per call, so no context share is a cost share; what filled it: %s context" % PROG

VIEWS = {"context": View(metric=schema.CONTEXT_HELD,
                         tables=(schema.CAUSE_DIM, schema.TOOL_DIM, schema.COMMAND_DIM),
                         levers=(schema.TOOL_DIM, schema.COMMAND_DIM),
                         reconciles=True, notes=(), starts=schema.STARTED_BY_DIM,
                         also=(schema.SUBAGENT_DIM, schema.PEAK_DIM, schema.SESSION_DIM, schema.PROJECT_DIM)),
         "spend": View(metric=schema.SPEND, tables=(schema.SUBAGENT_DIM,), levers=(schema.SUBAGENT_DIM,),
                       reconciles=False, notes=(SPEND_NOTE,),
                       also=(schema.PROJECT_DIM, schema.SESSION_DIM))}


def _colour(choice: str = style.AUTO) -> bool:
    return style.enabled(choice, sys.stdout.isatty())


def refuse(view: Optional[str], error: Exception) -> int:
    """A refusal, exit 2: its line and its hint, home as ``~``, each within
    the line budget (``fit``)."""
    head = "%s%s: error: " % (PROG, " " + view if view else "")
    hint = tables.home_text(getattr(error, "hint", "") or "")
    print("\n".join(fit(tables.home_text(head + str(error)), hint)), file=sys.stderr)
    return 2


ROOT = re.compile(r" --root ('[^']*'|\S+)")
EVERY = re.compile(r"; every [\w ]+: ")


def _elide(text: str) -> str:
    """``text`` within the line budget, its middle cut to ``…`` when it
    must be: its start and end kept."""
    keep = WIDTH - 1
    return text if len(text) <= WIDTH else text[:keep // 2] + "…" + text[len(text) - (keep - keep // 2):]


def fit(line: str, hint: str) -> List[str]:
    """An error's two lines within the budget, the most useful kept: what
    follows the error's last ``; `` (the nearest value, the declared ones)
    leads the hint when the error overflows; a hint that overflows drops
    the ``--root`` it repeats (the user typed it), then names its listing
    ``all``, then keeps its first clause; what still overflows is cut in
    the middle."""
    if len(line) > WIDTH and "; " in line:
        line, moved = line.rsplit("; ", 1)
        hint = moved + ("; " + hint if hint else "")
    if len(hint) > WIDTH:
        hint = ROOT.sub("", hint)
    if len(hint) > WIDTH:
        hint = EVERY.sub("; all: ", hint, 1)
    if len(hint) > WIDTH:
        hint = hint.split("; ", 1)[0]
    return [_elide(text) for text in (line, hint) if text]


def refuse_bare(word: str, view: str, values: Dict[str, List[str]]) -> UsageError:
    """A bare word: what replaced it if retired, the pin it would be if a
    row prints it (case aside), else the grammar."""
    if word in grammar.RETIRED:
        return UsageError("%s is retired: %s" % (word, grammar.RETIRED[word]), "e.g. " + grammar.run(view, "-v"))
    for dim, present in values.items():
        hit = [v for v in present if v.lower() == word.lower()]
        if hit:
            return UsageError("%r is a %s row: pin it as %s" % (word, dim, grammar.quote("%s=%s" % (dim, hit[0]))),
                              "a pin is DIM=VALUE; a table is by DIM")
    return UsageError("%r is neither a pin (DIM=VALUE) nor by DIM" % word,
                      "dimensions: " + ", ".join(schema.KIND_DIMENSIONS[grammar.carrier(view)]))


def resolve(dim: str, text: str, view: str, present: List[str],
            names: Optional[Dict[str, str]] = None) -> Tuple[Optional[str], str]:
    """A pin's value as the facts carry it (None: the catch-all row, the
    facts that lack ``dim``) and as the tables print it. ``present`` is
    every value of ``dim`` the view's facts carry, as printed."""
    text = text.rstrip(glossary.MARKER) or text  # a label pasted with its footnote marker
    if text.lower() == schema.residual_label(dim).lower() and dim in schema.RESIDUAL_NOTES:
        return None, schema.residual_label(dim)
    if dim in schema.VOCABULARY:
        declared = schema.VOCABULARY[dim]
        hit = [v for v in declared if v.lower() == text.lower()] or [
            v for v in declared if v.lower().startswith(text.lower())]
        if len(hit) == 1:
            return hit[0], hit[0]
        raise UsageError("unknown %s %r; declared: %s" % (dim, text, ", ".join(declared)),
                         "every %s in view: %s" % (dim, grammar.run(view, grammar.BY, dim)))
    printed = {tables.value(dim, v, names): v for v in present}
    value = tables.unhome(text)
    if dim in tables.NAMED:
        value = {label: i for i, label in (names or {}).items() if i in present}.get(text, value)
    if dim == schema.SESSION_DIM and value not in present:  # a session by any unique prefix
        hits = [v for v in present if v.lower().startswith(text.lower())]
        if len(hits) > 1:
            raise UsageError("%s=%s names %d sessions; type more of it, e.g. %s" % (
                dim, text, len(hits), grammar.quote("%s=%s" % (dim, tables.value(dim, hits[0], names)))),
                "every %s: %s" % (dim, grammar.run(view, grammar.BY, dim)))
        value = hits[0] if hits else value
    if value in present:
        return value, tables.value(dim, value, names)
    raise no_match(view, dim, text, list(printed), grammar.run(view, grammar.BY, dim))


def no_match(view: str, dim: str, text: str, printed: Sequence[str], every: str, given: bool = False) -> UsageError:
    """The refusal of a pin no fact carries (``given`` the pins before it):
    the nearest value as a pin, and the command listing every one."""
    lacking = text.lower() in ("", "none", "no", "-") and dim in schema.RESIDUAL_NOTES  # the catch-all
    near = [schema.residual_label(dim)] if lacking else difflib.get_close_matches(text, list(printed), 1, 0.5) or [
        p for p in printed if p.lower() == text.lower()][:1] or list(printed)[:1]
    return UsageError("no %s has %s=%s%s%s" % (
        schema.PLURAL[grammar.carrier(view)][:-1], dim, text, " with the pins before it" if given else "",
        "; nearest: %s" % grammar.quote("%s=%s" % (dim, near[0])) if near else "; none present"),
        "every %s: %s" % (dim, every))


def tools(view: View, sel: query.Selection) -> List[str]:
    """The selection's tools by mass, largest first: the order their hues
    are dealt in (``style.Painter``); none for a view whose carrier has no
    tool."""
    if schema.TOOL_DIM not in schema.KIND_DIMENSIONS[schema.metric(view.metric).carrier]:
        return []
    return [r.value for r in query.group(sel.facts, schema.TOOL_DIM, view.metric, sel.calls).rows
            if r.kind == query.REGULAR]


def main(argv: Optional[List[str]] = None) -> int:
    try:
        args = grammar.parse(sys.argv[1:] if argv is None else argv)
    except UsageError as error:
        return refuse(None, error)
    if args.view is None:
        print(grammar.HELP)
        return 0
    root = Path(args.root) if args.root else corpus.default_root()
    if not root.is_dir():
        return refuse(args.view, UsageError("--root names no directory (by default ~/.claude/projects)",
                                            "no such directory: %s" % args.root))
    view = VIEWS[args.view]
    if sys.stderr.isatty():
        n = sum(1 for _ in corpus.find_files(root, args.since))
        print("reading %d files under %s ..." % (n, tables.tilde(root)), end="\r", file=sys.stderr, flush=True)
    loaded = corpus.load(root, args.since)
    if sys.stderr.isatty():
        print("\033[K", end="", file=sys.stderr, flush=True)
    try:
        forest = walk.forest(loaded)
        names = dict(tables.subagent_names(loaded.agent_types, forest), **tables.session_names(forest))
        where, printed = [], []
        for dim, text in args.pins:
            present = query.values(forest, dim, view.metric)
            value, shown = resolve(dim, text, args.view, present, names)
            if (dim, value) in where:  # the same pin twice is one pin, echoed once
                continue
            where.append((dim, value))
            printed.append((dim, shown))
        if args.bare:
            dims = schema.KIND_DIMENSIONS[grammar.carrier(args.view)]
            raise refuse_bare(args.bare[0], args.view, {
                d: [tables.value(d, v, names) for v in query.values(forest, d, view.metric)] for d in dims})
        root_text = None if args.root is None or root == corpus.default_root() else tables.tilde(root)
        inv = grammar.Invocation(args.view, tuple(printed), args.since_text, root_text)
        sel = query.selection(forest, where, view.metric, view.reconciles)
        lines = render.report(view, sel, loaded, args.by, inv, args.verbose, forest=forest, names=names)
    except query.NoMatch as error:
        before = tuple(p for p in printed if p[0] != error.dim)
        twice = [v for d, v in printed if d == error.dim]
        if len(twice) > 1:  # one dimension pinned twice: every pin holds, so no fact has both
            keep = grammar.Invocation(args.view, before + ((error.dim, twice[-1]),), inv.since_text, inv.root)
            return refuse(args.view, UsageError("every pin holds, and no %s has %s; keep one" % (
                schema.PLURAL[grammar.carrier(args.view)][:-1], " and ".join(
                    grammar.quote("%s=%s" % (error.dim, v)) for v in twice)), "e.g. " + keep.command()))
        shown = [tables.value(error.dim, v, names) for v in error.present]
        value = dict(printed).get(error.dim, error.value)
        every = grammar.Invocation(args.view, before, inv.since_text, inv.root).command(by=error.dim)
        return refuse(args.view, no_match(args.view, error.dim, value, shown, every, given=True))
    except (UsageError, schema.SchemaError) as error:
        return refuse(args.view, error)
    paint = style.Painter(tools(view, sel), style.depth()).paint if _colour(args.color) else str
    try:
        print("\n".join(paint(line) for line in lines))
    except BrokenPipeError:  # a pager or head closed early: quiet, as a shell tool is
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    return 0 if not view.reconciles or sel.reconciliation.holds else 1
