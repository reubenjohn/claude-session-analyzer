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
| `--where project=NAME` / `session=ID` / `agent=ID` | a project directory name (e.g. `-home-me-workspace-myproject`), sessionId or agentId; keeps whole windows |
| `--where DIM=VALUE` | repeatable, exact after dedup; dims: project, session, agent, cause, tool, head, reason |
| `--by DIM` | one dimension's table instead of the default set |
| `--by fact` | leaf facts: `tokens  file:line  uuid  dimensions`, evidence indented under each |
| `--limit N` | rows per table; the rest fold into `+k more rows` |

## What each command answers

**`context`** books every change of context-window occupancy as an
*increment* with one `cause`: `window_head` (the first call's occupancy:
boot context for a fresh session, inherited for a fork; a note under the
cause table says so), `feed_forward` (the previous turn's own output),
`tool_result`, `user_text`, `ambiguous` (more than one candidate) and
`shrink` (a window that got smaller, signed). Default tables: cause, tool,
head, agent, session, project (`reason` via `--by`). A `single-call peak
context_tokens` line under the headline names the fullest window's call.

**`spend`** sums each call's cost in input-side base-token-equivalents:
output tokens, uncached input, cache writes (1h at 2.0x, 5m at 1.25x) and
cache reads at 0.1x. Default tables: project, session, agent; `--by agent`
answers "which subagent was expensive". Its note line says spend is paid
per call, so context shares are not cost shares.

Either headline names the top row of the first table shown, or of `--by`.

## The drill: headline -> `--by` -> `--where` -> `--by fact`

```bash
python3 -m sa context --since 7d                      # default tables
python3 -m sa context --since 7d --by cause           # one table
python3 -m sa context --since 7d --where cause=tool_result --by tool
python3 -m sa context --since 7d --where tool=Bash --by head   # Bash:cat ...
python3 -m sa context --since 7d --where cause=ambiguous --by fact --limit 2
```

`--by fact` prints the heaviest leaf facts with their locator, e.g.
`81,989  <project>/<session>.jsonl:76  <uuid>  project=... cause=ambiguous reason=multi_contributor`,
and under an ambiguous one a `candidates: <file>:<line> <uuid>` line per
contributor. Locators are relative to the corpus root in the population
line; open that transcript line to see what landed in the window. A
`head` is `<tool>:<summary>`: a Bash call's first command word
(`Bash:pytest`) or a file tool's extension (`Read:py`), never a path.
`spend` facts carry only project, session and agent, so `spend --where
cause=...` is refused with exit 2.

## Reading the output

Every run prints a **population** line: corpus root, files read, windows,
call and increment facts, lines skipped, duplicates excluded, `where`
filters. Quote it with any figure you report; a number without its
population is not a finding. The share column is `share of <base>`, the
mass the shares are over (just `share` when no row has one). Tables end
with the residual row `∅` (facts lacking the grouped dimension) and any
`(signed)` rows; neither has a share.

Unnarrowed, the `context` headline reads `= the N windows' final
occupancies summed` and ends with a three-line **reconciliation footer**:

```
reconciliation over 23 windows: window_head 1,011,695 + feed_forward 181,474 + tool_result 699,884 + user_text 30,444 + ambiguous 537,617 + shrink 0 = 2,461,114; final occupancy 2,461,114: OK
intervals 468 (= 491 calls - 23 windows): exact 373 (79.7%) + ambiguous 95 (20.3%) [multi_contributor 94, negative_remainder 1] + shrink 0 (0.0%): OK
exact: the interval's one token-relevant contributor (a tool_result or user text) after subtracting the previous call's output. Exact given the feed-forward model; bookkeeping attachments are folded into the single contributor's remainder.
```

Line 1 proves the increments telescope to the final occupancy; a
`MISMATCH` exits 1; distrust the numbers above it. Line 2
is this run's attribution quality over the intervals (calls minus
windows); line 3 defines *exact*. Rates are measured per run, never
hard-coded; report them with the headline. A drill (`--where` on a
non-window dimension) replaces the footer with one line, `reconciliation:
applies to the N whole windows above, not to this drill: OK`.

`spend` ends with the `output_tokens`, `cache_write_1h_tokens` and
`cache_write_5m_tokens` totals and the same `single-call peak` line.

## Refusals, and why

No dollars (rates differ per model and speed tier; a dollar figure would
be a confident wrong number); no estimated attribution (several candidates
go to the one `ambiguous` row with a reason, never a spread); no summed
peaks (`context_tokens` is a high-water mark). A good answer ends in an
action; a spread or a dollar guess leads nowhere you can act.

## Answering a user

1. Run the matching command, narrowed with `--since` / `--where project=`
   / `--where session=` to what they asked about.
2. Report the headline, the population line and the footer rates.
3. Drill one step past the headline; name the heaviest leaf with its
   `file:line`.
4. End with the action the numbers suggest, or say the attribution is too
   ambiguous (quote the rate) to suggest one.
