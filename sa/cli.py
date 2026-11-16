"""``sa context`` and ``sa spend``: read the words (``grammar``), select
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
import os
import sys
from pathlib import Path
from typing import List, Optional

from . import corpus, glossary, grammar, query, render, schema, style, tables, walk
from .grammar import UsageError
from .render import View

PROG = glossary.PROG
SPEND_NOTE = "paid per call, so no context share is a cost share; what filled it: %s context" % PROG

VIEWS = {"context": View(metric=schema.CONTEXT_HELD,
                         tables=(schema.CAUSE_DIM, schema.TOOL_DIM, schema.COMMAND_DIM),
                         levers=(schema.TOOL_DIM, schema.COMMAND_DIM),
                         reconciles=True, notes=(), starts=schema.STARTED_BY_DIM,
                         leads=(schema.PEAK_DIM,),
                         also=(schema.SUBAGENT_DIM, schema.PEAK_DIM, schema.SESSION_DIM, schema.PROJECT_DIM)),
         "spend": View(metric=schema.SPEND, tables=(schema.SUBAGENT_DIM,), levers=(schema.SUBAGENT_DIM,),
                       reconciles=False, notes=(SPEND_NOTE,),
                       also=(schema.PROJECT_DIM, schema.SESSION_DIM))}


def _colour(choice: str = style.AUTO) -> bool:
    return style.enabled(choice, sys.stdout.isatty())


def refuse(view: Optional[str], error: Exception) -> int:
    """A refusal, exit 2: its line and its hint, home as ``~``."""
    head = "%s%s: error: " % (PROG, " " + view if view else "")
    lines = [head + str(error)] + ([getattr(error, "hint")] if getattr(error, "hint", "") else [])
    print("\n".join(tables.home_text(line) for line in lines), file=sys.stderr)
    return 2


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
        return refuse(args.view, UsageError("no such directory: %s" % args.root, "--root takes the transcripts'"
                                            " directory; the default is ~/.claude/projects"))
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
            value, shown = grammar.resolve(dim, text, args.view, present, names)
            where.append((dim, value))
            printed.append((dim, shown))
        if args.bare:
            dims = schema.KIND_DIMENSIONS[grammar.carrier(args.view)]
            raise grammar.refuse_bare(args.bare[0], args.view, {
                d: [tables.value(d, v, names) for v in query.values(forest, d, view.metric)] for d in dims})
        root_text = None if args.root is None or root == corpus.default_root() else tables.tilde(root)
        inv = grammar.Invocation(args.view, tuple(printed), args.since_text, root_text)
        sel = query.selection(forest, where, view.metric, view.reconciles)
        lines = render.report(view, sel, loaded, args.by, inv, args.verbose, forest=forest, names=names)
    except query.NoMatch as error:
        before = tuple(p for p in printed if p[0] != error.dim)
        shown = [tables.value(error.dim, v, names) for v in error.present]
        value = dict(printed).get(error.dim, error.value)
        every = grammar.Invocation(args.view, before, inv.since_text, inv.root).command(by=error.dim)
        return refuse(args.view, grammar.no_match(args.view, error.dim, value, shown, every, given=True))
    except (UsageError, schema.SchemaError) as error:
        return refuse(args.view, error)
    paint = style.Painter(render.tools(view, sel), style.depth()).paint if _colour(args.color) else str
    try:
        print("\n".join(paint(line) for line in lines))
    except BrokenPipeError:  # a pager or head closed early: quiet, as a shell tool is
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    return 0 if not view.reconciles or sel.reconciliation.holds else 1
