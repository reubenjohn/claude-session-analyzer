"""Read the transcript forest: every ``*.jsonl`` under the corpus root.

Layout: ``<root>/<project>/<session>.jsonl`` for a main session and
``<root>/<project>/<session>/subagents/agent-*.jsonl`` for its agents. The
project is the first path component; it is the only identity taken from a
path. Session and agent come from the records: in the Phase 0 sweep (1,845
files, 2026-07-28, ``references/PHASE0_MEASUREMENT.md``; the population of
every file-count figure in this package) 1,588 files have a non-UUID
filename stem and carry the parent's sessionId.

Identity is the record ``uuid``, deduplicated across the whole forest: a
resumed or forked session replays its parent's records (2,767 of 205,003
uuids in the Phase 0 sweep appear in more than one file; per-file reading
inflates totals by 94%). A call's identity is its ``message.id``, deduplicated
ACROSS files only (D-MESSAGE-ID-DEDUP): a fork re-mints its parent's last
call under a new uuid (local corpus, 2026-10-01: 1 of ~888 live calls,
15,240 spend-equivalents, one phantom call and interval), while records
sharing an id within one file are the split constituents of one call.
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
from pathlib import Path
from typing import Callable, Dict, Iterator, List, NamedTuple, Optional, Tuple

Keep = Callable[[Path], bool]


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


class Corpus(NamedTuple):
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


def find_files(root: Path, keep: Optional[Keep] = None) -> Iterator[Tuple[Path, str, str]]:
    """``(path, root-relative name, project)`` for each transcript file, in
    sorted-path order.

    ``keep(path)`` narrows the population before reading; dedup then
    runs over the kept files only, so the population line names exactly the
    files whose records were counted.
    """
    for path in sorted(root.rglob("*.jsonl"), key=str):
        relative = path.relative_to(root)
        if keep is None or keep(path):
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


def _span(lines: List[Tuple[int, dict]]) -> Tuple[str, str]:
    """First and last record timestamps of a file (ISO strings order as text)."""
    stamps = [data.get("timestamp") for _, data in lines if data.get("timestamp")]
    return (stamps[0], stamps[-1]) if stamps else ("", "")


def load(root: Path, keep: Optional[Keep] = None) -> Corpus:
    """Every kept file's records, in owner order, with replays marked.

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
    for path, name, project in find_files(root, keep):
        lines = []
        for line_no, data in read_lines(path):
            if data is None:
                skipped += 1
            else:
                lines.append((line_no, data))
        read.append((_span(lines), path, name, project, lines))
    read.sort(key=lambda entry: entry[0][1], reverse=True)
    read.sort(key=lambda entry: (entry[0][0] == "", entry[0][0]))

    usages: Dict[str, List[dict]] = {}
    for *_, lines in read:
        for _, data in lines:
            call = message_id(data)
            if call is not None:
                usages.setdefault(call, []).append(data["message"].get("usage"))

    seen = set()
    owner: Dict[str, str] = {}  # message.id -> the file that first carried it
    files = []
    duplicates = 0
    for _, path, name, project, lines in read:
        records = []
        for line_no, data in lines:
            uuid = data.get("uuid")
            call = message_id(data)
            if call is not None:
                owner.setdefault(call, name)
            duplicate = (bool(uuid) and uuid in seen) or (call is not None and owner[call] != name)
            duplicates += duplicate
            if uuid:
                seen.add(uuid)
            records.append(Record(line_no, data, duplicate))
        files.append(SourceFile(path, name, project, records))
    return Corpus(files, usages, skipped, duplicates)
