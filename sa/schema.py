"""The one table every other module reads from.

A fact is one of two kinds. A ``call`` fact is one max-merged assistant
message and carries what it cost; an ``increment`` fact is one booked change
of context occupancy and carries where the context went. Each metric names
the single kind that carries it, so the two can never be summed together
(measured: ``context_delta`` read from both kinds totals exactly 2.000000x
the truth).

Adding a metric, a cause or a dimension is one line here. An unknown name
raises rather than skipping: a silent skip is how a wrong number stays
plausible.
"""
from typing import Dict, NamedTuple, Optional

ADDITIVE = "additive"
PEAK = "peak"

CALL = "call"
INCREMENT = "increment"
KINDS = (CALL, INCREMENT)


class Metric(NamedTuple):
    aggregation: str  # ADDITIVE sums; PEAK is a high-water mark and never sums
    carrier: str      # the one fact kind that carries it
    unit: str


METRICS = {
    "context_delta": Metric(ADDITIVE, INCREMENT, "context tokens"),
    "spend": Metric(ADDITIVE, CALL, "input-side base-token-equivalents"),
    "output_tokens": Metric(ADDITIVE, CALL, "tokens"),
    "cache_write_1h_tokens": Metric(ADDITIVE, CALL, "tokens"),
    "cache_write_5m_tokens": Metric(ADDITIVE, CALL, "tokens"),
    "context_tokens": Metric(PEAK, CALL, "context tokens"),
}  # type: Dict[str, Metric]

# Causes of an increment. The first five book non-negative mass; ``shrink``
# books the signed delta of a window that got smaller (830 of 45,555 measured
# call pairs) and is reported as its own signed row, never spread.
WINDOW_HEAD = "window_head"
FEED_FORWARD = "feed_forward"
TOOL_RESULT = "tool_result"
USER_TEXT = "user_text"
AMBIGUOUS = "ambiguous"
SHRINK = "shrink"
CAUSES = (WINDOW_HEAD, FEED_FORWARD, TOOL_RESULT, USER_TEXT, AMBIGUOUS, SHRINK)
EXACT_CAUSES = (TOOL_RESULT, USER_TEXT)

# Why an increment is ``ambiguous``. ``no_contributor`` was measured at 0 of
# 51,960 intervals; it is declared so that an empty interval, should one
# appear, is labelled rather than miscounted as multi_contributor.
MULTI_CONTRIBUTOR = "multi_contributor"
NEGATIVE_REMAINDER = "negative_remainder"
NO_CONTRIBUTOR = "no_contributor"
REASONS = (MULTI_CONTRIBUTOR, NEGATIVE_REMAINDER, NO_CONTRIBUTOR)

# A window is a file. The first three dimensions are constant over a window
# (measured: 0 of 1,845 files mix assistant records from two agentIds), so a
# filter on them selects whole windows and the reconciliation footer still
# telescopes.
WINDOW_DIMENSIONS = ("project", "session", "agent")
DIMENSIONS = WINDOW_DIMENSIONS + ("cause", "tool", "head", "reason",
                                  "candidate_count")
KIND_DIMENSIONS = {CALL: WINDOW_DIMENSIONS, INCREMENT: DIMENSIONS}

RESIDUAL = "∅"  # the row for facts that lack the grouped dimension


class SchemaError(KeyError):
    pass


def metric(name):
    # type: (str) -> Metric
    try:
        return METRICS[name]
    except KeyError:
        raise SchemaError("unknown metric %r; declared: %s"
                          % (name, ", ".join(sorted(METRICS))))


def check_cause(cause):
    # type: (str) -> str
    if cause not in CAUSES:
        raise SchemaError("unknown cause %r; declared: %s"
                          % (cause, ", ".join(CAUSES)))
    return cause


def check_dimension(dim, kind=None):
    # type: (str, Optional[str]) -> str
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


class Locator(NamedTuple):
    file: str
    line: int
    uuid: Optional[str]


class Fact(NamedTuple):
    kind: str
    dims: dict      # dimension name -> value, only the dimensions this fact has
    metrics: dict   # metric name -> number, only metrics of this fact's kind
    locator: Locator
    evidence: dict  # drill material that is not a dimension (lists, parent ids)


def fact(kind, dims, metrics, locator, evidence=None):
    # type: (str, dict, dict, Locator, Optional[dict]) -> Fact
    """Build a fact, refusing one whose metrics or dimensions are undeclared
    or whose metrics belong to the other kind."""
    if kind not in KINDS:
        raise SchemaError("unknown fact kind %r" % kind)
    for name in metrics:
        if metric(name).carrier != kind:
            raise SchemaError("%s is carried by %s facts, not %s"
                              % (name, metric(name).carrier, kind))
    for dim in dims:
        check_dimension(dim, kind)
    if kind == INCREMENT:
        check_cause(dims.get("cause"))
    return Fact(kind, dims, metrics, locator, evidence or {})
