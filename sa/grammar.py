"""The command line's one grammar (UX_PRINCIPLES 1: whatever the output
names is valid input, verbatim):

    python3 -m sa spend|context [by DIM | by change | by call] [DIM=VALUE ...] [-v]
                                [--since Nd|all] [--root DIR] [--color auto|always|never]

``DIM=VALUE`` is a pin: repeatable, different dimensions AND. ``by DIM``
prints that one table, every row; ``by change`` (context) and ``by call``
(spend) list the facts themselves. ``by`` is the only keyword: any other
bare word is refused with the nearest valid input. No arguments, or
``-h``, prints ``HELP`` and exits 0.

``parse`` reads the words; ``resolve`` reads a pin's value against the
facts (case-insensitive for a closed vocabulary, a catch-all row's label,
a subagent's printed name, ``~`` for home) after loading; ``Invocation``
prints any command back, pins as the tables print them, so a suggested
next step pastes and runs. A refusal is a ``UsageError``: at most two
lines, the nearest valid input and where the choices live.
"""
import difflib
import shlex
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from . import glossary, residual, schema, tables

PROG = glossary.PROG
VIEWS = ("spend", "context")  # cost first, then cost aside
BY = "by"
FACTS = {"context": "change", "spend": "call"}  # ``by`` this lists the facts
DEFAULT_SINCE = 7.0
ALL = "all"
WIDTH = 100  # every line's budget, an error's too
# Flags this grammar retired, and what replaced each: a mistake teaches.
RETIRED = {"--where": "write the pin alone, DIM=VALUE (tool=Bash)",
           "--by": "write by DIM (by tool), or by change / by call for the facts",
           "--limit": "by DIM prints every row of its table",
           "explain": "add -v to any command: it explains what that screen shows"}

HELP = """\
usage: %(p)s spend|context [by DIM] [DIM=VALUE ...] [-v] [--since Nd|all]

Reads your Claude Code transcripts (~/.claude/projects, the last 7 days)
and answers two questions:
  spend    What did my sessions cost? Each call's input, weighted by price.
  context  Cost aside, is context degrading the model? What an average call
           held, and what put it there.

Start broad, then narrow; each screen suggests the next command and ends
with its checks (✓): what it verified, in plain words.
  %(p)s context                             the answer and its tables
  %(p)s context by tool                     one table, every row
  %(p)s context tool=Bash command=Bash:cat  pin rows you saw (DIM=VALUE); pins stack
  %(p)s context tool=Bash by change         the changes themselves, file:line
  %(p)s context tool=Bash -v                how it's computed; what * words mean
  %(p)s spend by subagent                   what each subagent cost

DIM: %(w)s;
     context also %(i)s
--since 30d|all  files modified in the last N days (default 7d)
--root DIR       the transcripts' directory (default ~/.claude/projects)
--color auto|always|never""" % {"p": PROG, "w": ", ".join(schema.WINDOW_DIMENSIONS), "i": ", ".join(
    d for d in schema.KIND_DIMENSIONS[schema.INCREMENT] if d not in schema.WINDOW_DIMENSIONS)}


class UsageError(Exception):
    """A refusal: its message, then at most one line of where to go."""

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


class Args(NamedTuple):
    view: Optional[str]          # None: print HELP
    by: Optional[str] = None     # a dimension, or ``FACTS[view]``
    pins: Tuple[Tuple[str, str], ...] = ()  # as typed
    verbose: bool = False
    since: Optional[float] = DEFAULT_SINCE  # None: every file
    since_text: Optional[str] = None  # as typed; None when the default
    root: Optional[str] = None
    color: str = "auto"
    bare: Tuple[str, ...] = ()   # words that are neither ``by`` nor a pin: refused once the data names them


def _days(text: str) -> Optional[float]:
    if text == ALL:
        return None
    if not text.endswith("d") or not text[:-1].replace(".", "", 1).isdigit():
        raise UsageError("--since takes a number of days like 7d, or %s, not %r" % (ALL, text),
                         "e.g. %s context --since 30d" % PROG)
    return float(text[:-1])


def _dimension(dim: str, view: str) -> str:
    """A dimension the view's facts carry, else the nearest that is."""
    carried = schema.KIND_DIMENSIONS[carrier(view)]
    if dim in carried:
        return dim
    if dim in schema.DIMENSIONS:
        raise UsageError("%s's %s carry no %s" % (view, schema.PLURAL[carrier(view)], dim),
                         "its dimensions: " + ", ".join(carried))
    near = difflib.get_close_matches(dim, carried, 1, 0.6)
    raise UsageError("unknown dimension %r%s" % (dim, "; did you mean %s?" % near[0] if near else ""),
                     "dimensions: " + ", ".join(carried))


def _start(view: str, rest: Sequence[str]) -> str:
    """The command with the view put right and the user's other words
    kept, so it pastes as meant; the view alone when that overflows."""
    whole = run(view, *rest)
    return whole if len(whole) <= WIDTH - len("start here: ") else run(view)


def carrier(view: str) -> str:
    return schema.INCREMENT if view == "context" else schema.CALL


def parse(argv: Sequence[str]) -> Args:
    words = list(argv)
    if not words or any(w in ("-h", "--help") for w in words):
        return Args(None)
    lead = _global_flags(words)
    if lead == len(words):  # global flags alone: the front door, once they read right
        parse(["context"] + words)
        return Args(None)
    words.insert(0, words.pop(lead))
    view = words.pop(0)
    if view not in VIEWS:
        if view in RETIRED:
            raise UsageError("%s is retired: %s" % (view, RETIRED[view]),
                             "e.g. %s context -v" % PROG if view == "explain" else "see %s -h" % PROG)
        near = difflib.get_close_matches(view, VIEWS, 1, 0.6)
        raise UsageError("unknown command %r: %s" % (view, "did you mean %s?" % near[0] if near else
                                                       "the commands are spend and context"),
                         "start here: " + _start(near[0] if near else "context", words))
    found: Dict[str, object] = {"view": view}
    pins, bare = [], []
    while words:
        word = words.pop(0)
        flag, eq, inline = word.partition("=")
        if word in ("-v", "--verbose"):
            found["verbose"] = True
        elif flag in ("--since", "--root", "--color") and word.startswith("--"):
            if not eq and not words:
                raise UsageError("%s needs a value" % flag, "see %s -h" % PROG)
            text = inline if eq else words.pop(0)
            if flag == "--since":
                found["since"], found["since_text"] = _days(text), text
            elif flag == "--root":
                found["root"] = text
            elif text not in ("auto", "always", "never"):
                raise UsageError("--color takes auto, always or never, not %r" % text)
            else:
                found["color"] = text
        elif flag in RETIRED and word.startswith("-"):
            raise UsageError("%s is retired: %s" % (flag, RETIRED[flag]), "see %s -h" % PROG)
        elif word.startswith("-"):
            near = difflib.get_close_matches(flag, list(RETIRED) + list(GLOBAL), 1, 0.6)
            if near and near[0] in RETIRED:  # the retired flag it was meant as teaches the fix
                raise UsageError("unknown flag %s; %s is retired" % (word, near[0]), RETIRED[near[0]])
            raise UsageError("unknown flag %s%s" % (word, "; did you mean %s?" % near[0] if near else ""),
                             "flags: -v, --since, --root, --color; see %s -h" % PROG)
        elif word == BY:
            if "by" in found:
                raise UsageError("one by per command: by %s already" % found["by"])
            if not words:
                raise UsageError("by needs a table: by DIM, or by %s" % FACTS[view],
                                 "dimensions: " + ", ".join(schema.KIND_DIMENSIONS[carrier(view)]))
            what = words.pop(0)
            if what in FACTS.values() or what in ("fact", "facts", "changes", "calls"):
                if what not in (FACTS[view],):
                    raise UsageError("%s lists its %s: by %s" % (view, schema.PLURAL[carrier(view)],
                                                                 FACTS[view]))
                found["by"] = what
            else:
                found["by"] = _dimension(what, view)
        elif eq:
            pins.append((_dimension(flag, view), inline))
        elif word in schema.DIMENSIONS:
            raise UsageError("%r is a dimension: by %s prints its table; %s=VALUE pins a row" % (
                word, word, word), "e.g. %s %s by %s" % (PROG, view, word))
        elif word in FACTS.values() or word in ("fact", "facts"):
            raise UsageError("%r alone is no command: by %s lists them" % (word, FACTS[view]))
        else:
            bare.append(word)
    return Args(bare=tuple(bare), pins=tuple(pins), **found)


GLOBAL = ("--since", "--root", "--color")  # the flags that take a value


def _global_flags(words: Sequence[str]) -> int:
    """How many leading words are flags and their values: the command
    follows them (``--color never context`` reads as ``context --color never``)."""
    i = 0
    while i < len(words):
        flag, eq, _ = words[i].partition("=")
        if words[i] in ("-v", "--verbose"):
            i += 1
        elif flag in GLOBAL:
            i += 1 if eq else 2
        else:
            break
    return min(i, len(words))


def refuse_bare(word: str, view: str, values: Dict[str, List[str]]) -> UsageError:
    """A bare word: the pin it would be when a row carries it as printed
    (case aside), else the grammar."""
    for dim, present in values.items():
        hit = [v for v in present if v.lower() == word.lower()]
        if hit:
            return UsageError("%r is a %s row: pin it as %s" % (word, dim, quote("%s=%s" % (dim, hit[0]))),
                              "a pin is DIM=VALUE; a table is by DIM")
    return UsageError("%r is neither a pin (DIM=VALUE) nor by DIM" % word,
                      "dimensions: " + ", ".join(schema.KIND_DIMENSIONS[carrier(view)]))


def resolve(dim: str, text: str, view: str, present: List[str],
            names: Optional[Dict[str, str]] = None) -> Tuple[Optional[str], str]:
    """A pin's value as the facts carry it (None: the catch-all row, the
    facts that lack ``dim``) and as the tables print it. ``present`` is
    every value of ``dim`` the view's facts carry, as printed."""
    text = text.rstrip(glossary.MARKER) or text  # a label pasted with its footnote marker
    if text.lower() == residual.label(dim).lower() and dim in residual.RESIDUAL_NOTES:
        return None, residual.label(dim)
    if dim in schema.VOCABULARY:
        declared = schema.VOCABULARY[dim]
        hit = [v for v in declared if v.lower() == text.lower()] or [
            v for v in declared if v.lower().startswith(text.lower())]
        if len(hit) == 1:
            return hit[0], hit[0]
        raise UsageError("unknown %s %r; declared: %s" % (dim, text, ", ".join(declared)),
                         "every %s in view: %s" % (dim, run(view, BY, dim)))
    printed = {tables.value(dim, v, names): v for v in present}
    value = tables.unhome(text)
    if dim in tables.NAMED:
        value = {label: i for i, label in (names or {}).items() if i in present}.get(text, value)
    if dim == schema.SESSION_DIM and value not in present:  # a session by any unique prefix
        hits = [v for v in present if v.lower().startswith(text.lower())]
        if len(hits) > 1:
            raise UsageError("%s=%s names %d sessions; type more of it, e.g. %s" % (
                dim, text, len(hits), quote("%s=%s" % (dim, tables.value(dim, hits[0], names)))),
                "every %s: %s" % (dim, run(view, BY, dim)))
        value = hits[0] if hits else value
    if value in present:
        return value, tables.value(dim, value, names)
    raise no_match(view, dim, text, list(printed), run(view, BY, dim))


def no_match(view: str, dim: str, text: str, printed: Sequence[str], every: str, given: bool = False) -> UsageError:
    """The one refusal for a pin no fact carries (here, or ``query.narrow``
    given the pins before it): the nearest value as a pin, and the command
    that lists every one."""
    near = difflib.get_close_matches(text, list(printed), 1, 0.5) or [
        p for p in printed if p.lower() == text.lower()][:1] or (  # an empty value means the catch-all row
        [residual.label(dim)] if not text and dim in residual.RESIDUAL_NOTES else list(printed)[:1])
    return UsageError("no %s has %s=%s%s%s" % (
        schema.PLURAL[carrier(view)][:-1], dim, text, " with the pins before it" if given else "",
        "; nearest: %s" % quote("%s=%s" % (dim, near[0])) if near else "; none present"),
        "every %s: %s" % (dim, every))


def quote(word: str) -> str:
    """A word as a shell reads it back: quoted only when it must be."""
    return shlex.quote(word)


def run(*words: str) -> str:
    """``python3 -m sa`` and the words, each quoted as the shell needs."""
    return " ".join([PROG] + [quote(w) for w in words])


# A pin that implies others: a command its tool, a window every window dimension; a
# printed command leaves the implied pins out, the facts it selects the same.
IMPLIES = {schema.COMMAND_DIM: (schema.TOOL_DIM,),
           schema.WINDOW_DIM: tuple(d for d in schema.WINDOW_DIMENSIONS if d != schema.WINDOW_DIM)}


class Invocation(NamedTuple):
    """What was asked, printed back: any command derived from it pastes
    and runs, the pins as the tables print them, a non-default ``--since``
    and ``--root`` kept so the population stays the same."""
    view: str
    pins: Tuple[Tuple[str, str], ...] = ()  # (dim, value as printed)
    since_text: Optional[str] = None
    root: Optional[str] = None  # printed with ``~``; None at the default root

    def command(self, by: Optional[str] = None, add: Sequence[Tuple[str, str]] = (),
                verbose: bool = False) -> str:
        words = [self.view] + ([BY, by] if by else [])
        pins = list(self.pins) + list(add)
        implied = {d for p in pins if p[1] != residual.label(p[0]) for d in IMPLIES.get(p[0], ())}
        words += ["%s=%s" % p for p in pins if p[0] not in implied]
        flags = (["--since", self.since_text] if self.since_text else [])
        root = ""
        if self.root:
            root = " --root " + (("~/" + quote(self.root[2:])) if self.root.startswith("~/") else quote(self.root))
        return run(*(words + flags)) + root + (" -v" if verbose else "")
