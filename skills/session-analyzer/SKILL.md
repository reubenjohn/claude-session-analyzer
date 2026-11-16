---
name: session-analyzer
description: Measures where a Claude Code session's context went and what it cost, from the local transcripts; use when the user asks "where is my context going", "what did this session cost", "which subagent or tool was expensive", or "analyze my Claude Code sessions".
---

# session-analyzer

Two questions, two commands, from the JSONL transcripts under
`~/.claude/projects`.

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m sa context   # where did my context go
cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m sa spend     # what did it cost
```

Pin, then drill:

| Flag | Meaning |
|---|---|
| `--since 30d` | files modified in the last N days (default 7d; `all`: every file) |
| `--where project=` / `session=` / `subagent=` / `window=` / `started_by=` | project as printed (`~-work-app`), sessionId, subagent as printed or its id, a window's hex (`--by window`) or what began it; keeps whole windows |
| `--where DIM=VALUE` | a pin, repeatable, exact; dims: project, session, subagent, window, started_by, cause, tool, command, reason |
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
session, project (`reason` and `window` via `--by`).

**`spend`** sums each call's price-weighted input tokens: uncached
input, cache writes (1h at 2.0x, 5m at 1.25x) and cache reads at 0.1x;
output tokens are excluded, totalled apart at the end. Default tables:
project, session, subagent; `--by subagent` answers "which subagent was
expensive", its `unassigned` row the main windows. Context shares are not
cost shares.

Whatever `--by` shows, the `context` headline states one total, then a
block (shares of the mass added, shrink out): the starting context as a
sum by `started_by` (what was there at window start, never a window
size), then `growth`: the top tool `→` its largest command, then a
larger `top command`. `spend` names the largest subagent. Never a cause or a window row. A
`--where` pin omits the default tables and levers it implies (a command
its tool, a window its subagent, session, project). A drill's headline
names its pins and the windows hit (`… in 1 of 2 windows`); `largest single-call context N tokens (of W windows), window=<hex>`
under it: the fullest call, even under a drill.

## The drill: headline -> `--by` -> `--where` -> `--by fact`

```bash
python3 -m sa context
python3 -m sa context --by cause
python3 -m sa context --where tool=Bash --by command
python3 -m sa context --where cause=ambiguous --by fact --limit 2
```

`--by fact` prints the heaviest leaves with their locator, e.g.
`81,989  <project>/<session-id>.jsonl:76  <uuid>  project=… session=… cause=ambiguous reason=several`
and under an ambiguous one
`candidates:`, then one line per contributor:
`<file>:<line> <uuid>  cause=tool_result tool=Read command=Read:py`. The row
carries a tool only when all candidates share it. A `command` is a Bash
call's first command word as a basename (`Bash:pytest`),
or a file tool's extension (`Read:py`); never a path.
Exit 2, naming what is declared or present: `spend --where cause=...`
(calls carry only window dims), `cause=bogus` (undeclared),
`tool=bash` (no change carries it).

## Reading the output

The scope is
`read:` (files, the `--since` window, the root, lines skipped and
duplicates excluded: corpus-wide) and `in view where <window pins>:`
(windows and the view's `changes` or `calls`); a window is one context window:
a compaction a call follows starts one (`N compactions unpriced`). Quote both with a figure: a
number without its population is no finding. Table columns: the metric
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

It holds by construction: a failure prints the reconciliation in full
with `MISMATCH`, a bug in this tool, exit 1. A drill's checks line names
the N whole windows it applies to. `inherited (counted in parent)`
follows when a kept parent window already counts a fork's copy.

## Refusals

No dollars (rates differ per model); no estimated attribution
(one `ambiguous` row, never a spread); no summed peaks (`context_tokens`
is a high-water mark).

## Answering a user

1. Run the matching command, narrowed (`--since`, `--where project=` /
   `session=`) to what was asked.
2. Report the headline, the scope lines and the checks rates.
3. Drill one step past the headline; name the heaviest leaf with its
   `file:line`.
4. End with the action the numbers suggest, or say the attribution is too
   ambiguous (quote the rate).
