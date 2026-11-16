"""Cut the deduplicated forest into context windows (D-CONTEXT-WINDOW).

A window starts at a session start, a subagent, a fork, a replay or a
compaction marker and fills until its file ends or the next compaction.
It is cut AFTER forest dedup, from each file's live records, and never by
marking a record duplicate, so ``Corpus.duplicate_records`` is the same
cut or uncut. A marker cuts only when a call follows it in its file: a
marker that ends its file starts none (``python3 -m sa.sweep``, LOCAL
SWEEP 2026-11-16T00:53Z: 4 of 9). No window spans files (same run: 0 of
618 files replay another after a live record), so a file holds one or
more windows and stays the unit of reading, dedup and locators.

Identity is ``schema.WindowKey`` (file, line of the start record: the
file's first record, or the marker), independent of dedup and
``--since``. The calls (``Call``, ``calls``) live here because a window is
a run of calls; ``walk`` books each window's increments.

A fork or replayed window copied its parent's context: ``inherits`` finds,
per file, the parent's branch call (the ``fork-context-ref``'s
``parentLastUuid``, else the last replayed record before the first live
call) and its occupancy (D-FORK-INHERITED; same run: the first call of
each of 10 inheriting windows is 1.006 to 1.034 times it). Nothing is re-minted: the inherited
breakdown is the parent window's facts up to that call (``query.through``).
"""
from collections import Counter
from typing import Dict, List, NamedTuple, Optional, Tuple

from . import schema, usage
from .corpus import Corpus, Record, SourceFile, is_marker, message_id
from .schema import Locator, WindowKey

Usages = Dict[str, List[dict]]  # ``Corpus.usages``: message.id -> every usage dict under it
FORK_REF = "fork-context-ref"


def _message(data: dict) -> dict:
    message = data.get("message")
    return message if isinstance(message, dict) else {}


class Call(NamedTuple):
    first: int      # index of the first constituent in the records walked
    record: Record  # the first constituent, which locates the call
    usage: dict     # max-merged over the constituents


def calls(records: List[Record], usages: Usages) -> List[Call]:
    """Usage-carrying calls in first-constituent order.

    Assistant records sharing a ``message.id`` are one call, merged by
    ``usage.max_merge_usage`` (its docstring has why a field-wise max) over
    every constituent the forest carries under that id (``usages``), so a
    split spread over a fork and its parent, or over a compaction marker,
    merges whole and is credited once, to the window of its first
    constituent. A record without ``message.id`` is a call by itself. A
    call carries usage iff it has occupancy or output: a ``<synthetic>``
    zero-usage record is not a call and does not advance the chain.
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


def first_value(records: List[Record], key: str) -> Optional[str]:
    for record in records:
        value = record.data.get(key)
        if value:
            return value
    return None


def replays(source: SourceFile) -> bool:
    """The file opens with records another file owns: it copied them."""
    for r in source.records:
        if r.data.get("uuid") or message_id(r.data):
            return r.duplicate
    return False


def marked_fork(source: SourceFile) -> bool:
    """The file says it is a fork, whether or not its parent was read: a
    ``fork-context-ref`` record, or an ``api-request`` record (no uuid, so
    never a duplicate) whose ``querySource`` is ``FORK_SOURCE``. LOCAL SWEEP
    2026-11-16T02:29Z: 10 of 10 fork windows marked (9 by the api-request,
    1 by the ref), each with its parent found (``sweep.fork_marks``)."""
    return any(r.data.get("type") == FORK_REF or (
        r.data.get("type") == "api-request" and r.data.get("querySource") == FORK_SOURCE)
        for r in source.records)


FORK_SOURCE = "agent:builtin:fork"


def file_start(source: SourceFile) -> str:
    """What began the file's first window (D-START-CAUSE): a fork (a
    ``marked_fork``, or a subagent replaying a prefix) beats
    subagent_start; a main file replaying a prefix is ``replayed``. A
    marked fork stays one with its parent missing; a replay is known only
    by its parent's records."""
    agent = first_value(source.live, "agentId")
    copied = replays(source)
    if marked_fork(source) or (copied and agent):
        return schema.FORK
    if copied:
        return schema.REPLAYED
    return schema.SUBAGENT_START if agent else schema.SESSION_START


class Window(NamedTuple):
    key: WindowKey
    start: str          # a ``schema.STARTS`` value
    calls: List[Call]   # its calls; ``first`` indexes the file's live records


def cut(source: SourceFile, usages: Usages) -> List[Window]:
    """The file's windows in order: one from its first record, one from each
    live marker a call follows; a window with no call is none. A call
    belongs to the window its first constituent falls in."""
    live = source.live
    found = calls(live, usages)
    if not found:
        return []
    marks = [i for i, r in enumerate(live) if is_marker(r.data) and found[-1].first > i]
    starts = [(-1, WindowKey(source.name, source.records[0].line), file_start(source))]
    starts += [(i, WindowKey(source.name, live[i].line), schema.COMPACTION) for i in marks]
    out = []
    for k, (at, key, start) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(live)
        mine = [c for c in found if at < c.first < end]
        if mine:
            out.append(Window(key, start, mine))
    return out


def compactions(loaded: Corpus) -> Counter:
    """Live markers by outcome: ``started`` a window (a call follows) or
    ``ended`` their file. Every one is unpriced: the summarising call is
    absent (same run: 0 of 24,261 api-request records)."""
    out = Counter()
    for source in loaded.files:
        found = calls(source.live, loaded.usages)
        for i, r in enumerate(source.live):
            if is_marker(r.data):
                out["started" if found and found[-1].first > i else "ended"] += 1
    return out


class Inherit(NamedTuple):
    mass: int            # the parent window's occupancy at the branch call
    parent: WindowKey
    branch: Locator      # the parent's branch call


def _owners(loaded: Corpus) -> Dict[Tuple[str, str], Tuple[SourceFile, Record]]:
    """Where each live uuid and message.id sits."""
    at: Dict[Tuple[str, str], Tuple[SourceFile, Record]] = {}
    for source in loaded.files:
        for r in source.live:
            for key in (("u", r.data.get("uuid")), ("m", message_id(r.data))):
                if key[1]:
                    at.setdefault(key, (source, r))
    return at


def _branch(source: SourceFile, owners) -> Optional[Tuple[SourceFile, Record]]:
    """The parent record the file branched from."""
    last = None
    for r in source.records:
        if r.data.get("type") == FORK_REF:
            return owners.get(("u", r.data.get("parentLastUuid")))
        if r.duplicate and (r.data.get("uuid") or message_id(r.data)):
            last = owners.get(("u", r.data.get("uuid"))) or owners.get(("m", message_id(r.data)))
        elif not r.duplicate and r.data.get("type") == "assistant":
            break
    return last


def inherits(loaded: Corpus, cuts: Dict[str, List[Window]]) -> Dict[str, Inherit]:
    """File name -> what its first window inherited, for every file whose
    first window is a fork or replay whose parent call is in the forest:
    the parent's last call at or before the branch record. A parent not
    read (``--since``) leaves the copy live, counted in full."""
    owners, out = _owners(loaded), {}
    for source in loaded.files:
        mine = cuts.get(source.name)
        if not mine or mine[0].start not in (schema.FORK, schema.REPLAYED):
            continue
        found = _branch(source, owners)
        if found is None or found[0].name == source.name:
            continue
        owner, record = found
        before = [(w, c) for w in cuts.get(owner.name, []) for c in w.calls
                  if c.record.line <= record.line]
        if before:
            window, call = before[-1]
            out[source.name] = Inherit(usage.usage_context(call.usage), window.key,
                                       Locator(owner.name, call.record.line, call.record.data.get("uuid")))
    return out
