"""``--by fact``: the individual facts, largest first, each with its
dimensions and, indented under it, its evidence."""
from typing import Iterator, List, Optional

from . import glossary, query, schema, style
from .schema import Fact
from .tables import at, num, tags, uuid


def leaves(facts: List[Fact], metric: str, limit: int, calls: Optional[int] = None) -> List[str]:
    """The ``limit`` largest facts (a shrink is as large as its |mass|),
    each with its dimensions and, indented under it, its evidence: the
    candidate contributors of an ambiguous increment, the parent of a fork's
    starting context, the parent window and branch call of an inherited
    increment. Under a per-call metric each prints its part of the average
    (over the view's ``calls``) beside its raw ``context_delta``, the
    tokens it put in its window, and they rank by that part (D-PER-CALL)."""
    spec = schema.metric(metric)
    per_call = spec.aggregation == schema.PER_CALL
    largest = sorted((f for f in facts if f.kind == spec.carrier),
                     key=lambda f: -abs(f.metrics[metric]))[:limit]
    columns = [metric] + ([schema.CONTEXT_DELTA] if per_call else [])
    widths = [max(16, len(glossary.printed(m))) for m in columns]
    divisor = query.per(metric, calls)  # a per-call metric without its population raises

    def figures(values) -> str:
        return "  ".join("%*s" % (w, v) for w, v in zip(widths, values))
    lines = [figures(glossary.printed(m) for m in columns) + "  file:line  uuid  dimensions"]  # as in the tables
    for f in largest:
        values = [num(f.metrics[metric] / divisor)] + [num(f.metrics[m]) for m in columns[1:]]
        lines.append("%s  %s  %s  %s" % (figures(values), at(f.locator), uuid(f.locator), tags(f.dims)))
        lines += list(_evidence(f.evidence))
    lines[1:] = [style.tag(line, "", values=((0, len(line)),)) for line in lines[1:]]  # values only
    return lines


def recorded(candidate: schema.Candidate) -> str:
    """``1,204 characters  `` (``+ 1 non-text`` when an image came too):
    characters as the transcript records them, never converted to tokens;
    nothing when the size is unknown."""
    if candidate.chars is None:
        return ""
    other = " + %s non-text" % num(candidate.other) if candidate.other else ""
    return "%s characters%s  " % (num(candidate.chars), other)


HEAVIEST = " largest first, in characters as recorded"  # the candidates line: which one is heavy


def _evidence(evidence: dict) -> Iterator[str]:
    """Each key once; the candidates one per line under theirs, largest
    recorded size first (an unknown size last), each with its line, uuid,
    its size as recorded (``recorded``) and the dimensions it would have
    booked: the order says which is heavy, the change stays undivided."""
    for key, value in evidence.items():
        if key == schema.CANDIDATES:
            yield "%18s%s:%s" % ("", key, HEAVIEST if any(c.chars for c in value) else (
                "" if value else " none"))
            for candidate in sorted(value, key=lambda c: -(c.chars or -1)):
                yield "%20s%s %s  %s%s" % ("", at(candidate.locator), uuid(candidate.locator),
                                           recorded(candidate), tags(candidate.dims))
        elif isinstance(value, schema.WindowKey):  # a parent window: its --where value
            yield "%18s%s: %s=%s" % ("", key, schema.WINDOW_DIM, schema.window_value(value))
        elif isinstance(value, schema.Locator):
            yield "%18s%s: %s %s" % ("", key, at(value), uuid(value))
        else:
            yield "%18s%s: %s" % ("", key, value)
