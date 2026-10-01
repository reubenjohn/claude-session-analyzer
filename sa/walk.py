"""One file's records become facts.

A window is a file. Its ``call`` facts are the max-merged assistant messages
that carried usage; its ``increment`` facts book every change of context
occupancy from an empty window to the last call, so that per window
``sum(context_delta) == final occupancy`` by construction. What the
telescoping chain cannot check is whether one interval's mass went to the
right contributor; that is why only an interval with exactly one
token-relevant contributor is booked as exact and everything else is one
``ambiguous`` bucket with its reason, never a spread.

Records marked duplicate (replays owned by another file, by uuid or by the
call's message.id) mint no call, no contributor and no fact; the tool_use
join index spans every record so a tool_result whose tool_use was replayed
still resolves to its tool. A file whose first calls are replays books
``window_head`` at its first live call, the ruled inherited-context row.

Every figure below marked "local sweep 2026-10-01" is a line of
``scripts/local_sweep.py`` run that day over this machine's live corpus
(63 files, 55 windows, 1,597 calls, 1,542 intervals): a dated snapshot, not
reproducible elsewhere. The Phase 0 figures name their own population.
"""
from typing import Dict, Iterator, List, NamedTuple, Optional, Tuple

from . import heads, schema, usage
from .corpus import Corpus, Record, SourceFile, message_id
from .schema import Candidate, Fact, Locator

ToolUses = Dict[str, Tuple[str, dict]]
Usages = Dict[str, List[dict]]  # ``Corpus.usages``: message.id -> every usage dict under it


def _message(data: dict) -> dict:
    message = data.get("message")
    return message if isinstance(message, dict) else {}


def blocks(data: dict) -> List[dict]:
    content = _message(data).get("content")
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict)]


class Call(NamedTuple):
    first: int      # index of the first constituent in the records walked
    record: Record  # the first constituent, which locates the call
    usage: dict     # max-merged over the constituents


def calls(records: List[Record], usages: Usages) -> List[Call]:
    """Usage-carrying calls in first-constituent order.

    Assistant records sharing a ``message.id`` are one call, merged by
    ``usage.max_merge_usage`` (its docstring has why a field-wise max) over
    every constituent the forest carries under that id (``usages``), so a
    split spread over a fork and its parent merges whole and is credited
    once, to the owning file. A record without ``message.id`` is a call by
    itself. A call carries usage iff it has occupancy or output: a
    ``<synthetic>`` zero-usage record is not a call and does not advance
    the chain.
    """
    found, seen = [], set()
    for index, record in enumerate(records):
        if record.data.get("type") != "assistant":
            continue
        key = message_id(record.data)
        if key in seen:
            continue  # a later constituent of a call already found
        if key is None:
            merged = usage.max_merge_usage([_message(record.data).get("usage")])
        else:
            seen.add(key)
            merged = usage.max_merge_usage(usages[key])
        if usage.usage_context(merged) or merged.get("output_tokens"):
            found.append(Call(index, record, merged))
    return found


def tool_uses(records: List[Record]) -> ToolUses:
    """``tool_use.id -> (tool name, input)`` over the file. Every tool_result's
    ``tool_use_id`` resolves to an earlier record in its own file (59,740 of
    59,740 in the Phase 0 sweep), so this is the whole join."""
    index = {}
    for record in records:
        if record.data.get("type") == "assistant":
            for block in blocks(record.data):
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
        """What an exact increment books for it: the dimensions that are set."""
        named = {schema.CAUSE_DIM: self.cause, schema.TOOL_DIM: self.tool, schema.HEAD_DIM: self.head}
        return {dim: value for dim, value in named.items() if value is not None}


def contributors(records: List[Record], uses: ToolUses) -> Iterator[Contributor]:
    """The token-relevant records among ``records``: one contributor per
    tool_result block of a user record, and every other user record as user
    text. A record batching several results names several tools, so booking
    it to its first block would be exact to one tool by silent choice; none
    is observed (local sweep 2026-10-01: 0 of 2,420 tool_result records carry
    more than one block), which is why per-block is the fail-closed reading.

    Attachments, system records and bookkeeping types are not contributors.
    Measured over 51,960 intervals (2026-07-28): counting them collapses the
    exact rate from 96.92% to below 1% on versions that emit a per-turn
    attachment, and exact intervals that also hold such records show a lower
    mean remainder, not a higher one.
    """
    for record in records:
        if record.data.get("type") != "user":
            continue
        results = [block for block in blocks(record.data) if block.get("type") == "tool_result"]
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
    value, not an absence. Local sweep 2026-10-01: 183 of 344 multi_contributor
    intervals (1,253,677 of 1,928,743 context tokens) share one tool, and 93
    of them (770,101 tokens) share the head as well."""
    out = {}
    for dim in (schema.TOOL_DIM, schema.HEAD_DIM):
        values = {c.dims.get(dim) for c in found}
        if len(values) != 1 or None in values:
            return out
        out[dim] = values.pop()
    return out


def fork_evidence(records: List[Record]) -> dict:
    """A forked agent file opens with a ``fork-context-ref`` naming the
    parent; its first call's occupancy is inherited, not booted, and the
    ids are kept so a later build can stitch windows without a new schema."""
    for record in records:
        if record.data.get("type") == "fork-context-ref":
            return {schema.PARENT_SESSION: record.data.get("parentSessionId"),
                    schema.PARENT_LAST_UUID: record.data.get("parentLastUuid")}
    return {}


def first_value(records: List[Record], key: str) -> Optional[str]:
    for record in records:
        value = record.data.get(key)
        if value:
            return value
    return None


def walk(source: SourceFile, usages: Usages) -> Iterator[Fact]:
    """Facts of one window in file order, each call followed by the
    increments it closes; ``usages`` is the forest's, so a split call
    merges whole wherever its constituents landed.

    An interval's contributors are the user records strictly between the
    previous call's FIRST constituent and the current call's first. A split
    call's constituents interleave with their results (parallel tool use:
    constituent, result, constituent, result, next call; local sweep
    2026-10-01: 136 user records sit inside 86 of 1,597 calls' spans, counted
    by ``scripts/local_sweep.py``), so slicing from the previous call's last
    constituent hides the earlier result and books a two-contributor
    interval as exact.
    """
    uses = tool_uses(source.records)
    live = [record for record in source.records if not record.duplicate]
    # The window dimensions come from the live records, the ones that mint
    # the facts: a replayed prefix owned by another file names that file's
    # window (local sweep 2026-10-01: 0 of 63 files whose first record and
    # first live record disagree on either key).
    window = {schema.PROJECT_DIM: source.project,
              schema.SESSION_DIM: first_value(live, "sessionId"),
              schema.AGENT_DIM: first_value(live, "agentId"),  # None: a main window
              schema.WINDOW_DIM: source.name}
    window = {k: v for k, v in window.items() if v is not None}

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
            evidence={schema.CANDIDATES: [Candidate(locator(c.record), c.dims) for c in found]},
            **shared_dims(found))

    previous = None
    for call in calls(live, usages):
        yield schema.fact(schema.CALL, dict(window), {
            name: spec.read(call.usage) for name, spec in schema.METRICS.items()
            if spec.carrier == schema.CALL}, locator(call.record))
        if previous is None:
            yield increment(usage.usage_context(call.usage), call.record,
                            evidence=fork_evidence(source.records), cause=schema.WINDOW_HEAD)
        else:
            yield from interval(previous, call)
        previous = call


def forest(loaded: Corpus) -> List[Fact]:
    """Every window's facts, files in owner order: the one population the
    views, the sweep and the tests select from."""
    return [f for source in loaded.files for f in walk(source, loaded.usages)]
