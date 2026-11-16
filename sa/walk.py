"""Each window's records become facts.

A window is one context window, cut by ``windows`` (a file holds one or
more). Its ``call`` facts are the max-merged assistant messages that
carried usage; its ``increment`` facts book every change of context
occupancy from an empty window to the last call, so that per window
``sum(context_delta) == final occupancy`` by construction. What the
telescoping chain cannot check is whether one interval's mass went to the
right contributor; that is why only an interval with exactly one
token-relevant contributor is booked as exact and everything else is one
``ambiguous`` bucket with its reason, never a spread.

Records marked duplicate (replays owned by another file, by uuid or by the
call's message.id) mint no call, no contributor and no fact; the tool_use
join index spans every record so a tool_result whose tool_use was replayed
still resolves to its tool. A window's first call books its head: for a
fork or replayed window whose parent is in the forest, ``inherited`` (the
parent window's occupancy at the branch call, one increment, its evidence
the parent window and that call) and ``starting_context``, the remainder; for
any other window, ``starting_context`` alone (D-FORK-INHERITED, D-NO-START-SPLIT).

Every figure below marked "local sweep 2026-10-01T11:50Z" is a line of
``python3 -m sa.sweep`` run at that minute over this machine's live
corpus (67 files, 59 windows, 1,672 calls, 1,613 intervals): one snapshot
of a corpus that grows hourly, not reproducible elsewhere. The Phase 0
figures name their own population.
"""
from typing import Dict, Iterator, List, NamedTuple, Optional, Tuple

from . import heads, schema, usage, windows as windows_module
from .corpus import Corpus, Record, SourceFile
from .schema import Candidate, Fact, Locator
from .windows import Call, Usages, Window, calls, first_value, _message  # noqa: F401 (re-exported)

ToolUses = Dict[str, Tuple[str, dict]]


def blocks(data: dict) -> List[dict]:
    content = _message(data).get("content")
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict)]


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
        named = {schema.CAUSE_DIM: self.cause, schema.TOOL_DIM: self.tool, schema.COMMAND_DIM: self.head}
        return {dim: value for dim, value in named.items() if value is not None}


def contributors(records: List[Record], uses: ToolUses) -> Iterator[Contributor]:
    """The token-relevant records among ``records``: one contributor per
    tool_result block of a user record, and every other user record as user
    text. A record batching several results names several tools, so booking
    it to its first block would be exact to one tool by silent choice; none
    is observed (local sweep 2026-10-01T11:50Z: 0 of 2,615 tool_result
    records carry more than one block), which is why per-block is the
    fail-closed reading.

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
    value, not an absence. Local sweep 2026-10-01T11:50Z: 203 of 375
    ``several`` intervals (1,567,663 of 2,284,391 context tokens)
    share one tool, and 104 of them (937,714 tokens) share the head as
    well."""
    out = {}
    for dim in (schema.TOOL_DIM, schema.COMMAND_DIM):
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


def walk(source: SourceFile, usages: Usages, cut: Optional[List[Window]] = None,
         inherit: Optional[windows_module.Inherit] = None) -> Iterator[Fact]:
    """Facts of one file's windows in file order, each call followed by the
    increments it closes; ``usages`` is the forest's, so a split call
    merges whole wherever its constituents landed. ``cut`` is the file's
    windows (``windows.cut`` when omitted); ``inherit``, what its first
    window copied from its parent (``windows.inherits``).

    An interval's contributors are the user records strictly between the
    previous call's FIRST constituent and the current call's first. A split
    call's constituents interleave with their results (parallel tool use:
    constituent, result, constituent, result, next call; local sweep
    2026-10-01T11:50Z: 143 user records sit inside 89 of 1,672 calls'
    spans), so slicing from the previous call's last constituent hides the
    earlier result and books a two-contributor interval as exact.
    """
    uses = tool_uses(source.records)
    live = source.live
    # The file's dimensions come from the live records, the ones that mint
    # the facts: a replayed prefix owned by another file names that file's
    # window (local sweep 2026-10-01T11:50Z: 0 of 67 files whose first
    # record and first live record disagree on either key).
    named = {schema.PROJECT_DIM: source.project,
             schema.SESSION_DIM: first_value(live, "sessionId"),
             schema.SUBAGENT_DIM: first_value(live, "agentId")}  # None: a main window
    named = {k: v for k, v in named.items() if v is not None}
    for k, win in enumerate(windows_module.cut(source, usages) if cut is None else cut):
        dims = dict(named)
        dims.update({schema.WINDOW_DIM: schema.window_value(win.key), schema.STARTED_BY_DIM: win.start,
                     schema.PEAK_DIM: schema.band(max(usage.usage_context(c.usage) for c in win.calls))})
        yield from _window(source, live, uses, win, dims, inherit if k == 0 else None)


def _window(source: SourceFile, live: List[Record], uses: ToolUses, win: Window, window: dict,
            inherit: Optional[windows_module.Inherit]) -> Iterator[Fact]:
    def locator(record: Record) -> Locator:
        return Locator(source.name, record.line, record.data.get("uuid"))

    def increment(delta: int, record: Record, evidence: Optional[dict] = None,
                  **dims: Optional[str]) -> Fact:
        all_dims = dict(window)
        all_dims.update((k, v) for k, v in dims.items() if v is not None)
        return schema.fact(schema.INCREMENT, all_dims, {schema.CONTEXT_DELTA: delta},
                           locator(record), evidence, win.key)

    def interval(previous: Call, current: Call) -> Iterator[Fact]:
        delta = usage.context_delta(previous.usage, current.usage)
        if delta < 0:
            yield increment(delta, current.record, cause=schema.SHRINK)
            return
        fed_forward = previous.usage["output_tokens"]
        if delta < fed_forward:
            yield increment(delta, current.record, cause=schema.AMBIGUOUS,
                            reason=schema.LESS_THAN_REPLY)
            return
        yield increment(fed_forward, previous.record, cause=schema.REPLIES)
        remainder = delta - fed_forward
        found = list(contributors(live[previous.first + 1:current.first], uses))
        if len(found) == 1:
            yield increment(remainder, found[0].record, **found[0].dims)
            return
        yield increment(
            remainder, current.record, cause=schema.AMBIGUOUS,
            reason=schema.SEVERAL if found else schema.UNEXPLAINED,
            evidence={schema.CANDIDATES: [Candidate(locator(c.record), c.dims) for c in found]},
            **shared_dims(found))

    previous = None
    for call in win.calls:
        yield schema.fact(schema.CALL, dict(window), {
            name: spec.read(call.usage) for name, spec in schema.METRICS.items()
            if spec.carrier == schema.CALL}, locator(call.record), window=win.key)
        if previous is None:
            head = usage.usage_context(call.usage)
            if inherit is not None:
                head -= inherit.mass  # unclamped: the remainder is the window's own start
                yield increment(inherit.mass, call.record, cause=schema.INHERITED, evidence={
                    schema.PARENT_WINDOW: inherit.parent, schema.BRANCH_CALL: inherit.branch})
            first = win.start != schema.COMPACTION
            yield increment(head, call.record, evidence=fork_evidence(source.records) if first else None,
                            cause=schema.STARTING_CONTEXT)
        else:
            yield from interval(previous, call)
        previous = call


def forest(loaded: Corpus) -> List[Fact]:
    """Every window's facts, files in owner order: the one population the
    views, the sweep and the tests select from. The files are cut first,
    so a fork finds its parent's window and branch call."""
    cuts = {source.name: windows_module.cut(source, loaded.usages) for source in loaded.files}
    inherited = windows_module.inherits(loaded, cuts)
    return [f for source in loaded.files
            for f in walk(source, loaded.usages, cuts[source.name], inherited.get(source.name))]
