"""Read the transcript forest: every ``*.jsonl`` under the corpus root.

Layout: ``<root>/<project>/<session>.jsonl`` for a main session and
``<root>/<project>/<session>/subagents/agent-*.jsonl`` for its agents. The
project is the first path component; it is the only identity taken from a
path. Session and agent come from the records: in the Phase 0 sweep (1,845
files, 2026-07-28, ``references/PHASE0_MEASUREMENT.md``; the population of
every Phase 0 figure in this package) 1,588 files have a non-UUID filename
stem and carry the parent's sessionId.

Identity is the record ``uuid``, deduplicated across the whole forest: a
resumed or forked session replays its parent's records (2,767 of 205,003
uuids in the Phase 0 sweep appear in more than one file; per-file reading
inflates totals by 94%). A call's identity is its ``message.id``, deduplicated
ACROSS files only (D-MESSAGE-ID-DEDUP): a fork re-mints its parent's last
call under a new uuid (local sweep 2026-10-01T11:50Z, one minute's snapshot
of this machine's corpus by ``python3 -m sa.sweep``, 67 files and 1,672
live calls: 1 re-mint, 15,240 spend-equivalents, one phantom call and
interval), while records sharing an id within one file are the split
constituents of one call. A window is a file, never a ``parentUuid``
chain: no link names a uuid in another file (same sweep,
``sweep.cross_file_parents``: 0 of 12,557), so a continuation is joined by
its replayed records, not by its parent.
Files are read in owner order, so that the earliest-starting,
longest-running copy of a window owns the records it shares with any other
copy, and a replayed record in any later copy is MARKED duplicate rather
than dropped: the walk still needs it to resolve a tool_result whose
tool_use was replayed, and a split call's usage is max-merged over every
copy wherever it landed (``Corpus.usages``). Dedup is never by content,
because a sibling fork re-bills identical text under new uuids and that
re-billing is real. Records without a uuid are kept; they are bookkeeping
and carry no tokens.
"""
import json
import time
from pathlib import Path
from typing import Dict, Iterator, List, NamedTuple, Optional, Tuple

DAY = 86400.0


def default_root() -> Path:
    return Path.home() / ".claude" / "projects"


class Record(NamedTuple):
    line: int        # physical line number, 1-based, counted before any skipping
    data: dict
    duplicate: bool  # its uuid or its call's message.id was already seen in an earlier-owned file


class SourceFile(NamedTuple):
    path: Path
    name: str        # path relative to the root; what locators and output carry
    project: str
    records: List[Record]

    @property
    def live(self) -> List[Record]:
        """The records this file owns: the ones that mint its facts."""
        return [r for r in self.records if not r.duplicate]


class Corpus(NamedTuple):
    root: Path
    since_days: Optional[float]  # the files were kept by modification time; None: every file
    files: List[SourceFile]
    usages: Dict[str, List[dict]]  # message.id -> every usage dict the forest carries under it
    skipped_lines: int        # blank, unparseable, or not a JSON object
    duplicate_records: int    # marked because their uuid or message.id was already seen


def message_id(data: dict) -> Optional[str]:
    """The ``message.id`` of an assistant record; None for any other record
    or an id-less one, which is never a key."""
    message = data.get("message")
    if data.get("type") != "assistant" or not isinstance(message, dict):
        return None
    return message.get("id")


def find_files(root: Path, since_days: Optional[float] = None) -> Iterator[Tuple[Path, str, str]]:
    """``(path, root-relative name, project)`` for each transcript file, in
    sorted-path order; only those modified within ``since_days`` when it is
    given. The population is narrowed before reading, so dedup runs over the
    kept files only and the read line names exactly the files whose records
    were counted.
    """
    cutoff = None if since_days is None else time.time() - since_days * DAY
    for path in sorted(root.rglob("*.jsonl"), key=str):
        relative = path.relative_to(root)
        if cutoff is None or path.stat().st_mtime >= cutoff:
            yield path, relative.as_posix(), relative.parts[0]


def read_lines(path: Path) -> Iterator[Tuple[int, Optional[dict]]]:
    """``(physical line number, parsed object)`` for every line of one file.

    Lines that are blank, unparseable, or parse to a non-object yield
    ``None`` so the caller can count them; the line number of every later
    record is unaffected (the Phase 0 sweep had 2 unparseable lines).
    """
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            try:
                data = json.loads(line)
            except ValueError:
                data = None
            yield line_no, data if isinstance(data, dict) else None


class _File(NamedTuple):
    """One file's parsed lines and its span, before dedup."""
    first: str       # first and last record timestamps; "" when the file has none
    last: str
    path: Path
    name: str
    project: str
    lines: List[Tuple[int, dict]]


def _span(lines: List[Tuple[int, dict]]) -> Tuple[str, str]:
    """First and last record timestamps of a file (ISO strings order as text)."""
    stamps = [data.get("timestamp") for _, data in lines if data.get("timestamp")]
    return (stamps[0], stamps[-1]) if stamps else ("", "")


def load(root: Path, since_days: Optional[float] = None) -> Corpus:
    """Every file's records (those modified within ``since_days``, when
    given), in owner order, with replays marked.

    Owner order is (first record timestamp ascending, last record timestamp
    DESCENDING, path): the earliest-starting, longest-running copy of a
    window comes first and so owns every record it shares, by uuid and by
    message.id alike. A file with no timestamps at all has no claim to being
    earliest, so it sorts after every stamped file and owns only what no
    stamped copy carries. Two stable sorts implement the descending middle
    key.
    """
    read = []
    skipped = 0
    for path, name, project in find_files(root, since_days):
        lines = []
        for line_no, data in read_lines(path):
            if data is None:
                skipped += 1
            else:
                lines.append((line_no, data))
        read.append(_File(*_span(lines), path, name, project, lines))
    read.sort(key=lambda f: f.last, reverse=True)
    read.sort(key=lambda f: (f.first == "", f.first))

    usages: Dict[str, List[dict]] = {}
    for f in read:
        for _, data in f.lines:
            call = message_id(data)
            if call is not None:
                usages.setdefault(call, []).append(data["message"].get("usage"))

    seen = set()
    owner: Dict[str, str] = {}  # message.id -> the file that first carried it
    files = []
    duplicates = 0
    for f in read:
        records = []
        for line_no, data in f.lines:
            uuid = data.get("uuid")
            call = message_id(data)
            if call is not None:
                owner.setdefault(call, f.name)
            duplicate = (bool(uuid) and uuid in seen) or (call is not None and owner[call] != f.name)
            duplicates += duplicate
            if uuid:
                seen.add(uuid)
            records.append(Record(line_no, data, duplicate))
        files.append(SourceFile(f.path, f.name, f.project, records))
    return Corpus(root, since_days, files, usages, skipped, duplicates)
