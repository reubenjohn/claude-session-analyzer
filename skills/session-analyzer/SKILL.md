---
name: session-analyzer
description: Measures whether context is hurting a Claude Code model (context rot), what fills it, and what it cost, from the local transcripts; use when the user asks "where is my context going", "is my context too big", "what did this session cost", "which subagent or tool was expensive".
---

# session-analyzer

Two questions, two commands, from the JSONL transcripts under
`~/.claude/projects`: were inference free, is context hurting the model
(every call reasons over its whole window), what fills it, how to fix
it; and what did it cost.

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m sa context   # is context a problem, what fills it
cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m sa spend     # what did it cost
```

Pin, then drill:

| Flag | Meaning |
|---|---|
| `--since 30d` | files modified in the last N days (default 7d; `all`: every file) |
| `--where project=` / `session=` / `subagent=` / `window=` / `started_by=` / `peak=` | project as printed (`~-work-app`), sessionId, subagent as printed or its id, a window's hex (`--by window`), what began it, or the band of its largest call (`0-50K`, `50-100K`, `100-200K`, `200K+`); keeps whole windows |
| `--where DIM=VALUE` | a pin, repeatable, exact; also cause, tool, command, reason (a drill) |
| `--by DIM` | one dimension's table |
| `--by fact` | one change (spend: call) per row: `<metric>  file:line  uuid  dims`, evidence under |
| `--limit N` | rows per table (5); the rest fold to `+k more rows`, never causes, `unassigned` or negative (shrink) rows |

## What each command answers

**`context`** books every change of a window's context (a *change*;
the metric prints as `context tokens`) with one `cause`:
`starting_context` (the first call's context, less what a fork or replay
`inherited`), `replies` (Claude's replies, tool-call inputs included),
`tool_result`, `user_text`, `ambiguous` (no one contributor; `reason`:
`several`, `less_than_reply`, `unexplained`) and `shrink` (a window that
got smaller, signed). Default tables: cause, tool, command, subagent,
peak (with windows and calls), session, project.

**`spend`** sums each call's price-weighted input tokens: uncached
input, cache writes (1h 2.0x, 5m 1.25x), cache reads 0.1x; output
apart. Default tables: project, session, subagent (`unassigned`: the
main windows). Context shares are not cost shares.

Whatever `--by` shows, the `context` headline states one total, then a
block (shares of the mass added, shrink out): the starting context as a
sum by `started_by` (what was there at window start, never a window
size), then `growth`: the top tool `→` its largest command, then a
larger `top command`. `spend` names the largest subagent. A
`--where` pin omits the default tables and levers it implies (a command
its tool, a window its subagent, session, project). A drill's headline
names its pins and the windows hit (`… in 1 of 2 windows`); then
`average context per call* N tokens, over C calls in W windows`: what a
call held, over the whole windows in view, never summed. A fork whose
parent file is missing counts its copy as its own; the scope says how many.

## The path: is it a problem -> what -> where -> what to fix

```bash
python3 -m sa context                                    # average, by peak
python3 -m sa context --where peak=200K+                 # what fills them
python3 -m sa context --where peak=200K+ --by session    # where
python3 -m sa context --where peak=200K+ --where command=Bash:cat --by fact  # file:line
```

`--by fact` prints the heaviest leaves, e.g.
`81,989  <project>/<session-id>.jsonl:76  <uuid>  project=… cause=ambiguous reason=several`,
an ambiguous one's `candidates:` under it, one `<file>:<line> <uuid>  dims`
each; it carries a tool only when all candidates share it. A `command` is a Bash
call's first command word as a basename (`Bash:pytest`),
or a file tool's extension (`Read:py`); never a path.
Exit 2, naming what is declared or present: `spend --where cause=...`
(calls carry only window dims), `cause=bogus` (undeclared),
`tool=bash` (no change carries it).

## Reading the output

The scope is
`read:` (files, `--since`, root, lines skipped, duplicates excluded:
corpus-wide) and `in view where <window pins>:` (windows, `changes` or
`calls`); a compaction a call follows starts a window (`N compactions
unpriced`). Quote both with a figure. Table columns: the metric
(`context tokens`, `spend`), its count (`changes`, `calls`) and `share
of <base>`, naming its base. Tables end with `unassigned*` (facts
lacking the grouped dimension) and any `(signed)` rows; neither has a
share. A default table cuts a label over 40 chars to `…tail`; `--by`
prints it whole. A `*` term is explained in one clause below the tables,
in full by `python3 -m sa explain TERM`.

Unnarrowed, the `context` cause table ends with `= total N  ✓ = final
window sizes`, and the last line is this run's attribution
quality over the gaps between calls (calls minus windows), each split
into one or more changes:

<!-- example: context | ✓ checks -->
```
✓ checks: 254,860 added - 300 shrink = 254,560; 18 gaps between calls (21 calls - 3 windows): 6 to one source (33.3%), 9 ambiguous (50.0%), 3 shrank (16.7%)
```

A failure prints `MISMATCH` in full, a bug in this tool, exit 1. A
drill's checks line names the whole windows it applies to. `inherited (counted in parent)`
follows when a kept parent window already counts a fork's copy.

## Refusals

No dollars; no estimated attribution (one `ambiguous` row, never a
spread); no summed peaks.

## Answering a user

1. Run the matching command, narrowed (`--since`, `--where project=` /
   `session=`) to what was asked.
2. Report the headline, the scope lines and the checks rates.
3. Drill one step past the headline; name the heaviest leaf with its
   `file:line`.
4. End with the action the numbers suggest, or say the attribution is too
   ambiguous (quote the rate).
