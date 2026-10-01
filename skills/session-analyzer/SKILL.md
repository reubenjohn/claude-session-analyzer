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

Default scope is the whole corpus; narrow, then drill:

| Flag | Meaning |
|---|---|
| `--since 7d` | files modified in the last N days (the only pre-read filter) |
| `--where project=NAME` / `--where session=ID` | one project directory name (e.g. `-home-me-workspace-myproject`) or one sessionId, exact; keeps whole windows |
| `--where DIM=VALUE` | repeatable, exact match after dedup; dims: project, session, agent, cause, tool, head, reason, candidate_count |
| `--by DIM` | one dimension's table instead of all |
| `--by fact` | the leaf facts: one line each, `tokens  file:line  uuid  dimensions` |
| `--limit N` | rows per table; the rest fold into one `+k more rows` line |

## What each command answers

**`context`** books every change of context-window occupancy as an
*increment* with one `cause`: `window_head` (the first call's occupancy:
boot context for a fresh session, inherited for a fork), `feed_forward`
(the previous turn's own output), `tool_result`, `user_text`, `ambiguous`
(more than one candidate) and `shrink` (a window that got smaller,
reported signed). The headline names the top cause, then one
table per dimension.

**`spend`** sums each call's cost in input-side base-token-equivalents:
output tokens, uncached input, cache writes (1h at 2.0x, 5m at 1.25x) and
cache reads at 0.1x. The headline names the top project; `--by agent` is
the usual follow-up for "which subagent was expensive".

## The drill: headline -> `--by` -> `--where` -> `--by fact`

Each step narrows the population; the last lands on a transcript line.

```bash
python3 -m sa context --since 7d                          # every table
python3 -m sa context --since 7d --by cause               # one table
python3 -m sa context --since 7d --where cause=tool_result --by tool
python3 -m sa context --since 7d --where tool=Bash --by head   # first command word
python3 -m sa context --since 7d --where tool=Bash --where head=cat --by fact
```

`--by fact` prints the heaviest leaf facts with their locator, e.g.
`9,535  <file>:<line>  <uuid>  cause=tool_result tool=Write head=py`. Open
that transcript line to see what landed in the window. A `head` is the
first command word of a Bash call or a file tool's extension, never a
path. `spend` facts carry only project, session and agent, so `spend
--where cause=...` is refused with exit 2.

## Reading the output

Every run prints a **population** line: files read, windows, call facts,
increment facts, lines skipped, duplicate records excluded, and `where`
filters. Quote it with any figure you report; a number without its
population is not a finding.

The share column is `share of <base>`, the mass the shares are over. Tables end with the residual row `∅` (facts lacking the grouped
dimension) and any rows marked `(signed)`; neither has a share.

Unnarrowed, the `context` headline reads `= the N windows' final
occupancies summed` and ends with a three-line **reconciliation footer**:

```
reconciliation over 20 windows: window_head 906,778 + feed_forward 168,187 + tool_result 498,935 + user_text 21,042 + ambiguous 458,828 + shrink 0 = 2,053,770; final occupancy 2,053,770: OK
intervals 371 (= 391 calls - 20 windows): exact 291 (78.4%) + ambiguous 80 (21.6%) [multi_contributor 79, negative_remainder 1] + shrink 0 (0.0%): OK
exact: the interval's one token-relevant contributor (a tool_result or user text) after subtracting the previous call's output; bookkeeping attachments in the interval fold into its remainder [OPEN]
```

Line 1 proves the increments telescope to the final occupancy; a
`MISMATCH` exits 1 and the numbers above it are not trustworthy. Line 2
is this run's attribution quality over the intervals (calls minus
windows): *exact* went to exactly one contributor, *ambiguous* is the rest
with reasons, *shrink* is windows that got smaller; line 3 defines
*exact*. Rates are measured per run, never hard-coded; report them with
the headline. A drill
(`--where` on a non-window dimension) replaces the footer with one line:
`reconciliation: applies to the N whole windows above, not to this drill:
OK`.

`spend` ends with the other call-carried totals (`output_tokens`,
`cache_write_1h_tokens`, `cache_write_5m_tokens`) and the largest single
call's `context_tokens` at its `file:line`, a peak never summed.

## What the tool refuses to do, and why

- **No dollars.** Spend is in weighted input-side tokens. A rate differs
  per model and speed tier, so a dollar figure would be a confident wrong
  number.
- **No estimated attribution.** An interval with more than one candidate
  contributor goes to the one `ambiguous` row with its reason, never
  spread by guesswork.
- **Peaks are never summed.** `context_tokens` is a high-water mark; the
  tool reports the single largest call, not a total.
- **Every figure names its population.** The line is reprinted on every
  run.

A good answer ends in an action; a spread or a dollar guess leads nowhere
you can act.

## Answering a user

1. Run the matching command, narrowed with `--since` / `--where project=`
   / `--where session=` to what they asked about.
2. Report the headline, the population line and the footer rates.
3. Drill one step past the headline and name the heaviest leaf, with its
   `file:line`.
4. End with the action the numbers suggest, or say that the attribution
   is too ambiguous (quote the rate) to suggest one.
