"""Read the transcript forest: every ``*.jsonl`` under the corpus root.

Layout: ``<root>/<project>/<session>.jsonl`` for a main session and
``<root>/<project>/<session>/subagents/agent-*.jsonl`` for its agents. The
project is the first path component; it is the only identity taken from a
path. Session and agent come from the records (1,588 of 1,845 measured files
have a non-UUID filename stem and carry the parent's sessionId).

Identity is the record ``uuid``, deduplicated across the whole forest with
the first occurrence winning in sorted-path order: a resumed or forked
session replays its parent's records (2,767 of 205,003 measured uuids appear
in more than one file; per-file reading inflates totals by 94%). Dedup is
never by content, because a sibling fork re-bills identical text under new
uuids and that re-billing is real. Records without a uuid are kept; they are
bookkeeping and carry no tokens.
"""
import json
from pathlib import Path
from typing import Callable, Iterator, List, NamedTuple, Optional, Tuple


def default_root():
    # type: () -> Path
    return Path.home() / ".claude" / "projects"


class Record(NamedTuple):
    line: int   # physical line number, 1-based, counted before any skipping
    data: dict


class SourceFile(NamedTuple):
    path: Path
    project: str
    records: List[Record]


class Corpus(NamedTuple):
    files: List[SourceFile]
    skipped_lines: int        # blank, unparseable, or not a JSON object
    duplicate_records: int    # dropped because their uuid was already seen


def find_files(root, keep=None):
    # type: (Path, Optional[Callable[[Path, str], bool]]) -> Iterator[Tuple[Path, str]]
    """``(path, project)`` for each transcript file, in sorted-path order.

    ``keep(path, project)`` narrows the population before reading; dedup then
    runs over the kept files only, so the population line names exactly the
    files whose records were counted.
    """
    for path in sorted(root.rglob("*.jsonl"), key=str):
        project = path.relative_to(root).parts[0]
        if keep is None or keep(path, project):
            yield path, project


def read_lines(path):
    # type: (Path) -> Iterator[Record]
    """Parse one file line by line, keeping the physical line number.

    Lines that are blank, unparseable, or parse to a non-object are yielded
    with ``data=None`` so the caller can count them; the line number of every
    later record is unaffected (2 unparseable lines exist in a healthy
    measured corpus).
    """
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            try:
                data = json.loads(line)
            except ValueError:
                data = None
            yield Record(line_no, data if isinstance(data, dict) else None)


def load(root, keep=None):
    # type: (Path, Optional[Callable[[Path, str], bool]]) -> Corpus
    """Every kept file's records after forest-wide uuid dedup."""
    seen = set()
    files = []
    skipped = duplicates = 0
    for path, project in find_files(root, keep):
        records = []
        for record in read_lines(path):
            if record.data is None:
                skipped += 1
                continue
            uuid = record.data.get("uuid")
            if uuid:
                if uuid in seen:
                    duplicates += 1
                    continue
                seen.add(uuid)
            records.append(record)
        files.append(SourceFile(path, project, records))
    return Corpus(files, skipped, duplicates)
