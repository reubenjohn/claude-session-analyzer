"""One file's records become facts.

A window is a file. Its ``call`` facts are the max-merged assistant messages
that carried usage; its ``increment`` facts book every change of context
occupancy from an empty window to the last call, so that per window
``sum(context_delta) == final occupancy`` by construction. What the
telescoping chain cannot check is whether one interval's mass went to the
right contributor; that is why only an interval with exactly one
token-relevant contributor is booked as exact and everything else is one
``ambiguous`` bucket with its reason, never a spread.

Records marked duplicate (replays owned by another file) mint no call, no
contributor and no fact; the tool_use join index spans every record so a
tool_result whose tool_use was replayed still resolves to its tool. A file
whose first calls are replays books ``window_head`` at its first live call,
the ruled inherited-context row.

Every figure below marked "local corpus" was measured by this package over
the live local corpus, 33 files, 2026-10-01; the Phase 0 figures name their
own population.
"""
from typing import Dict, Iterator, List, NamedTuple, Optional, Tuple

from . import heads, schema, usage
from .corpus import Record, SourceFile
from .schema import Fact, Locator

ToolUses = Dict[str, Tuple[str, dict]]


def _message(data: dict) -> dict:
    message = data.get("message")
    return message if isinstance(message, dict) else {}


def _blocks(data: dict) -> List[dict]:
    content = _message(data).get("content")
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict)]


class Call(NamedTuple):
    first: int      # index of the first constituent in the records walked
    record: Record  # the first constituent, which locates the call
    usage: dict     # max-merged over the constituents


def calls(records: List[Record]) -> List[Call]:
    """Usage-carrying calls in first-constituent order.

    Assistant records sharing a ``message.id`` are one call, merged by
    ``usage.max_merge_usage`` (its docstring has why a field-wise max). A
    record without ``message.id`` is a call by itself. A call carries usage
    iff it has occupancy or output: a ``<synthetic>`` zero-usage record is
    not a call and does not advance the chain.
    """
    groups: Dict[object, List[int]] = {}
    for index, record in enumerate(records):
        if record.data.get("type") != "assistant":
            continue
        message_id = _message(record.data).get("id")
        key = message_id if message_id is not None else ("line", record.line)
        groups.setdefault(key, []).append(index)
    found = []
    for indices in groups.values():
        merged = usage.max_merge_usage(
            [_message(records[i].data).get("usage") for i in indices])
        if usage.usage_context(merged) or merged.get("output_tokens"):
            found.append(Call(indices[0], records[indices[0]], merged))
    return found


def tool_uses(records: List[Record]) -> ToolUses:
    """``tool_use.id -> (tool name, input)`` over the file. Every tool_result's
    ``tool_use_id`` resolves to an earlier record in its own file (59,740 of
    59,740 in the Phase 0 sweep), so this is the whole join."""
    index = {}
    for record in records:
        if record.data.get("type") == "assistant":
            for block in _blocks(record.data):
                if block.get("type") == "tool_use":
                    index[block.get("id")] = (block.get("name"), block.get("input"))
    return index


class Contributor(NamedTuple):
    record: Record
    cause: str
    tool: Optional[str]
    head: Optional[str]

    @property
    def dims(self) -> dict:
        """What an exact increment books for it: the fields that are set,
        named by the dimensions they are."""
        return {k: v for k, v in self._asdict().items() if k != "record" and v is not None}


def contributors(records: List[Record], uses: ToolUses) -> Iterator[Contributor]:
    """The token-relevant records among ``records``: one contributor per
    tool_result block of a user record, and every other user record as user
    text. A record batching several results names several tools, so booking
    it to its first block would be exact to one tool by silent choice; none
    is observed (local corpus: 0 of 808 tool_result records carry more than
    one block), which is why per-block is the fail-closed reading.

    Attachments, system records and bookkeeping types are not contributors.
    Measured over 51,960 intervals (2026-07-28): counting them collapses the
    exact rate from 96.92% to below 1% on versions that emit a per-turn
    attachment, and exact intervals that also hold such records show a lower
    mean remainder, not a higher one.
    """
    for record in records:
        if record.data.get("type") != "user":
            continue
        results = [block for block in _blocks(record.data) if block.get("type") == "tool_result"]
        if not results:
            yield Contributor(record, schema.USER_TEXT, None, None)
        for block in results:
            tool, tool_input = uses.get(block.get("tool_use_id"), (None, None))
            yield Contributor(record, schema.TOOL_RESULT, tool, heads.head_of(tool, tool_input))


def shared_dims(found: List[Contributor]) -> dict:
    """The tool, and then the head, that EVERY candidate of an ambiguous
    interval carries (DECISION_LOG D-AMBIGUOUS-TOOL): the increment keeps its
    cause and reason, and the mass stays in the one residual bucket, but when
    the only ambiguity is which of several calls of one tool it is still
    answerable by tool. A user_text candidate or a tool_result whose tool_use
    did not resolve has no tool, so it unsets both; the head ``other`` is a
    value, not an absence. Local corpus: 79 of 127 multi_contributor
    intervals (404k of 634k ambiguous tokens) share one tool, and 36 of them
    (206k tokens) share the head as well."""
    out = {}
    for dim in (schema.TOOL_DIM, schema.HEAD_DIM):
        values = {c.dims.get(dim) for c in found}
        if len(values) != 1 or None in values:
            return out
        out[dim] = values.pop()
    return out


class Candidate(NamedTuple):
    """Evidence of one contributor of an ambiguous increment."""
    locator: Locator
    dims: dict


def fork_evidence(records: List[Record]) -> dict:
    """A forked agent file opens with a ``fork-context-ref`` naming the
    parent; its first call's occupancy is inherited, not booted, and the
    ids are kept so a later build can stitch windows without a new schema."""
    for record in records:
        if record.data.get("type") == "fork-context-ref":
            return {"parent_session": record.data.get("parentSessionId"),
                    "parent_last_uuid": record.data.get("parentLastUuid")}
    return {}


def _first_value(records: List[Record], key: str) -> Optional[str]:
    for record in records:
        value = record.data.get(key)
        if value:
            return value
    return None


def walk(source: SourceFile) -> Iterator[Fact]:
    """Facts of one window in file order, each call followed by the
    increments it closes.

    An interval's contributors are the user records strictly between the
    previous call's FIRST constituent and the current call's first. A split
    call's constituents interleave with their results (parallel tool use:
    constituent, result, constituent, result, next call; local corpus: 67
    user records sit inside 44 of 588 calls' spans), so slicing from the
    previous call's last constituent hides the earlier result and books a
    two-contributor interval as exact.
    """
    window = {
        "project": source.project,
        "session": _first_value(source.records, "sessionId"),
        "agent": _first_value(source.records, "agentId") or "main",
    }
    uses = tool_uses(source.records)
    live = [record for record in source.records if not record.duplicate]

    def locator(record: Record) -> Locator:
        return Locator(source.name, record.line, record.data.get("uuid"))

    def increment(delta: int, record: Record, evidence: Optional[dict] = None,
                  **dims: Optional[str]) -> Fact:
        all_dims = dict(window)
        all_dims.update((k, v) for k, v in dims.items() if v is not None)
        return schema.fact(schema.INCREMENT, all_dims, {schema.CONTEXT_DELTA: delta},
                           locator(record), evidence)

    def interval(previous: Call, current: Call) -> Iterator[Fact]:
        delta = usage.context_delta(previous.usage, current.usage)
        if delta < 0:
            yield increment(delta, current.record, cause=schema.SHRINK)
            return
        fed_forward = previous.usage["output_tokens"]
        if delta < fed_forward:
            yield increment(delta, current.record, cause=schema.AMBIGUOUS,
                            reason=schema.NEGATIVE_REMAINDER)
            return
        yield increment(fed_forward, previous.record, cause=schema.FEED_FORWARD)
        remainder = delta - fed_forward
        found = list(contributors(live[previous.first + 1:current.first], uses))
        if len(found) == 1:
            yield increment(remainder, found[0].record, **found[0].dims)
            return
        yield increment(
            remainder, current.record, cause=schema.AMBIGUOUS,
            reason=schema.MULTI_CONTRIBUTOR if found else schema.NO_CONTRIBUTOR,
            evidence={"candidates": [Candidate(locator(c.record), c.dims) for c in found]},
            **shared_dims(found))

    previous = None
    for call in calls(live):
        tiers = call.usage.get("cache_creation") or {}
        yield schema.fact(schema.CALL, dict(window), {
            schema.SPEND: usage.usage_spend(call.usage),
            "output_tokens": call.usage["output_tokens"],
            "cache_write_1h_tokens": tiers.get("ephemeral_1h_input_tokens", 0),
            "cache_write_5m_tokens": tiers.get("ephemeral_5m_input_tokens", 0),
            schema.CONTEXT_TOKENS: usage.usage_context(call.usage),
        }, locator(call.record))
        if previous is None:
            yield increment(usage.usage_context(call.usage), call.record,
                            evidence=fork_evidence(source.records), cause=schema.WINDOW_HEAD)
        else:
            yield from interval(previous, call)
        previous = call
