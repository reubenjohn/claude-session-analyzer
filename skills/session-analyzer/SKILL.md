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

Narrow, then drill:

| Flag | Meaning |
|---|---|
| `--since 30d` | files modified within the last N days (default 7d; `all` reads every file) |
| `--where project=` / `session=` / `agent=` / `window=` | project directory name (`-home-me-workspace-myproject`), sessionId, agentId or root-relative file name (isolates one main window); keeps whole windows |
| `--where DIM=VALUE` | repeatable, exact; dims: project, session, agent, window, cause, tool, head, reason |
| `--by DIM` | one dimension's table |
| `--by fact` | leaf facts: `<metric>  file:line  uuid  dimensions`, evidence indented |
| `--limit N` | rows per table; the rest fold into `+k more rows` |

## What each command answers

**`context`** books every change of context-window occupancy as an
*increment* with one `cause`: `window_head` (the first call's occupancy:
boot, or inherited for a fork), `feed_forward` (the previous turn's own
output),
`tool_result`, `user_text`, `ambiguous` (not attributable to one
contributor; `reason` says why) and `shrink` (a window that got smaller,
signed). Default tables: cause, tool,
head, agent, session, project (`reason` and `window` via `--by`).

**`spend`** sums each call's cost in input-side base-token-equivalents:
output tokens, uncached input, cache writes (1h at 2.0x, 5m at 1.25x) and
cache reads at 0.1x. Default tables: project, session, agent; `--by agent`
answers "which subagent was expensive", its `∅` row being the main
windows. A note says spend is paid per call: context shares are not cost
shares.

Whatever `--by` shows, the `context` headline names the top tool with
its mass and share of the total, `within it` that tool's largest head
with its share of the tool and of the total, then a larger head under
another tool, one clause per line: `top tool=Bash 223,025 (28.1% of the
793,922 total)`, `within it head=Bash:git 50,904 (22.8% of Bash, 6.4% of
the total)`; `spend` names the top agent. Never a cause or a window row. A `--where`
pin omits the default tables and levers it implies (a head its tool, a
window its agent, session, project). A drill's headline names its pins and
counts the windows its facts come from (`… where tool=Bash in 29 of 36
windows`). `single-call peak
context_tokens` under it is the fullest call over the N whole windows,
even under a drill.

## The drill: headline -> `--by` -> `--where` -> `--by fact`

```bash
python3 -m sa context
python3 -m sa context --by cause
python3 -m sa context --where tool=Bash --by head
python3 -m sa context --where cause=ambiguous --by fact --limit 2
```

`--by fact` prints the heaviest leaves with their locator, e.g.
`81,989  <project>/<session-id>.jsonl:76  <uuid>  project=… session=… cause=ambiguous reason=multi_contributor`
and under an ambiguous one
`candidates:`, then a line per contributor with its cause/tool/head:
`<file>:<line> <uuid>  cause=tool_result tool=Read head=Read:py`. The row
carries a tool only when all candidates share it. Open the locator to
see what landed.
A `head` is a Bash call's first command word (past keywords, wrappers
and near-silent builtins: `cd`, `echo`) as a basename (`Bash:pytest`),
or a file tool's extension (`Read:py`); never a path.
Exit 2, naming what is declared or present: `spend --where cause=...`
(calls carry only the window dims), `cause=bogus` (undeclared),
`tool=bash` (no fact carries it).

## Reading the output

Sections, in order: scope, answer, tables, key, checks. The scope is
`read:` (files, the `--since` window, the root, then lines skipped and
duplicates excluded: corpus-wide) and `kept where <window pins>:`
(windows and the view's carrier facts). Quote both with a figure: a
number without its population is no finding. Table columns: the metric,
its carrier's count (`increments`, `calls`) and `share of <base>`, which
names its base (`total`, `N added`, `N with a tool`). Tables end with the
residual row `∅` (facts lacking the grouped dimension) and any `(signed)`
rows; neither has a share. Only a default table cuts a label over 40
chars to `…tail`; `--by` shows it whole, ready for `--where`. One dimmed
`key` says what each `∅` and unsplittable row holds; a `°` term is in
`python3 -m sa explain TERM`, with why its number may surprise.

Unnarrowed, the `context` cause table ends with `= total N  ✓ matches
the final window sizes`, and the last line is this run's attribution
quality over the intervals (calls minus windows):

```
✓ checks: 232 intervals (240 calls - 8 windows) = exact 206 (88.8%) + ambiguous 26 (11.2%) + shrink 0 (0.0%)
```

It holds by construction: a failure prints the reconciliation in full
with `MISMATCH`, a bug in this tool, exit 1. A drill's checks line names
the N whole windows it applies to. `spend` ends with the output and
cache-write token totals.

## Refusals

No dollars (rates differ per model and tier); no estimated attribution
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
