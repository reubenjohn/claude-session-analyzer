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
"""
from typing import Dict, Iterator, List, NamedTuple, Optional, Tuple

from . import heads, schema, usage
from .corpus import Record, SourceFile
from .schema import Fact, Locator


def _message(data):
    # type: (dict) -> dict
    message = data.get("message")
    return message if isinstance(message, dict) else {}


def _blocks(data):
    # type: (dict) -> List[dict]
    content = _message(data).get("content")
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict)]


class Call(NamedTuple):
    first: int      # index of the first constituent in the records walked
    record: Record  # the first constituent, which locates the call
    usage: dict     # max-merged over the constituents


def calls(records):
    # type: (List[Record]) -> List[Call]
    """Usage-carrying calls in first-constituent order.

    Assistant records sharing a ``message.id`` are one call (78.05% of 53,855
    measured ids are split over several records, and 73% of the split ones
    disagree on output_tokens, which is why the merge is a field-wise max).
    A record without ``message.id`` is a call by itself. A call carries usage
    iff it has occupancy or output: a ``<synthetic>`` zero-usage record is
    not a call and does not advance the chain.
    """
    groups = {}  # type: Dict[object, List[int]]
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


def tool_uses(records):
    # type: (List[Record]) -> Dict[str, Tuple[str, dict]]
    """``tool_use.id -> (tool name, input)`` over the file. Every measured
    tool_result's ``tool_use_id`` resolves to an earlier record in its own
    file (59,740 of 59,740), so this is the whole join."""
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


def contributors(records, uses):
    # type: (List[Record], Dict[str, Tuple[str, dict]]) -> Iterator[Contributor]
    """The token-relevant records among ``records``: user records carrying a
    tool_result, named by their first such block (0 of 296 block-content user
    records on the 24-file local corpus carry more than one), and all other
    user records as user text.

    Attachments, system records and bookkeeping types are not contributors.
    Measured: counting them collapses the exact rate from 96.92% to below
    1% on versions that emit a per-turn attachment, and exact intervals that
    also hold such records show a lower mean remainder, not a higher one.
    """
    for record in records:
        if record.data.get("type") != "user":
            continue
        for block in _blocks(record.data):
            if block.get("type") == "tool_result":
                tool, tool_input = uses.get(block.get("tool_use_id"), (None, None))
                yield Contributor(record, schema.TOOL_RESULT, tool,
                                  heads.head_of(tool, tool_input))
                break
        else:
            yield Contributor(record, schema.USER_TEXT, None, None)


def fork_evidence(records):
    # type: (List[Record]) -> dict
    """A forked agent file opens with a ``fork-context-ref`` naming the
    parent; its first call's occupancy is inherited, not booted, and the
    ids are kept so a later build can stitch windows without a new schema."""
    for record in records:
        if record.data.get("type") == "fork-context-ref":
            return {"parent_session": record.data.get("parentSessionId"),
                    "parent_last_uuid": record.data.get("parentLastUuid")}
    return {}


def _first_value(records, key):
    # type: (List[Record], str) -> Optional[str]
    for record in records:
        value = record.data.get(key)
        if value:
            return value
    return None


def walk(source):
    # type: (SourceFile) -> Iterator[Fact]
    """Facts of one window in file order, each call followed by the
    increments it closes.

    An interval's contributors are the user records strictly between the
    previous call's FIRST constituent and the current call's first. A split
    call's constituents interleave with their results (parallel tool use:
    constituent, result, constituent, result, next call; 54 user records sit
    inside 32 of 362 calls' spans on the 27-file local corpus, 2026-09-30),
    so slicing from the previous call's last constituent hides the earlier
    result and books a two-contributor interval as exact.
    """
    path = str(source.path)
    window = {
        "project": source.project,
        "session": _first_value(source.records, "sessionId"),
        "agent": _first_value(source.records, "agentId") or "main",
    }
    uses = tool_uses(source.records)
    live = [record for record in source.records if not record.duplicate]

    def locator(record):
        # type: (Record) -> Locator
        return Locator(path, record.line, record.data.get("uuid"))

    def increment(cause, delta, record, evidence=None, **dims):
        # type: (str, int, Record, Optional[dict], **object) -> Fact
        all_dims = dict(window, cause=cause)
        all_dims.update((k, v) for k, v in dims.items() if v is not None)
        return schema.fact(schema.INCREMENT, all_dims, {"context_delta": delta},
                           locator(record), evidence)

    def interval(previous, current):
        # type: (Call, Call) -> Iterator[Fact]
        delta = usage.context_delta(previous.usage, current.usage)
        if delta < 0:
            yield increment(schema.SHRINK, delta, current.record)
            return
        fed_forward = previous.usage["output_tokens"]
        if delta < fed_forward:
            yield increment(schema.AMBIGUOUS, delta, current.record,
                            reason=schema.NEGATIVE_REMAINDER)
            return
        yield increment(schema.FEED_FORWARD, fed_forward, previous.record)
        remainder = delta - fed_forward
        found = list(contributors(live[previous.first + 1:current.first], uses))
        if len(found) == 1:
            one = found[0]
            yield increment(one.cause, remainder, one.record, tool=one.tool, head=one.head)
            return
        yield increment(
            schema.AMBIGUOUS, remainder, current.record,
            reason=schema.MULTI_CONTRIBUTOR if found else schema.NO_CONTRIBUTOR,
            candidate_count=len(found),
            evidence={"candidates": [c.record.data.get("uuid") for c in found]})

    previous = None
    for call in calls(live):
        tiers = call.usage.get("cache_creation") or {}
        yield schema.fact(schema.CALL, dict(window), {
            "spend": usage.usage_spend(call.usage),
            "output_tokens": call.usage["output_tokens"],
            "cache_write_1h_tokens": tiers.get("ephemeral_1h_input_tokens", 0),
            "cache_write_5m_tokens": tiers.get("ephemeral_5m_input_tokens", 0),
            "context_tokens": usage.usage_context(call.usage),
        }, locator(call.record))
        if previous is None:
            yield increment(schema.WINDOW_HEAD, usage.usage_context(call.usage),
                            call.record, evidence=fork_evidence(source.records))
        else:
            yield from interval(previous, call)
        previous = call
