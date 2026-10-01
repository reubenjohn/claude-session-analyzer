# claude-session-analyzer

Two questions about your Claude Code sessions, answered from the JSONL
transcripts under `~/.claude/projects`: **where is my context going?**
(`sa context`) and **what did it cost?** (`sa spend`). Every figure names
its population, every table shows its residual, and `context` ends with a
reconciliation proving the increments add up to the windows' final
occupancy. A Claude Code plugin whose skill drives the CLI, or plain
`python3 -m sa`. Standard library only, Python 3.8+.

## Install

```
claude plugin marketplace add reubenjohn/claude-session-analyzer
claude plugin install claude-session-analyzer@reubenjohn
```

(or `/plugin` inside Claude Code). Then ask Claude "where is my
context going?"; the skill runs the commands below.

## The two commands

```
python3 -m sa context --since 7d --by cause
```

```
context_delta: 2,461,114 context tokens = the 23 windows' final occupancies summed; top cause=window_head 41.1%
single-call peak context_tokens: 195,591 context tokens at -home-me-workspace-myproject/<session-id>.jsonl:537
population: root ~/.claude/projects; 30 files read (modified within 7d), 23 windows, 491 call facts, 958 increment facts; 0 lines skipped, 0 duplicate records excluded

by cause        context tokens    count  share of 2,461,114
window_head          1,011,695       23               41.1%
tool_result            699,884      346               28.4%
ambiguous              537,617       95               21.8%
feed_forward           181,474      467                7.4%
user_text               30,444       27                1.2%
window_head: first call's context: boot prompt + first message, or inherited parent context for a fork; not splittable by content

reconciliation over 23 windows: window_head 1,011,695 + feed_forward 181,474 + tool_result 699,884 + user_text 30,444 + ambiguous 537,617 + shrink 0 = 2,461,114; final occupancy 2,461,114: OK
intervals 468 (= 491 calls - 23 windows): exact 373 (79.7%) + ambiguous 95 (20.3%) [multi_contributor 94, negative_remainder 1] + shrink 0 (0.0%): OK
exact: the interval's one token-relevant contributor (a tool_result or user text) after subtracting the previous call's output. Exact given the feed-forward model; bookkeeping attachments are folded into the single contributor's remainder.
```

```
python3 -m sa spend --since 7d --by agent --limit 3
```

```
spend: 8,194,625 input-side base-token-equivalents over 492 call facts in 23 windows; top agent=main 47.7%
spend is paid per call; context shares are not cost shares. What put the tokens there is answered by `sa context` (--by tool, --by head).
population: root ~/.claude/projects; 30 files read (modified within 7d), 23 windows, 492 call facts, 960 increment facts; 0 lines skipped, 0 duplicate records excluded

by agent       input-side base-token-equivalents    count  share of 8,194,625
main                  3,906,924      214               47.7%
agent-a1                920,382       71               11.2%
agent-b2                838,959       53               10.2%
+12 more rows         2,528,359      154               30.9%

output_tokens: 188,704 tokens
cache_write_1h_tokens: 865,486 tokens
cache_write_5m_tokens: 1,342,327 tokens
single-call peak context_tokens: 195,591 context tokens at -home-me-workspace-myproject/<session-id>.jsonl:537
```

Spend is input-side base-token-equivalents (cache reads 0.1x, 5m writes
1.25x, 1h writes 2.0x), never dollars. Footer rates are measured per run;
locators are relative to the population line's root. No estimated
attribution (several candidates is one `ambiguous` row, never a spread),
peaks are never summed, a `MISMATCH` exits 1.

## The drill

```
python3 -m sa context                    # cause, tool, head, agent, session, project
python3 -m sa context --by reason        # one dimension's table
python3 -m sa context --where cause=tool_result --by tool
python3 -m sa context --where tool=Bash --by head      # heads: Bash:cat, Read:py
python3 -m sa context --where cause=ambiguous --by fact --limit 2
```

Dimensions: `project`, `session`, `agent`, `cause`, `tool`, `head`,
`reason`. `--where DIM=VALUE` is repeatable and exact: on
`project`/`session`/`agent` it keeps whole windows; otherwise it is a
drill, the footer shrinks to one line, and a dimension the view's facts
never carry (`spend --where cause=...`) exits 2. `--since Nd` filters files
by modification time before reading. The headline names the top row of the
first table shown, or of `--by`. `--by fact` lists the heaviest leaves with
`file:line`, uuid and, when ambiguous, `candidates:` lines.

## Tests, layout

`python3 -m pytest tests/`: synthetic fixtures plus the privacy gate (no
real paths, session ids or transcript text in tracked files). `sa/` is the
package (`corpus`, `walk`, `heads`, `schema`, `query`, `cli`, `usage`);
`skills/session-analyzer/` and `.claude-plugin/` are the plugin;
`references/` holds the design brief, decision log and measurements.

## License

MIT
