# claude-session-analyzer

Two questions about your Claude Code sessions, answered from the JSONL
transcripts under `~/.claude/projects`: **where is my context going?**
(`sa context`) and **what did it cost?** (`sa spend`). Every figure names
its population; `context` ends with a reconciliation proving the
increments sum to the windows' final occupancy. A Claude Code plugin or
plain `python3 -m sa`; stdlib only, Python 3.8+.

## Install

```
claude plugin marketplace add reubenjohn/claude-session-analyzer
claude plugin install claude-session-analyzer@reubenjohn
```

## Usage

```
python3 -m sa context --since 7d --by cause
```

```
context_delta: 3,872,684 context tokens = the 32 windows' final occupancies summed; top cause=tool_result 1,287,069 (33.2%)
single-call peak context_tokens over the 32 whole windows: 255,333 context tokens at -home-me-workspace-myproject/<session-id>.jsonl:807
population: root ~/.claude/projects; 39 files read (modified within 7d), 32 windows, 863 call facts, 1693 increment facts; 0 lines skipped, 0 duplicate records excluded

by cause         context_delta  increments  share of 3,872,684
window_head          1,323,189          32               34.2%
tool_result          1,287,069         591               33.2%
ambiguous              998,551         200               25.8%
feed_forward           205,510         830                5.3%
user_text               58,365          40                1.5%
window_head: first call's context: boot prompt + first message, or inherited parent context for a fork; not splittable by content

reconciliation over 32 windows: window_head 1,323,189 + feed_forward 205,510 + tool_result 1,287,069 + user_text 58,365 + ambiguous 998,551 + shrink 0 = 3,872,684; final occupancy 3,872,684: OK
intervals 831 (= 863 calls - 32 windows): exact 631 (75.9%) + ambiguous 200 (24.1%) [multi_contributor 199, negative_remainder 1] + shrink 0 (0.0%): OK
exact: the interval's one token-relevant contributor (a tool_result or user text) after subtracting the previous call's output. Exact given the feed-forward model; bookkeeping attachments are folded into the single contributor's remainder.
```

```
python3 -m sa spend --since 7d --by agent --limit 3
```

```
spend: 14,626,322 input-side base-token-equivalents over 863 call facts in 32 windows; top agent=agent-a1 1,116,805 (11.3% of 9,858,904 with an agent)
single-call peak context_tokens over the 32 whole windows: 255,333 context tokens at -home-me-workspace-myproject/<session-id>.jsonl:807
spend is paid per call; context shares are not cost shares. What put the tokens there is answered by `sa context` (--by tool, --by head).
population: root ~/.claude/projects; 39 files read (modified within 7d), 32 windows, 863 call facts, 1693 increment facts; 0 lines skipped, 0 duplicate records excluded

by agent                  spend  calls  share of 9,858,904
agent-a1              1,116,805     68               11.3%
agent-b2              1,089,695     65               11.1%
agent-c3              1,007,906     71               10.2%
+20 more rows         6,644,499    412               67.4%
∅                     4,767,417    247                   -
∅: main windows (no subagent)

output_tokens: 212,917 tokens
cache_write_1h_tokens: 925,228 tokens
cache_write_5m_tokens: 2,728,855 tokens
```

Spend weights cache reads 0.1x, 5m writes 1.25x, 1h writes 2.0x; never
dollars. No estimated attribution (one `ambiguous` row, never a spread),
no summed peaks; a `MISMATCH` exits 1.

## The drill

```
python3 -m sa context --where cause=tool_result --by tool
python3 -m sa context --where tool=Bash --by head
python3 -m sa context --where cause=ambiguous --by fact --limit 2
```

`--where DIM=VALUE` (dims: project, session, agent, cause, tool, head,
reason) is repeatable and exact: on `project`/`session`/`agent` it keeps
whole windows; otherwise it drills and the footer shrinks to one line.
An undeclared value (`cause=bogus`) or one no fact carries (`tool=bash`)
exits 2, naming what is declared or present. `--limit N` folds the rest
into `+k more rows`. A head is a Bash call's first command word (keywords,
wrappers, builtins skipped) as a basename (`Bash:pytest`, `Bash:check.sh`)
or a file tool's extension (`Read:py`). The headline names the top row of
the first table shown, or of `--by`, with its mass and share base (`of
9,585,211 with an agent` when `∅` is excluded); never `window_head`. Table
columns: the metric, its `increments`/`calls`, `share of <base>`; the
residual `∅` row ends it, noted under `by tool`, `by head`, `by agent`.
`--by fact` lists the heaviest leaves as `<metric>  file:line  uuid
dimensions`; an ambiguous leaf lists its `candidates:` with cause, tool
and head.

## Layout

`python3 -m pytest tests/` runs synthetic fixtures and the privacy gate
(no real paths, ids or transcript text in tracked files). `sa/` is the
package, `skills/` and `.claude-plugin/` the plugin, `references/` the
design docs.

## License

MIT
