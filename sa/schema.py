"""The one table every other module reads from.

A fact is one of two kinds. A ``call`` fact is one max-merged assistant
message and carries what it cost; an ``increment`` fact is one booked change
of context occupancy and carries where the context went. Each metric names
the single kind that carries it, so the two can never be summed together
(measured: ``context_delta`` read from both kinds totals exactly 2.000000x
the truth).

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
# target, never a default table. ``DIMENSIONS`` is ordered general to
# specific; a headline leads with the most specific one shown
# (``render.report``).
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


class SchemaError(KeyError):
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
