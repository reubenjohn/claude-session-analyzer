---
name: session-analyzer
description: Measures where a Claude Code session's context went and what it cost, from the local transcripts; use when the user asks "where is my context going", "what did this session cost", "which subagent or tool was expensive", or "analyze my Claude Code sessions".
---

# session-analyzer

Two questions, two commands, from the JSONL transcripts under
`~/.claude/projects`; stdlib only.

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m sa context   # where did my context go
cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m sa spend     # what did it cost
```

Narrow, then drill:

| Flag | Meaning |
|---|---|
| `--since 7d` | files modified within the last N days |
| `--where project=` / `session=` / `agent=` / `window=` | project directory name (`-home-me-workspace-myproject`), sessionId, agentId or root-relative file name (isolates one main window); keeps whole windows |
| `--where DIM=VALUE` | repeatable, exact; dims: project, session, agent, window, cause, tool, head, reason |
| `--by DIM` | one dimension's table |
| `--by fact` | leaf facts: `<metric>  file:line  uuid  dimensions`, evidence indented |
| `--limit N` | rows per table, at least 1; the rest fold into `+k more rows` |

## What each command answers

**`context`** books every change of context-window occupancy as an
*increment* with one `cause`: `window_head` (the first call's occupancy:
boot, or inherited for a fork), `feed_forward` (the previous turn's own
output),
`tool_result`, `user_text`, `ambiguous` (more than one candidate) and
`shrink` (a window that got smaller, signed). Default tables: cause, tool,
head, agent, session, project (`reason` and `window` via `--by`).

**`spend`** sums each call's cost in input-side base-token-equivalents:
output tokens, uncached input, cache writes (1h at 2.0x, 5m at 1.25x) and
cache reads at 0.1x. Default tables: project, session, agent; `--by agent`
answers "which subagent was expensive", its `∅` row being the main
windows. A note says spend is paid per call: context shares are not cost
shares.

Either headline names the largest lever row (`context`: tool or head,
ties to the more specific; `spend`: agent) or `--by`'s top row, with its
mass and share of the total: `top tool=Bash 1,553,915 (31.5% of the
4,936,844 total)`. Never `window_head` or `ambiguous`; `--by fact` names
none. A drill's headline counts the windows
its facts come from (`in 29 of 36 windows`). The `single-call peak
context_tokens` line under it names the fullest call over the N whole
windows, even under a drill.

## The drill: headline -> `--by` -> `--where` -> `--by fact`

```bash
python3 -m sa context
python3 -m sa context --by cause
python3 -m sa context --where tool=Bash --by head
python3 -m sa context --where cause=ambiguous --by fact --limit 2
```

`--by fact` prints the heaviest leaves with their locator, e.g.
`81,989  <project>/<session-id>.jsonl:76  <uuid>  project=<project> session=<session-id> cause=ambiguous reason=multi_contributor`
(no `agent=` on a main-window leaf), and under an ambiguous one
`candidates:`, then a line per contributor with its cause/tool/head:
`<file>:<line> <uuid>  cause=tool_result tool=Read head=Read:py`. The row
carries a tool only when all candidates share one. Locators are
root-relative; open the line to see what landed.
A `head` is a Bash call's first command word (keywords, wrappers and
output-less builtins (`echo`, `source`) skipped) as a basename
(`Bash:pytest`), or a file tool's extension (`Read:py`); never a path.
Exit 2, naming what is declared or present: `spend --where cause=...`
(spend facts carry only the window dims), `--where cause=bogus`
(undeclared), `--where tool=bash` (no fact carries it).

## Reading the output

Every run prints a **population** line: corpus root, files read, windows,
call and increment facts, lines skipped, duplicates excluded, `where`
filters. Quote it with any figure; a number without its population is not
a finding. Table columns: the metric (`context_delta`, `spend`), its
carrier's count (`increments`, `calls`) and `share of <base>`, the mass
the shares are over. Tables end with the residual row `∅` (facts lacking
the grouped dimension, a note saying what it holds) and any `(signed)`
rows; neither has a share. A label over 40 chars keeps its tail behind
`…`; `--by fact` and a `--where` refusal show it whole.

Unnarrowed, the `context` headline reads `= the N windows' final
occupancies summed` and ends with a three-line **reconciliation footer**
whose first two lines read:

```
reconciliation over 32 windows: window_head 1,323,189 + feed_forward 205,510 + tool_result 1,287,069 + user_text 58,365 + ambiguous 998,551 + shrink 0 = 3,872,684; final occupancy 3,872,684: OK
intervals 831 (= 863 calls - 32 windows): exact 631 (75.9%) + ambiguous 200 (24.1%) [multi_contributor 199, negative_remainder 1] + shrink 0 (0.0%): OK
```

Line 1 proves the increments telescope to the final occupancy; a
`MISMATCH` exits 1. Line 2 is this run's attribution quality over the
intervals (calls minus windows); line 3 defines *exact* (one token-relevant
contributor after subtracting the previous call's output). Report the
rates with the headline. A drill replaces the footer with one line,
`reconciliation: applies to the N whole windows above, not to this
drill: OK`. `spend` ends with the output and cache-write token totals.

## Refusals, and why

No dollars (rates differ per model and tier: a confident wrong number);
no estimated attribution (several candidates: one `ambiguous` row, never
a spread); no summed peaks (`context_tokens` is a high-water mark).

## Answering a user

1. Run the matching command, narrowed (`--since`, `--where project=` /
   `session=`) to what was asked.
2. Report the headline, the population line and the footer rates.
3. Drill one step past the headline; name the heaviest leaf with its
   `file:line`.
4. End with the action the numbers suggest, or say the attribution is too
   ambiguous (quote the rate).
