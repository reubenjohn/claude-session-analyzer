"""The one table every other module reads from.

A fact is one of two kinds. A ``call`` fact is one max-merged assistant
message and carries what it cost; an ``increment`` fact is one booked change
of context occupancy and carries where the context went. Each metric names
the one kind that carries it and ``fact`` refuses it on the other, so a
total over one metric is never a sum over both kinds: a metric read from
both would count every token twice (measured, on the carrier-less design
this one replaced: exactly 2.000000x the truth).

Adding a metric or a dimension is one line here; a cause is its entry in
``CAUSES`` plus the branch of ``walk`` that books it. An unknown name
raises rather than skipping: a silent skip is how a wrong number stays
plausible.
"""
import difflib
import hashlib
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple

from . import heads, usage

ADDITIVE = "additive"
PEAK = "peak"
# Summed over one population's carrier facts, then divided by that
# population's calls (D-PER-CALL): never summed or merged across two.
PER_CALL = "per_call"

CALL = "call"
INCREMENT = "increment"
KINDS = (CALL, INCREMENT)
# What the output calls a fact of each kind: an increment
# is a change of a window's context.
PLURAL = {CALL: "calls", INCREMENT: "changes"}


class Metric(NamedTuple):
    aggregation: str  # ADDITIVE sums; PEAK is a high-water mark and never sums; PER_CALL divides
    carrier: str      # the one fact kind that carries it
    unit: str
    # A call metric is read from the call's max-merged usage dict; an
    # increment metric is booked by the walk and has no reader.
    read: Optional[Callable[[dict], float]] = None


# The two metrics the reconciliation joins: every booked increment against
# the occupancy the window's last call reports. ``context_held`` is an
# increment's delta times the calls of its window that held it (``walk.held``):
# summed over whole windows it is their calls' summed occupancy, so over
# the population's calls it is the average context per call, split by row.
CONTEXT_DELTA = "context_delta"
CONTEXT_TOKENS = "context_tokens"
CONTEXT_HELD = "context_held"
SPEND = "spend"

METRICS: Dict[str, Metric] = {
    CONTEXT_DELTA: Metric(ADDITIVE, INCREMENT, "context tokens"),
    CONTEXT_HELD: Metric(PER_CALL, INCREMENT, "tokens"),
    SPEND: Metric(ADDITIVE, CALL, "price-weighted input tokens", usage.usage_spend),
    "output_tokens": Metric(ADDITIVE, CALL, "tokens", lambda u: u["output_tokens"]),
    "input_tokens": Metric(ADDITIVE, CALL, "tokens", lambda u: int(u.get("input_tokens", 0) or 0)),
    "cache_read_tokens": Metric(ADDITIVE, CALL, "tokens", lambda u: int(u.get("cache_read_input_tokens", 0) or 0)),
    "cache_write_1h_tokens": Metric(ADDITIVE, CALL, "tokens", lambda u: usage.cache_creation_tiers(u)[0]),
    "cache_write_5m_tokens": Metric(ADDITIVE, CALL, "tokens", lambda u: usage.cache_creation_tiers(u)[1]),
    CONTEXT_TOKENS: Metric(PEAK, CALL, "tokens", usage.usage_context),
}
# Spend's terms and their weights (D-SPEND-TERMS): each a call metric above,
# summed and weighted, adds up to spend (``-v`` works it in the run's numbers).
SPEND_TERMS = (("input_tokens", 1.0), ("cache_read_tokens", usage.CACHE_READ_WEIGHT),
               ("cache_write_5m_tokens", usage.CACHE_WRITE_WEIGHT["5m"]),
               ("cache_write_1h_tokens", usage.CACHE_WRITE_WEIGHT["1h"]))

# Causes of an increment. All but ``shrink`` book non-negative mass; ``shrink``
# books the signed delta of a window that got smaller (``usage.context_delta``
# has the measurement) and is reported as its own signed row, never spread.
# ``inherited`` is what a fork or replayed window copied: its parent window's
# occupancy at the branch call (D-FORK-INHERITED); ``starting_context`` is then the
# window's own start, the remainder, never split by content (D-NO-START-SPLIT).
STARTING_CONTEXT = "starting_context"
INHERITED = "inherited"
REPLIES = "replies"
TOOL_RESULT = "tool_result"
USER_TEXT = "user_text"
AMBIGUOUS = "ambiguous"
SHRINK = "shrink"
CAUSES = (STARTING_CONTEXT, INHERITED, REPLIES, TOOL_RESULT, USER_TEXT, AMBIGUOUS, SHRINK)
EXACT_CAUSES = (TOOL_RESULT, USER_TEXT)

# Why an increment is ``ambiguous``. ``unexplained`` (0 of 51,960
# intervals, 2026-07-28) is declared so an empty interval is labelled.
SEVERAL = "several"
LESS_THAN_REPLY = "less_than_reply"
UNEXPLAINED = "unexplained"
REASONS = (SEVERAL, LESS_THAN_REPLY, UNEXPLAINED)

# A window is one context window (D-CONTEXT-WINDOW, ``windows``). The window
# dimensions are constant over a window, so a filter on them selects whole
# windows and the reconciliation still telescopes. A main window has no
# ``subagent`` (D-AGENT-DIM). ``window`` is ``window_value`` of the window's
# identity: the one dimension that isolates a window, a drill target, never
# a default table. ``started_by`` names what began it (D-START-CAUSE).
# ``peak`` is the band of the window's largest call (D-PEAK-BAND).
# ``DIMENSIONS`` is the presentation order of the tables.
PROJECT_DIM = "project"
SESSION_DIM = "session"
SUBAGENT_DIM = "subagent"
WINDOW_DIM = "window"
STARTED_BY_DIM = "started_by"
PEAK_DIM = "peak"
WINDOW_DIMENSIONS = (PROJECT_DIM, SESSION_DIM, SUBAGENT_DIM, WINDOW_DIM, STARTED_BY_DIM, PEAK_DIM)
CAUSE_DIM = "cause"
TOOL_DIM = "tool"
COMMAND_DIM = "command"
REASON_DIM = "reason"
DIMENSIONS = WINDOW_DIMENSIONS + (CAUSE_DIM, TOOL_DIM, COMMAND_DIM, REASON_DIM)
KIND_DIMENSIONS = {CALL: WINDOW_DIMENSIONS, INCREMENT: DIMENSIONS}
# Starts: fork beats subagent_start; ``replayed``: a main file opening with
# another file's records (a resume or /branch).
SESSION_START = "session_start"
SUBAGENT_START = "subagent_start"
FORK = "fork"
REPLAYED = "replayed"
COMPACTION = "compaction"
STARTS = (SESSION_START, SUBAGENT_START, FORK, REPLAYED, COMPACTION)
# A window's ``peak``: the band its largest call's ``context_tokens`` falls
# in, each band's lower edge inclusive (K = 1,000). A label, never a summed
# peak; ASCII and shell-safe, so the pin ``peak=200K+`` needs no quoting.
BANDS = ("0-50K", "50-100K", "100-200K", "200K+")
BAND_EDGES = (0, 50000, 100000, 200000)  # each band's lower edge, inclusive
VOCABULARY = {CAUSE_DIM: CAUSES, REASON_DIM: REASONS, STARTED_BY_DIM: STARTS,
              PEAK_DIM: BANDS}  # declared values
# Dimensions whose rows print in a declared order, not by mass, in every
# view: the bands fullest first.
ORDERED = {PEAK_DIM: BANDS[::-1]}


def band(tokens: float) -> str:
    """The ``peak`` band of a window whose largest call held ``tokens``."""
    return [b for b, edge in zip(BANDS, BAND_EDGES) if tokens >= edge][-1]


# The catch-all row of a table by a dimension, ``RESIDUAL_NOTES[dim]``: its
# label, what its facts lack (``no tool``, ``main``; printed as is, it pins
# that row: ``query.select`` reads its value as None), and the cases ``-v``
# lists, each a reading of a residual fact and the dims it holds for. An
# ambiguous change is residual when its candidates share no one tool (by tool)
# or no one command (by command); a tool_result, when its tool_use did not
# resolve (by tool) or its tool has no command (by command).
Case = Tuple[str, Callable[[dict], bool]]


def _cause(cause: str) -> Callable[[dict], bool]:
    return lambda dims: dims.get(CAUSE_DIM) == cause


RESIDUAL_NOTES: Dict[str, Tuple[str, List[Case]]] = {
    SUBAGENT_DIM: ("main", []),  # typable as printed: subagent=main
    TOOL_DIM: ("no tool", [(c, _cause(c)) for c in (STARTING_CONTEXT, REPLIES, USER_TEXT, INHERITED)] + [
        ("%s naming no one tool" % AMBIGUOUS, _cause(AMBIGUOUS)),
        ("an unresolved %s" % TOOL_RESULT, _cause(TOOL_RESULT))]),
    COMMAND_DIM: ("no command", [
        ("no tool", lambda dims: TOOL_DIM not in dims),
        ("not %s" % "/".join(sorted(heads.EXTRACTORS)),
         lambda dims: TOOL_DIM in dims and _cause(TOOL_RESULT)(dims)),
        ("%s naming no one command" % AMBIGUOUS, lambda dims: TOOL_DIM in dims and _cause(AMBIGUOUS)(dims))]),
    REASON_DIM: ("not %s" % AMBIGUOUS, [  # shrink is the signed row, never residual
        (c, _cause(c)) for c in CAUSES if c not in (AMBIGUOUS, SHRINK)]),
}


def residual_cases(dim: str) -> str:
    """Every case the catch-all row of a table by ``dim`` can hold: for
    ``-v``, after its label."""
    return ", ".join(text for text, _ in RESIDUAL_NOTES[dim][1])


# A catch-all that is a population, not a remainder: ``main`` is windows like
# any subagent's, so it is in its table's share base (D-MAIN-IN-BASE).
IN_BASE = (SUBAGENT_DIM,)


def residual_label(dim: str) -> str:
    """The catch-all row's label in a table by ``dim``: what its facts lack."""
    return RESIDUAL_NOTES[dim][0] if dim in RESIDUAL_NOTES else "no " + dim

# Evidence keys: an ambiguous increment lists its contributors; a fork's
# starting context names the parent ids its fork-context-ref gives; an inherited
# increment names its parent window and the parent's branch call.
CANDIDATES = "candidates"
PARENT_SESSION = "parent_session"
PARENT_LAST_UUID = "parent_last_uuid"
PARENT_WINDOW = "parent_window"
BRANCH_CALL = "branch_call"


class SchemaError(ValueError):
    pass


def metric(name: str) -> Metric:
    try:
        return METRICS[name]
    except KeyError:
        raise SchemaError("unknown metric %r; declared: %s"
                          % (name, ", ".join(sorted(METRICS))))


def check_dimension(dim: str, kind: Optional[str] = None) -> str:
    """``dim`` is declared and, when ``kind`` is given, carried by it: a
    dimension the carrier never has would print a confident zero."""
    if dim not in DIMENSIONS:
        raise SchemaError("unknown dimension %r; declared: %s"
                          % (dim, ", ".join(DIMENSIONS)))
    if kind is not None and dim not in KIND_DIMENSIONS[kind]:
        raise SchemaError("dimension %r is never carried by %s, which carry: %s"
                          % (dim, PLURAL[kind], ", ".join(KIND_DIMENSIONS[kind])))
    return dim


def nearest(text: str, choices: List[str]) -> Optional[str]:
    """The choice closest to ``text``, case aside; none when nothing is close."""
    lowered = {c.lower(): c for c in choices}
    close = difflib.get_close_matches(text.lower(), list(lowered), 1, 0.6)
    return lowered[close[0]] if close else None


def unknown_value(dim: str, value: str) -> str:
    """The refusal of an undeclared value: the nearest declared one as a pin."""
    near = nearest(value, VOCABULARY[dim])
    return "unknown %s %r%s" % (dim, value, "; nearest: %s=%s" % (dim, near) if near else "")


def check_value(dim: str, value: Optional[str]) -> Optional[str]:
    """``value`` is declared, when ``dim`` has a vocabulary: a filter on a
    misspelt cause would print a confident zero."""
    if dim in VOCABULARY and value not in VOCABULARY[dim]:
        raise SchemaError("%s; declared: %s" % (unknown_value(dim, str(value)), ", ".join(VOCABULARY[dim])))
    return value


class Locator(NamedTuple):
    file: str
    line: int
    uuid: Optional[str]


class WindowKey(NamedTuple):
    """A window's identity: its file and the physical line of its start
    record (the file's first, or the compaction marker's). Independent of
    dedup and ``--since``; what ``reconcile`` and ``window_count`` key on."""
    file: str
    line: int


def window_value(key: WindowKey) -> str:
    """The ``window`` value: 8 hex of sha1 over ``file:line``. Display and
    pins only; a collision cannot merge two windows' accounting."""
    return hashlib.sha1(("%s:%d" % key).encode("utf-8")).hexdigest()[:8]


class Fact(NamedTuple):
    kind: str
    dims: dict      # dimension name -> str value (ids, names, declared constants), only those this fact has
    metrics: dict   # metric name -> number, only metrics of this fact's kind
    locator: Locator
    evidence: dict  # drill material that is not a dimension: candidates, parent ids
    window: WindowKey


class Candidate(NamedTuple):
    """Evidence of one contributor of an ambiguous increment: where it is,
    the dimensions it would have booked, and its size as the transcript
    records it: the characters of its text and its non-text parts (an
    image), uncounted. No token count is recorded per contributor, and none
    is estimated."""
    locator: Locator
    dims: dict
    chars: Optional[int] = None
    other: int = 0


def fact(kind: str, dims: dict, metrics: dict, locator: Locator,
         evidence: Optional[dict] = None, window: Optional[WindowKey] = None) -> Fact:
    """Build a fact, refusing one whose metrics or dimensions are undeclared
    or whose metrics belong to the other kind. Without ``window`` (a
    hand-built fact) it sits in its file's one window, keyed at line 1."""
    if kind not in KINDS:
        raise SchemaError("unknown fact kind %r" % kind)
    for name in metrics:
        if metric(name).carrier != kind:
            raise SchemaError("%s is carried by %s facts, not %s"
                              % (name, metric(name).carrier, kind))
    for dim in dims:
        check_value(check_dimension(dim, kind), dims[dim])
    if kind == INCREMENT:
        check_value(CAUSE_DIM, dims.get(CAUSE_DIM))
    return Fact(kind, dims, metrics, locator, evidence or {}, window or WindowKey(locator.file, 1))
