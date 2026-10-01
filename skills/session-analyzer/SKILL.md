---
name: session-analyzer
description: Measures where a Claude Code session's context went and what it cost, from the local transcripts; use when the user asks "where is my context going", "what did this session cost", "which subagent or tool was expensive", or "analyze my Claude Code sessions".
---

# session-analyzer

Two questions, two commands, from the JSONL transcripts under
`~/.claude/projects`. Standard library only.

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m sa context   # where did my context go
cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m sa spend     # what did it cost
```

Narrow, then drill:

| Flag | Meaning |
|---|---|
| `--since 7d` | files modified within the last N days |
| `--where project=` / `session=` / `agent=` | a project directory name (e.g. `-home-me-workspace-myproject`), sessionId or agentId; keeps whole windows |
| `--where DIM=VALUE` | repeatable, exact after dedup; dims: project, session, agent, cause, tool, head, reason |
| `--by DIM` | one dimension's table |
| `--by fact` | leaf facts: `tokens  file:line  uuid  dimensions`, evidence indented under each |
| `--limit N` | rows per table, at least 1; the rest fold into `+k more rows` |

## What each command answers

**`context`** books every change of context-window occupancy as an
*increment* with one `cause`: `window_head` (the first call's occupancy:
boot, or inherited for a fork; a note says so), `feed_forward` (the
previous turn's own output),
`tool_result`, `user_text`, `ambiguous` (more than one candidate) and
`shrink` (a window that got smaller, signed). Default tables: cause, tool,
head, agent, session, project (`reason` via `--by`).

**`spend`** sums each call's cost in input-side base-token-equivalents:
output tokens, uncached input, cache writes (1h at 2.0x, 5m at 1.25x) and
cache reads at 0.1x. Default tables: project, session, agent; `--by agent`
answers "which subagent was expensive", its `∅` row being the main
windows (no subagent; a note says so). A note says spend is paid per
call: context shares are not cost shares.

Either headline names the top row of the first table shown, or of
`--by`, with its mass and the base of its share: `top agent=agent-a1
1,116,805 (13.2% of 8,475,046 with an agent)` when the `∅` row is
excluded, `top cause=tool_result 1,190,872 (34.3%)` when the base is the
total. Never `window_head`; `--by fact` names no top row. The
`single-call peak context_tokens` line, directly under the headline,
names the fullest call over the N whole windows, even under a drill.

## The drill: headline -> `--by` -> `--where` -> `--by fact`

```bash
python3 -m sa context --since 7d
python3 -m sa context --since 7d --by cause
python3 -m sa context --since 7d --where tool=Bash --by head
python3 -m sa context --since 7d --where cause=ambiguous --by fact --limit 2
```

`--by fact` prints the heaviest leaf facts with their locator, e.g.
`81,989  -home-me-workspace-myproject/<session-id>.jsonl:76  <uuid>  project=-home-me-workspace-myproject session=<session-id> cause=ambiguous reason=multi_contributor`
(a main-window leaf carries no `agent=` tag), and under an ambiguous one
`candidates:` once, then a line per contributor with its own
cause/tool/head:
`<file>:<line> <uuid>  cause=tool_result tool=Read head=Read:py`. The row
itself carries a tool only when all its candidates share one. Locators
are relative to the population root; open the line to see what landed.
A `head` is a Bash call's first word (`Bash:pytest`) or a file tool's
extension (`Read:py`), never a path. Exit 2, naming what is declared:
`spend --where cause=...` (spend facts carry only project, session,
agent) and `--where cause=bogus` (not a declared value).

## Reading the output

Every run prints a **population** line: corpus root, files read, windows,
call and increment facts, lines skipped, duplicates excluded, `where`
filters. Quote it with any figure you report; a number without its
population is not a finding. `share of <base>` names the mass the shares
are over. Tables end with the residual row `∅` (facts
lacking the grouped dimension; under `by tool`, `by head` and `by agent`
a note says what it holds) and any `(signed)` rows; neither has a share.

Unnarrowed, the `context` headline reads `= the N windows' final
occupancies summed` and ends with a three-line **reconciliation footer**:

```
reconciliation over 30 windows: window_head 1,253,541 + feed_forward 198,359 + tool_result 1,190,872 + user_text 50,254 + ambiguous 779,353 + shrink 0 = 3,472,379; final occupancy 3,472,379: OK
intervals 740 (= 770 calls - 30 windows): exact 590 (79.7%) + ambiguous 150 (20.3%) [multi_contributor 149, negative_remainder 1] + shrink 0 (0.0%): OK
exact: the interval's one token-relevant contributor (a tool_result or user text) after subtracting the previous call's output. Exact given the feed-forward model; bookkeeping attachments are folded into the single contributor's remainder.
```

Line 1 proves the increments telescope to the final occupancy; a
`MISMATCH` exits 1. Line 2 is this run's attribution quality over the
intervals (calls minus windows); line 3 defines *exact*. Report the rates
with the headline. A drill replaces the footer with one line,
`reconciliation: applies to the N whole windows above, not to this
drill: OK`. `spend` ends with the output and cache-write token totals.

## Refusals, and why

No dollars (rates differ per model and tier: a confident wrong number);
no estimated attribution (several candidates go to one `ambiguous` row,
never a spread); no summed peaks (`context_tokens` is a high-water mark).

## Answering a user

1. Run the matching command, narrowed (`--since`, `--where project=` /
   `session=`) to what they asked about.
2. Report the headline, the population line and the footer rates.
3. Drill one step past the headline; name the heaviest leaf with its
   `file:line`.
4. End with the action the numbers suggest, or say the attribution is too
   ambiguous (quote the rate) to suggest one.
