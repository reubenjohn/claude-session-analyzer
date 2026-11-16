"""Reading a screen in tests: its sections, headline, checks, the ``-v``
block and the commands it prints, each wrapped command rejoined
(``joined``). ``fixtures`` re-exports these; corpora are built there."""
import re

from sa import glossary, notes, schema

AVERAGE = glossary.marked(glossary.AVERAGE).replace("_", " ") + " "


def sections(out):
    """The report's blank-line-separated sections, each a list of lines:
    scope, answer, tables, key, checks."""
    return [s.splitlines() for s in out.rstrip("\n").split("\n\n")]


def headline(out):
    """The answer as one string: the total line, then the block's lines,
    padding collapsed, ``; ``-joined in reading order."""
    first, *rest = sections(out)[1]
    rest = [line for line in rest[:next((i for i, l in enumerate(rest) if l.startswith("→")), len(rest))]]
    return "; ".join([first] + [re.sub(r" +", " ", line.strip()) for line in rest if line.startswith("  ")])


def closing(out):
    """The checks' lines, last: the last section from its first ``✓`` (or
    ``✗``) line, the ways deeper above it in that section aside."""
    lines = sections(joined(out))[-1]
    return lines[next((i for i, l in enumerate(lines) if l.startswith(("✓", "✗"))), 0):]


def checks(out):
    """The checks, last: its lines joined, the identities then the gaps."""
    return "\n".join(closing(out))


def worked(out):
    """The ``-v`` worked equation under the checks line: the lines after
    it, its uncertainty lines (a cause's share, ``!``) aside, joined with a
    leading newline."""
    lines = closing(out)
    material = re.compile(r"^  (%s)\*?: " % "|".join(schema.CAUSES))  # a cause's share of the average
    return "".join("\n" + line for line in lines[1:] if not line.lstrip().startswith("!")
                   and glossary.PROG not in line and not material.match(line))


def also(out):
    """The dimensions the table pointer offers: its command's, then the
    gloss's (beside it or under it); none when there is no pointer."""
    lines = joined(out).splitlines()
    at = [i for i, l in enumerate(lines) if l.startswith(glossary.PROG) and " by " in l.split("  ")[0]]
    if not at:
        return []
    command, _, gloss = (lines[at[0]] + "  " + lines[at[0] + 1].strip()).partition("  ")
    rest = gloss.split(notes.ALSO, 1)[1].split("  ")[0].split(", ") if gloss.startswith(notes.ALSO) else []
    words = command.split()
    return [words[words.index("by") + 1]] + rest


def pointer_v(out):
    """The ``-v`` pointer: its command, then what it adds, in lines."""
    lines = joined(out).splitlines() + [""]
    at = next((i for i, l in enumerate(lines) if l.startswith(glossary.PROG) and " -v " in l + " "), None)
    under = lines[at + 1].strip() if at is not None and lines[at + 1].startswith("    how ") else ""
    return None if at is None else lines[at] + ("  " + under if under else "")


def average(out):
    return [line for line in sections(out)[1] if line.startswith(AVERAGE)]


def verbose(out):
    """The ``-v`` block's lines (``notes.HEAD`` opens each part), as printed."""
    lines = out.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(notes.HEAD)), len(lines))
    end = next((i for i in range(start, len(lines)) if not lines[i] or lines[i].startswith(("✓", "✗"))), len(lines))
    return lines[start:end]


def key(out):
    """The ``-v`` block's entries as (label, text), wrapped lines joined: a
    figure's ``name = working``, a marked word's ``word: meaning; surprise``,
    a catch-all's ``label (by DIM): cases``. Run with ``-v``."""
    entries = []
    for line in verbose(out):
        if line.startswith(notes.INDENT):
            entries[-1] += " " + line.strip()
        elif not line.startswith(notes.HEAD):
            entries.append(line.strip())
    return [(m.group(1), m.group(2)) for m in (re.match(r"^(.+?)(?:: | = )(.*)$", e) for e in entries)]


def joined(out):
    """The output with each command wrapped to the line budget (`` \\``,
    then its indented continuation) rejoined on one line, as a shell reads it;
    the read line's root, on a line of its own when long, and what the read
    set aside, on the next, rejoined too."""
    out = re.sub(r"^(read: .* under)\n  (.*)\n  (?=\d)", r"\1 \2; ", out, flags=re.M)  # what it set aside
    return re.sub(r" \\\n +", " ", re.sub(r"^(read: .* under)\n  ", r"\1 ", out, flags=re.M))


def listed(out):
    """``by change``/``by call``: each window's file as its header says it
    opens, the directory named once joined to its path (a long one rejoined
    from its broken lines)."""
    lines = out.splitlines()
    head = next(i for i, l in enumerate(lines) if re.match(r"^by (change|call), files in", l))
    under = lines[head].split(", files in", 1)[1].strip()
    if not under:  # a long root on its own lines
        under = lines[head + 1].strip()
        while under.endswith("/") and lines[head + 2].startswith("  ") and lines[head + 2].strip().endswith("/"):
            head += 1
            under += lines[head + 1].strip()
    files, path = [], ""
    for line in lines[head + 1:]:
        if path or re.match(r"^[^ ]\S*(\.jsonl|/)(  |$)", line):
            path += line.strip().split("  ")[0]
            if path.endswith(".jsonl"):
                files.append(under + path)
                path = ""
    return files


def hint(out):
    """The ``→ next:`` line, its command rejoined; None when there is none."""
    return next((l for l in joined(out).splitlines() if l.startswith("→ next: ")), None)
