"""The UX-pass probe (``references/UX_FEEDBACK.md`` track B): what the
records say about compaction, window starts, fork prefixes and the content
of a window's head, measured with the parser itself (``corpus``, ``walk``),
never a copy of it. A measuring module, not engine: nothing here changes a
fact the CLI books. ``python3 -m sa.probe_ux`` runs it over the live corpus
under ``~/.claude/projects`` and stamps the minute on the first line, so
``references/PROPOSAL_UX_MODEL.md`` can cite it by date. Aggregate counts
only: no transcript text, no ids, no paths.

One section per question of the proposal: ``compaction`` and ``segmented``
(the reconciliation with each window cut at its markers) in
``probe_compaction``; ``triggers``, ``inherited`` (fork prefixes against
their parent) and ``head_content`` in ``probe_windows``.
"""
import datetime
from typing import List

from . import walk
from .corpus import Corpus, default_root, load
from .probe_compaction import compaction, fmt, segmented
from .probe_windows import head_content, inherited, triggers


def report(loaded: Corpus) -> List[str]:
    facts = walk.forest(loaded)
    sections = [("1 compaction", compaction(loaded)), ("2 segmented", segmented(loaded, facts)),
                ("3 triggers", triggers(loaded)), ("4 inherited", inherited(loaded, facts)),
                ("5 head content", head_content(loaded))]
    return ["[%s] %s" % (name, line) for name, lines in sections for line in lines]


if __name__ == "__main__":
    loaded = load(default_root())
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    print("UX PROBE %s: %s files" % (now, fmt(len(loaded.files))))
    print("\n".join(report(loaded)))
