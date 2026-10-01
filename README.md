# claude-session-analyzer

Two questions about your Claude Code sessions, answered from the JSONL
transcripts under `~/.claude/projects`: **where is my context going?**
(`sa context`) and **what did it cost?** (`sa spend`). Every figure names
its population, every table shows its residual, and `context` ends with a
reconciliation proving the increments add up to the windows' final
occupancy. A Claude Code plugin, or plain `python3 -m sa`; standard
library only, Python 3.8+.

## Install

```
claude plugin marketplace add reubenjohn/claude-session-analyzer
claude plugin install claude-session-analyzer@reubenjohn
```

(or `/plugin`); the skill then runs the commands below.

## Usage

```
python3 -m sa context --since 7d --by cause
```

```
context_delta: 3,215,537 context tokens = the 28 windows' final occupancies summed; top cause=window_head 36.9%
single-call peak context_tokens over the 28 whole windows: 229,804 context tokens at -home-me-workspace-myproject/<session-id>.jsonl:694
population: root ~/.claude/projects; 35 files read (modified within 7d), 28 windows, 693 call facts, 1357 increment facts; 0 lines skipped, 0 duplicate records excluded

by cause        context tokens    count  share of 3,215,537
window_head          1,184,945       28               36.9%
tool_result          1,085,484      489               33.8%
ambiguous              703,403      142               21.9%
feed_forward           195,206      664                6.1%
user_text               46,499       34                1.4%
window_head: first call's context: boot prompt + first message, or inherited parent context for a fork; not splittable by content

reconciliation over 28 windows: window_head 1,184,945 + feed_forward 195,206 + tool_result 1,085,484 + user_text 46,499 + ambiguous 703,403 + shrink 0 = 3,215,537; final occupancy 3,215,537: OK
intervals 665 (= 693 calls - 28 windows): exact 523 (78.6%) + ambiguous 142 (21.4%) [multi_contributor 141, negative_remainder 1] + shrink 0 (0.0%): OK
exact: the interval's one token-relevant contributor (a tool_result or user text) after subtracting the previous call's output. Exact given the feed-forward model; bookkeeping attachments are folded into the single contributor's remainder.
```

```
python3 -m sa spend --since 7d --by agent --limit 3
```

```
spend: 11,622,628 input-side base-token-equivalents over 693 call facts in 28 windows; top agent=main 37.7%
spend is paid per call; context shares are not cost shares. What put the tokens there is answered by `sa context` (--by tool, --by head).
population: root ~/.claude/projects; 35 files read (modified within 7d), 28 windows, 693 call facts, 1357 increment facts; 0 lines skipped, 0 duplicate records excluded

by agent       input-side base-token-equivalents    count  share of 11,622,628
main                  4,378,067      233                37.7%
agent-a1              1,116,805       68                 9.6%
agent-b2              1,007,906       71                 8.7%
+17 more rows         5,119,850      321                44.1%

output_tokens: 202,521 tokens
cache_write_1h_tokens: 899,729 tokens
cache_write_5m_tokens: 2,077,766 tokens
single-call peak context_tokens over the 28 whole windows: 229,804 context tokens at -home-me-workspace-myproject/<session-id>.jsonl:694
```

Spend weights cache reads 0.1x, 5m writes 1.25x, 1h writes 2.0x; never
dollars. Locators are relative to the population line's root. No estimated
attribution (several candidates is one `ambiguous` row, never a spread),
no summed peaks; a `MISMATCH` exits 1.

## The drill

```
python3 -m sa context              # cause, tool, head, agent, session, project
python3 -m sa context --by reason
python3 -m sa context --where cause=tool_result --by tool
python3 -m sa context --where tool=Bash --by head      # Bash:cat, Read:py
python3 -m sa context --where cause=ambiguous --by fact --limit 2
```

Dimensions: `project`, `session`, `agent`, `cause`, `tool`, `head`,
`reason`. `--where DIM=VALUE` is repeatable and exact: on
`project`/`session`/`agent` it keeps whole windows; otherwise it is a
drill, the footer shrinks to one line, and a dimension the view's facts
never carry exits 2. `--since Nd` filters files
by mtime; `--limit N` (at least 1) folds the rest of a table into `+k more
rows`. The headline names the top row of the first table shown, or of
`--by`; under `by tool` and `by head` a note says what the residual `∅`
row holds. `--by fact` lists the heaviest leaves as `tokens  file:line
uuid  dimensions`; an ambiguous leaf lists its `candidates:` once, one
line each with file:line, uuid and its own cause, tool and head, and
carries a tool itself only when all candidates share one.

## Layout

`python3 -m pytest tests/`: synthetic fixtures plus the privacy gate (no
real paths, session ids or transcript text in tracked files). `sa/` is the
package; `skills/session-analyzer/` and `.claude-plugin/` the plugin;
`references/` the design docs.

## License

MIT
