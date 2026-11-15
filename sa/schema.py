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

# Causes of an increment. The first five book non-negative mass; ``shrink``
# books the signed delta of a window that got smaller (``usage.context_delta``
# has the measurement) and is reported as its own signed row, never spread.
WINDOW_HEAD = "window_head"
FEED_FORWARD = "feed_forward"
TOOL_RESULT = "tool_result"
USER_TEXT = "user_text"
AMBIGUOUS = "ambiguous"
SHRINK = "shrink"
CAUSES = (WINDOW_HEAD, FEED_FORWARD, TOOL_RESULT, USER_TEXT, AMBIGUOUS, SHRINK)
EXACT_CAUSES = (TOOL_RESULT, USER_TEXT)

# Why an increment is ``ambiguous``. ``no_contributor`` was measured at 0 of
# 51,960 intervals (2026-07-28 sweep); it is declared so that an empty
# interval, should one appear, is labelled rather than miscounted.
MULTI_CONTRIBUTOR = "multi_contributor"
NEGATIVE_REMAINDER = "negative_remainder"
NO_CONTRIBUTOR = "no_contributor"
REASONS = (MULTI_CONTRIBUTOR, NEGATIVE_REMAINDER, NO_CONTRIBUTOR)

# A window is a file. The window dimensions are constant over a window
# (no file in the Phase 0 sweep named in ``corpus`` mixes assistant records
# from two agentIds), so a filter on them selects whole windows and the
# reconciliation footer still telescopes. A main window has no ``agent``
# (D-AGENT-DIM): only a subagent's window carries one. ``window`` is the
# root-relative file name (D-WINDOW-DIM): the one dimension that selects a
# main window alone, since ``session`` keeps its subagents too; a drill
# target, never a default table. ``DIMENSIONS`` is the presentation order
# of the tables; the headline walks each view's levers (``cli.VIEWS``).
PROJECT_DIM = "project"
SESSION_DIM = "session"
AGENT_DIM = "agent"
WINDOW_DIM = "window"
WINDOW_DIMENSIONS = (PROJECT_DIM, SESSION_DIM, AGENT_DIM, WINDOW_DIM)
CAUSE_DIM = "cause"
TOOL_DIM = "tool"
HEAD_DIM = "head"
REASON_DIM = "reason"
DIMENSIONS = WINDOW_DIMENSIONS + (CAUSE_DIM, TOOL_DIM, HEAD_DIM, REASON_DIM)
KIND_DIMENSIONS = {CALL: WINDOW_DIMENSIONS, INCREMENT: DIMENSIONS}
VOCABULARY = {CAUSE_DIM: CAUSES, REASON_DIM: REASONS}  # dimensions whose values are declared

# Evidence keys: an ambiguous increment lists its contributors; a fork's
# window head names the parent whose context it inherited.
CANDIDATES = "candidates"
PARENT_SESSION = "parent_session"
PARENT_LAST_UUID = "parent_last_uuid"


class SchemaError(ValueError):
    pass


def metric(name: str) -> Metric:
    try:
        return METRICS[name]
    except KeyError:
        raise SchemaError("unknown metric %r; declared: %s"
                          % (name, ", ".join(sorted(METRICS))))


def check_dimension(dim: str, kind: Optional[str] = None) -> str:
    """``dim`` is declared and, when ``kind`` is given, carried by that kind:
    a filter or table over a dimension the carrier never has would print a
    confident zero."""
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


class Fact(NamedTuple):
    kind: str
    dims: dict      # dimension name -> str value (ids, names, declared constants), only those this fact has
    metrics: dict   # metric name -> number, only metrics of this fact's kind
    locator: Locator
    evidence: dict  # drill material that is not a dimension: candidates, parent ids


class Candidate(NamedTuple):
    """Evidence of one contributor of an ambiguous increment: where it is
    and the dimensions it would have booked."""
    locator: Locator
    dims: dict


def fact(kind: str, dims: dict, metrics: dict, locator: Locator,
         evidence: Optional[dict] = None) -> Fact:
    """Build a fact, refusing one whose metrics or dimensions are undeclared
    or whose metrics belong to the other kind."""
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
    return Fact(kind, dims, metrics, locator, evidence or {})


# The glossary: every term the output prints, in plain words, and why its
# number might surprise a reader. It drives ``sa explain``, the key under the
# tables, the ``°`` markers and ``--help``; a test holds that every declared
# metric, kind, dimension, cause and reason has an entry. ``marked`` terms
# are the irreducible concepts: they print with ``MARKER`` where the key
# names them. The residual row's label is declared here so the key and the
# glossary share it.
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
        "one transcript file: a main session or one subagent, each its own context window",
        "a resume, fork or /branch writes a new file, so one session can be several windows;"
        " a file with no call is read but is no window", True),
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
    PROJECT_DIM: Term("the project directory the session ran in, path-encoded",
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
        "the context a window's first call already had: system prompt, tools, CLAUDE.md and"
        " first message, or the context a fork or resume inherited",
        "often the largest cause; the transcript does not record its contents, so it is"
        " not split further", True),
    FEED_FORWARD: Term("the previous call's own output, read back by the next call",
                       "it is what the model wrote, not what a tool returned"),
    TOOL_RESULT: Term("a tool's output, booked exactly to its tool and head",
                      "the part you can act on: drill it with --where tool="),
    USER_TEXT: Term("text typed into the window (by you or a hook)",
                    "usually small: typing rarely fills a window"),
    AMBIGUOUS: Term(
        "an interval whose tokens more than one contributor (or none) could have put there;"
        " never spread over them",
        "it still names a tool when every candidate came from one; --by fact lists the"
        " candidates", True),
    SHRINK: Term("a window that got smaller between two calls (a compaction): a negative row",
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
    EXACT: Term("an interval with one contributor: booked to it after subtracting the"
                " previous call's output",
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
