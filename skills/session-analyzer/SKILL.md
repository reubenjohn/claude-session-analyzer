---
name: session-analyzer
description: Measures where a Claude Code session's context went and what it cost, from the local transcripts; use when the user asks "where is my context going", "what did this session cost", "which subagent or tool was expensive", or "analyze my Claude Code sessions".
---

# session-analyzer

Two questions, two commands, read from the JSONL transcripts under
`~/.claude/projects`. Standard library only; nothing to install.

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m sa context   # where did my context go
cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m sa spend     # what did it cost
```

Default scope is the whole corpus. Narrow it first, then drill:

| Flag | Meaning |
|---|---|
| `--since 7d` | files modified in the last N days |
| `--project SUBSTR` | project directory name contains SUBSTR |
| `--session ID` | one sessionId |
| `--where DIM=VALUE` | repeatable filter; dims: project, session, agent, cause, tool, head, reason, candidate_count |
| `--by DIM` | one dimension's table instead of all of them |
| `--by fact` | the leaf facts: one line each, ending in `file:line uuid` |
| `--limit N` | rows per table (default 10) |

## What each command answers

**`context`** books every change of context-window occupancy as an
*increment* with one `cause`: `window_head` (the first call's occupancy:
boot context for a fresh session, inherited context for a fork),
`feed_forward` (the previous turn's own output), `tool_result`,
`user_text`, `ambiguous` (an interval with more than one candidate) and
`shrink` (a window that got smaller, reported signed). The headline names
the top cause; the tables break the total down by every dimension.

**`spend`** sums each call's cost in base-token-equivalents: output tokens,
uncached input, cache writes (1h at 2.0x, 5m at 1.25x) and cache reads at
0.1x. The headline names the top project; `--by agent` is the usual
follow-up ("which subagent was expensive").

## The drill: headline -> `--by` -> `--where` -> `--by fact`

Each step narrows the population and ends at a line in a transcript file.

```bash
python3 -m sa context --since 7d                          # headline + every table
python3 -m sa context --since 7d --by cause               # one table
python3 -m sa context --since 7d --where cause=tool_result --by tool
python3 -m sa context --since 7d --where tool=Bash --by head   # first command word
python3 -m sa context --since 7d --where tool=Bash --where head=cat --by fact
```

`--by fact` prints the heaviest leaf facts with their locator, e.g.
`127,811  <file>:<line>  <uuid>  cause=window_head`. Open that line of the
transcript to see what landed in the window. A `head` is the first command
word of a Bash call or a file tool's extension, never a path or a full
command line.

## Reading the output

Every run prints a **population** line: files read, windows, call facts,
increment facts, lines skipped, duplicate records dropped. Quote it with
any figure you report; a number without its population is not a finding.

Tables end with the residual row `∅` (facts that lack the grouped
dimension) and, when present, signed rows marked `(signed)`; neither has a
share. Shares are over the non-residual, non-signed mass.

`context` ends with a two-line **reconciliation footer**:

```
reconciliation over 18 windows: window_head 836,574 + feed_forward 159,164 + tool_result 568,729 + user_text 13,909 + ambiguous 195,950 + shrink 0 = 1,774,326; final occupancy 1,774,326: OK
intervals 314: exact 282 (89.8%), ambiguous 32 (10.2%) [multi_contributor 31, negative_remainder 1], shrink 0 (0.0%)
```

Line 1 proves the increments telescope to the windows' final occupancy; a
`MISMATCH` exits 1 and means the numbers above it are not trustworthy.
Line 2 is this run's measured attribution quality: the *exact* rate is how
much of the chain was attributed to exactly one contributor, *ambiguous*
is the rest (with its reasons), *shrink* is how often a window got
smaller. These rates are measured per run, never hard-coded; report them
alongside the headline so the reader knows how firm the attribution is.

`spend` ends with the other call-carried totals (`output_tokens`,
`cache_write_1h_tokens`, `cache_write_5m_tokens`) and the single largest
window's `context_tokens`, a peak that is never summed.

## What the tool refuses to do, and why

- **No dollars.** Spend is in weighted tokens. A rate differs per model and
  per speed tier, so a dollar figure would be a confident wrong number.
- **No estimated attribution.** An interval with more than one candidate
  contributor goes to the one `ambiguous` row with its reason; it is never
  spread across candidates by guesswork.
- **Peaks are never summed.** `context_tokens` is a high-water mark; the
  tool reports the single largest window, not a total.
- **Every figure names its population.** Filters change the population;
  the line is reprinted on every run.

The reason, in the asker's words: a good answer ends in an action. "Bash
`cat` results are 17% of tool-result context in this project" leads to
"read with `--limit` or `sed -n`"; a spread estimate or a dollar guess
leads nowhere you can act.

## Answering a user

1. Run the matching command, narrowed with `--since` / `--project` /
   `--session` to what they asked about.
2. Report the headline, the population line and the footer rates.
3. Drill one step past the headline and name the heaviest leaf, with its
   `file:line`.
4. End with the action the numbers suggest, or say that the attribution
   is too ambiguous (quote the rate) to suggest one.
