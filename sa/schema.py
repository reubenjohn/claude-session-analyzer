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
import hashlib
from typing import Callable, Dict, NamedTuple, Optional

from . import usage

ADDITIVE = "additive"
PEAK = "peak"

CALL = "call"
INCREMENT = "increment"
KINDS = (CALL, INCREMENT)


class Metric(NamedTuple):
    aggregation: str  # ADDITIVE sums; PEAK is a high-water mark and never sums
    carrier: str      # the one fact kind that carries it
    unit: str
    # A call metric is read from the call's max-merged usage dict; an
    # increment metric is booked by the walk and has no reader.
    read: Optional[Callable[[dict], float]] = None


# The two metrics the reconciliation joins: every booked increment against
# the occupancy the window's last call reports.
CONTEXT_DELTA = "context_delta"
CONTEXT_TOKENS = "context_tokens"
SPEND = "spend"

METRICS: Dict[str, Metric] = {
    CONTEXT_DELTA: Metric(ADDITIVE, INCREMENT, "context tokens"),
    SPEND: Metric(ADDITIVE, CALL, "input-side base-token-equivalents", usage.usage_spend),
    "output_tokens": Metric(ADDITIVE, CALL, "tokens", lambda u: u["output_tokens"]),
    "cache_write_1h_tokens": Metric(ADDITIVE, CALL, "tokens", lambda u: usage.cache_creation_tiers(u)[0]),
    "cache_write_5m_tokens": Metric(ADDITIVE, CALL, "tokens", lambda u: usage.cache_creation_tiers(u)[1]),
    CONTEXT_TOKENS: Metric(PEAK, CALL, "context tokens", usage.usage_context),
}

# Causes of an increment. All but ``shrink`` book non-negative mass; ``shrink``
# books the signed delta of a window that got smaller (``usage.context_delta``
# has the measurement) and is reported as its own signed row, never spread.
# ``inherited`` is what a fork or replayed window copied: its parent window's
# occupancy at the branch call (D-FORK-INHERITED); ``window_head`` is then the
# window's own start, the remainder, never split by content (D-NO-START-SPLIT).
WINDOW_HEAD = "window_head"
INHERITED = "inherited"
FEED_FORWARD = "feed_forward"
TOOL_RESULT = "tool_result"
USER_TEXT = "user_text"
AMBIGUOUS = "ambiguous"
SHRINK = "shrink"
CAUSES = (WINDOW_HEAD, INHERITED, FEED_FORWARD, TOOL_RESULT, USER_TEXT, AMBIGUOUS, SHRINK)
EXACT_CAUSES = (TOOL_RESULT, USER_TEXT)

# Why an increment is ``ambiguous``. ``no_contributor`` (0 of 51,960
# intervals, 2026-07-28) is declared so an empty interval is labelled.
MULTI_CONTRIBUTOR = "multi_contributor"
NEGATIVE_REMAINDER = "negative_remainder"
NO_CONTRIBUTOR = "no_contributor"
REASONS = (MULTI_CONTRIBUTOR, NEGATIVE_REMAINDER, NO_CONTRIBUTOR)

# A window is one context window (D-CONTEXT-WINDOW, ``windows``). The window
# dimensions are constant over a window, so a filter on them selects whole
# windows and the reconciliation still telescopes. A main window has no
# ``agent`` (D-AGENT-DIM). ``window`` is ``window_value`` of the window's
# identity: the one dimension that isolates a window, a drill target, never
# a default table. ``start`` names what began it (D-START-CAUSE).
# ``DIMENSIONS`` is the presentation order of the tables.
PROJECT_DIM = "project"
SESSION_DIM = "session"
AGENT_DIM = "agent"
WINDOW_DIM = "window"
START_DIM = "start"
WINDOW_DIMENSIONS = (PROJECT_DIM, SESSION_DIM, AGENT_DIM, WINDOW_DIM, START_DIM)
CAUSE_DIM = "cause"
TOOL_DIM = "tool"
HEAD_DIM = "head"
REASON_DIM = "reason"
DIMENSIONS = WINDOW_DIMENSIONS + (CAUSE_DIM, TOOL_DIM, HEAD_DIM, REASON_DIM)
KIND_DIMENSIONS = {CALL: WINDOW_DIMENSIONS, INCREMENT: DIMENSIONS}
# Starts: fork beats subagent; ``replayed``: a main file opening with
# another file's records (a resume or /branch).
SESSION_START = "session_start"
SUBAGENT = "subagent"
FORK = "fork"
REPLAYED = "replayed"
COMPACTION = "compaction"
STARTS = (SESSION_START, SUBAGENT, FORK, REPLAYED, COMPACTION)
VOCABULARY = {CAUSE_DIM: CAUSES, REASON_DIM: REASONS, START_DIM: STARTS}  # declared values

# Evidence keys: an ambiguous increment lists its contributors; a fork's
# window head names the parent ids its fork-context-ref gives; an inherited
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
        raise SchemaError("dimension %r is never carried by %s facts, which carry: %s"
                          % (dim, kind, ", ".join(KIND_DIMENSIONS[kind])))
    return dim


def check_value(dim: str, value: Optional[str]) -> Optional[str]:
    """``value`` is declared, when ``dim`` has a vocabulary: a filter on a
    misspelt cause would print a confident zero."""
    if dim in VOCABULARY and value not in VOCABULARY[dim]:
        raise SchemaError("unknown %s %r; declared: %s"
                          % (dim, value, ", ".join(VOCABULARY[dim])))
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
    ``--where`` only; a collision cannot merge two windows' accounting."""
    return hashlib.sha1(("%s:%d" % key).encode("utf-8")).hexdigest()[:8]


class Fact(NamedTuple):
    kind: str
    dims: dict      # dimension name -> str value (ids, names, declared constants), only those this fact has
    metrics: dict   # metric name -> number, only metrics of this fact's kind
    locator: Locator
    evidence: dict  # drill material that is not a dimension: candidates, parent ids
    window: WindowKey


class Candidate(NamedTuple):
    """Evidence of one contributor of an ambiguous increment: where it is
    and the dimensions it would have booked."""
    locator: Locator
    dims: dict


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


# The glossary: every term the output prints, in plain words, and why its
# number might surprise. It drives ``sa explain``, the key, the ``°`` markers
# and ``--help``; a test holds that every declared term has an entry.
# ``marked`` terms, the irreducible concepts, print with ``MARKER``.
RESIDUAL_LABEL = "∅"
EXACT = "exact"
DRILL = "drill"
MARKER = "°"


class Term(NamedTuple):
    meaning: str
    surprise: str
    marked: bool = False


GLOSSARY: Dict[str, Term] = {
    WINDOW_DIM: Term(
        "one context window: from a session start, subagent, fork, replay or compaction to"
        " its file's end or the next compaction; named by a short hash",
        "a file holds one window per compaction that a call follows; a file with no call"
        " is read but is no window", True),
    START_DIM: Term("what began the window: " + ", ".join(STARTS),
                    "a compaction starts a new window in the same file; its head re-counts"
                    " the system prompt"),
    CALL: Term("one assistant message, its split records merged: what spend is read from",
               "a message written as several records counts once"),
    INCREMENT: Term("one booked change of a window's context between two calls:"
                    " what context_delta is read from",
                    "one ambiguous increment can name several tool results"),
    CONTEXT_DELTA: Term(
        "context tokens booked to what put them in a window; summed, they equal the"
        " windows' final sizes",
        "it is net: what a compaction or other shrink removed is not counted, so a window"
        " that grew to 700K and compacted to 70K reports 70K"),
    SPEND: Term("what the calls billed, in input-side base-token-equivalents"
                " (cache writes x1.25 or x2.0, cache reads x0.1)",
                "every call re-reads its whole context, so spend grows with context times"
                " calls; it is never quoted in dollars"),
    CONTEXT_TOKENS: Term("one call's context size; a peak, so only its largest call is shown",
                         "never summed: a sum counts a token once per call that re-read it"),
    "output_tokens": Term("tokens the calls generated",
                          "the next call reads them back, as feed_forward"),
    "cache_write_1h_tokens": Term("tokens written to the 1-hour prompt cache (billed x2.0)",
                                  "each call writes one cache tier only"),
    "cache_write_5m_tokens": Term("tokens written to the 5-minute prompt cache (billed x1.25)",
                                  "each call writes one cache tier only"),
    PROJECT_DIM: Term("the project directory the session ran in, path-encoded (/ as -),"
                      " home printed as ~",
                      "a long name prints as its tail in a default table; --by prints it whole"),
    SESSION_DIM: Term("a session id: its main window and every subagent window",
                      "--where session= keeps the subagents too; --where window= isolates one"),
    AGENT_DIM: Term("a subagent's id; a main window has none",
                    "main windows are the ∅ row of by agent"),
    CAUSE_DIM: Term("what kind of thing put the tokens in the context",
                    "window_head is often the largest and cannot be split further"),
    TOOL_DIM: Term("the tool whose result put the tokens there",
                   "context the model wrote or you typed has no tool: it is ∅"),
    HEAD_DIM: Term("<tool>:<summary>: a Bash command's first command word (Bash:git) or a"
                   " file tool's file extension (Read:py)",
                   "never a path; python3 x.py is Bash:python3"),
    REASON_DIM: Term("why an increment is ambiguous", "only ambiguous increments have one"),
    WINDOW_HEAD: Term(
        "the context a window's first call already had, less what it inherited: system prompt,"
        " tools, CLAUDE.md and first message, or a compaction's summary",
        "often the largest cause; the transcript does not record its contents, so it is"
        " not split further", True),
    INHERITED: Term("what a fork or replayed window copied: its parent window's occupancy at"
                    " the branch call",
                    "counted once: left out of the total when the parent window is kept;"
                    " its breakdown is the parent's up to that call"),
    FEED_FORWARD: Term("the previous call's own output, read back by the next call",
                       "it is what the model wrote, not what a tool returned"),
    TOOL_RESULT: Term("a tool's output, booked exactly to its tool and head",
                      "the part you can act on: drill it with --where tool="),
    USER_TEXT: Term("text typed into the window (by you or a hook)",
                    "usually small: typing rarely fills a window"),
    AMBIGUOUS: Term(
        "an interval not booked to one contributor: more than one entered, none did, or it"
        " grew by less than the previous call's output; never spread over them",
        "it still names a tool when every candidate came from one; --by fact lists the"
        " candidates", True),
    SHRINK: Term("a window that got smaller between two calls (often, not always, a"
                 " compaction): a negative row",
                 "excluded from every share, always in the checks"),
    MULTI_CONTRIBUTOR: Term("several results or texts entered in one interval",
                            "the tokens are not split between them"),
    NEGATIVE_REMAINDER: Term("the interval grew by less than the previous call's output",
                             "rare; the whole delta stays ambiguous"),
    NO_CONTRIBUTOR: Term("the context grew with nothing recorded to explain it",
                         "declared so it is labelled should it appear"),
    RESIDUAL_LABEL: Term("the part of a table's total with no value for its dimension;"
                         " the key says why, per table",
                         "often most of the total: window_head has no tool", True),
    EXACT: Term("an interval with one contributor that grew by at least the previous call's"
                " output: booked to it after subtracting that output",
                "exact given that model; bookkeeping attachments fold into the remainder"),
    DRILL: Term("a --where on cause, tool, head or reason: narrows the facts inside the"
                " windows kept",
                "the checks still cover the whole windows, not the drill"),
}


def explain(term: str) -> Term:
    try:
        return GLOSSARY[term.rstrip(MARKER)]
    except KeyError:
        raise SchemaError("unknown term %r; known: %s" % (term, ", ".join(GLOSSARY)))
