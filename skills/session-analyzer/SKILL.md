---
name: session-analyzer
description: Measures where a Claude Code session's context went and what it cost, from the local transcripts; use when the user asks "where is my context going", "what did this session cost", "which subagent or tool was expensive", or "analyze my Claude Code sessions".
---

# session-analyzer

Two questions, two commands, read from the JSONL transcripts under
`~/.claude/projects`. Standard library only.

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m sa context   # where did my context go
cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m sa spend     # what did it cost
```

Narrow, then drill:

| Flag | Meaning |
|---|---|
| `--since 7d` | files modified in the last N days (the only pre-read filter) |
| `--where project=NAME` / `session=ID` / `agent=ID` | a project directory name (e.g. `-home-me-workspace-myproject`), sessionId or agentId; keeps whole windows |
| `--where DIM=VALUE` | repeatable, exact after dedup; dims: project, session, agent, cause, tool, head, reason |
| `--by DIM` | one dimension's table instead of the default set |
| `--by fact` | leaf facts: `tokens  file:line  uuid  dimensions`, evidence indented under each |
| `--limit N` | rows per table, at least 1; the rest fold into `+k more rows` |

## What each command answers

**`context`** books every change of context-window occupancy as an
*increment* with one `cause`: `window_head` (the first call's occupancy:
boot context for a fresh session, inherited for a fork; a note under the
cause table says so), `feed_forward` (the previous turn's own output),
`tool_result`, `user_text`, `ambiguous` (more than one candidate) and
`shrink` (a window that got smaller, signed). Default tables: cause, tool,
head, agent, session, project (`reason` via `--by`). The `single-call
peak context_tokens over the N whole windows` line names the fullest
call, whole windows even under a drill.

**`spend`** sums each call's cost in input-side base-token-equivalents:
output tokens, uncached input, cache writes (1h at 2.0x, 5m at 1.25x) and
cache reads at 0.1x. Default tables: project, session, agent; `--by agent`
answers "which subagent was expensive". Its note line says spend is paid
per call, so context shares are not cost shares.

Either headline names the top row of the first table shown, or of `--by`.

## The drill: headline -> `--by` -> `--where` -> `--by fact`

```bash
python3 -m sa context --since 7d
python3 -m sa context --since 7d --by cause
python3 -m sa context --since 7d --where cause=tool_result --by tool
python3 -m sa context --since 7d --where tool=Bash --by head
python3 -m sa context --since 7d --where cause=ambiguous --by fact --limit 2
```

`--by fact` prints the heaviest leaf facts with their locator, e.g.
`81,989  -home-me-workspace-myproject/<session-id>.jsonl:76  <uuid>  project=-home-me-workspace-myproject session=<session-id> agent=main cause=ambiguous reason=multi_contributor`,
and under an ambiguous one `candidates:` once, then a line per contributor
with its own cause/tool/head:
`<file>:<line> <uuid>  cause=tool_result tool=Read head=Read:py`. The row
itself carries a tool only when all its candidates share one. Locators
are relative to the corpus root in the population line; open that line
to see what landed. A `head` is a Bash
call's first word (`Bash:pytest`) or a file tool's extension (`Read:py`),
never a path. `spend --where cause=...` is refused (exit 2): spend facts
carry only project, session and agent.

## Reading the output

Every run prints a **population** line: corpus root, files read, windows,
call and increment facts, lines skipped, duplicates excluded, `where`
filters. Quote it with any figure you report; a number without its
population is not a finding. The share column is `share of <base>`, the
mass the shares are over (just `share` when no row has one). Tables end
with the residual row `∅` (facts lacking the grouped dimension; under `by
tool` and `by head` a note says what it holds) and any `(signed)`
rows; neither has a share.

Unnarrowed, the `context` headline reads `= the N windows' final
occupancies summed` and ends with a three-line **reconciliation footer**:

```
reconciliation over 28 windows: window_head 1,184,945 + feed_forward 195,206 + tool_result 1,085,484 + user_text 46,499 + ambiguous 703,403 + shrink 0 = 3,215,537; final occupancy 3,215,537: OK
intervals 665 (= 693 calls - 28 windows): exact 523 (78.6%) + ambiguous 142 (21.4%) [multi_contributor 141, negative_remainder 1] + shrink 0 (0.0%): OK
exact: the interval's one token-relevant contributor (a tool_result or user text) after subtracting the previous call's output. Exact given the feed-forward model; bookkeeping attachments are folded into the single contributor's remainder.
```

Line 1 proves the increments telescope to the final occupancy; a
`MISMATCH` exits 1; distrust the numbers above it. Line 2 is this run's
attribution quality over the intervals (calls minus windows); line 3
defines *exact*. Report the rates with the headline. A drill (`--where` on a non-window dimension) replaces the
footer with one line, `reconciliation: applies to the N whole windows
above, not to this drill: OK`.

`spend` ends with the output and cache-write token totals and the same
`single-call peak` line.

## Refusals, and why

No dollars (rates differ per model and tier; a dollar figure would be a
confident wrong number); no estimated attribution (several candidates go
to the one `ambiguous` row, never a spread); no summed peaks
(`context_tokens` is a high-water mark). A good answer ends in an action.

## Answering a user

1. Run the matching command, narrowed with `--since` / `--where project=`
   / `--where session=` to what they asked about.
2. Report the headline, the population line and the footer rates.
3. Drill one step past the headline; name the heaviest leaf with its
   `file:line`.
4. End with the action the numbers suggest, or say the attribution is too
   ambiguous (quote the rate) to suggest one.
