---
name: session-analyzer
description: Measures what Claude Code sessions cost and, cost aside, whether context degrades the model (context rot) and what fills it, from transcripts; use when the user asks "where is my context going", "is my context too big", "what did this session cost", "which subagent or tool was expensive".
---

# session-analyzer

Two questions from `~/.claude/projects`: what did it cost; then, cost
aside, is context degrading the model (every call reasons over its
whole window: context rot), what fills it, what to cut.

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m sa spend     # what did it cost
cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m sa context   # cost aside: is context a problem
```

Pin, then drill:

| Flag | Meaning |
|---|---|
| `--since 30d` | files modified in the last N days (default 7d; `all`: every file) |
| `--where project=` / `session=` / `subagent=` / `window=` / `started_by=` / `peak=` | as printed (a subagent: or its id; a window: its hex, `--by window`; peak: `0-50K` .. `200K+`, the band of its largest call); keeps whole windows |
| `--where DIM=VALUE` | a pin, repeatable, exact; also cause, tool, command, reason (a drill) |
| `--by DIM` | one dimension's table |
| `--by fact` | one change (spend: call) per row: `<metric>  file:line  uuid  dims`, evidence under |
| `--limit N` | rows per table (5); the rest fold to `+k more rows`, never causes, `unassigned` or negative (shrink) rows |

## What each command answers

**`context`** books every change of a window's context (a *change*)
with one `cause`, and prints its `part of avg`: its tokens times the
calls that held it, over ALL calls in view, so a table's rows add up
to the average context per call. Causes: `starting_context` (what a window held at its first call; a fork's
copy is `inherited` apart), `replies` (Claude's replies, tool-call inputs included),
`tool_result`, `user_text`, `ambiguous` (no one contributor; `reason`:
`several`, `less_than_reply`, `unexplained`) and `shrink` (a window that
got smaller, signed). Default tables: cause, tool, command, subagent,
peak, session, project; a window table adds windows, calls, own `avg call`.

**`spend`** sums each call's price-weighted input tokens: uncached
input, cache writes (1h 2.0x, 5m 1.25x), cache reads 0.1x; output
apart. Default tables: project, session, subagent (`unassigned`: the
main windows). Context shares are not cost shares.

Whatever `--by` shows, the `context` headline opens with `average
context per call* N tokens, over C calls in W windows` (what a call
held; never summed, never "added per call"), then a block in the same
unit (shares of the average before shrink): the starting context by
`started_by`, then `growth`: the top tool `→` its largest command, then
a larger `top command`. `spend` names the largest subagent. A `--where`
pin omits the default tables and levers it implies (a command its tool,
a window its subagent, session, project). A drill keeps the calls of the
windows in view and names its changes (`, from 3 changes where
tool=Bash in 2 of them`). A fork missing its parent (or
branch call) counts its copy as its own; the scope says so.

## The path: is it a problem -> what -> where -> what to fix

```bash
python3 -m sa context                                    # average, by peak
python3 -m sa context --where peak=200K+                 # what fills them
python3 -m sa context --where peak=200K+ --where tool=Bash  # where: top tool
python3 -m sa context --where peak=200K+ --where command=Bash:cat --by fact  # file:line
```

`--by fact` prints the heaviest leaves, its part of the average then its
raw tokens, e.g. `1,204  81,989  <project>/<id>.jsonl:76  <uuid>  … cause=ambiguous`,
an ambiguous one's `candidates:` under it, one `<file>:<line> <uuid>  dims`
each; it carries a tool only when all candidates share it. A `command` is a Bash
call's first command word as a basename (`Bash:pytest`),
or a file tool's extension (`Read:py`); never a path.
Exit 2 names what is declared or present (`cause=bogus`, `tool=bash`,
`spend --where cause=`: calls carry only window dims).

## Reading the output

The scope is
`read:` (files, `--since`, root, lines skipped, duplicates excluded:
corpus-wide) and `in view where <window pins>:` (windows, `changes` or
`calls`); a compaction a call follows starts a window (`N compactions
unpriced`). Quote both with a figure. Table columns: the metric
(`part of avg`, `spend`), its count (`changes`, `calls`) and `share
of <base>`, naming its base. Tables end with `unassigned*` (facts
lacking the grouped dimension) and any `(signed)` rows; neither has a
share. A default table cuts a label over 40 chars to `…tail`; `--by`
prints it whole. A `*` term is explained in one clause below the tables,
in full by `python3 -m sa explain TERM`.

Unnarrowed, the `context` cause table ends with `= average N  ✓ = mean
call size`; the checks state the per-call and summed identities, then
this run's attribution quality over the gaps between calls:

<!-- example: context | ✓ checks -->
```
✓ checks: 1,778,890 tokens × calls (each change's tokens × the calls that held it) = the calls' sizes summed; 254,860 tokens added - 300 shrink = 254,560 = the final window sizes
  18 gaps between calls (21 calls - 3 windows): 6 to one source (33.3% of gaps), 9 ambiguous (50.0% of gaps), 3 shrank (16.7% of gaps)
```

A failure prints `MISMATCH` in full, a bug in this tool, exit 1. A
drill's checks name the whole windows it applies to.

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
