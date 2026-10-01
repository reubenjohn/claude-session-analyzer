# claude-session-analyzer

Two questions about your Claude Code sessions, answered from the JSONL
transcripts under `~/.claude/projects`: **where is my context going?**
(`sa context`) and **what did it cost?** (`sa spend`). Every figure names
its population, and `context` ends with a reconciliation proving the
increments sum to the windows' final occupancy. A Claude Code plugin, or
plain `python3 -m sa`; standard library only, Python 3.8+.

## Install

```
claude plugin marketplace add reubenjohn/claude-session-analyzer
claude plugin install claude-session-analyzer@reubenjohn
```

(or `/plugin`).

## Usage

```
python3 -m sa context --since 7d --by cause
```

```
context_delta: 3,472,379 context tokens = the 30 windows' final occupancies summed; top cause=tool_result 1,190,872 (34.3%)
single-call peak context_tokens over the 30 whole windows: 237,966 context tokens at -home-me-workspace-myproject/<session-id>.jsonl:733
population: root ~/.claude/projects; 37 files read (modified within 7d), 30 windows, 770 call facts, 1509 increment facts; 0 lines skipped, 0 duplicate records excluded

by cause        context tokens    count  share of 3,472,379
window_head          1,253,541       30               36.1%
tool_result          1,190,872      554               34.3%
ambiguous              779,353      150               22.4%
feed_forward           198,359      739                5.7%
user_text               50,254       36                1.4%
window_head: first call's context: boot prompt + first message, or inherited parent context for a fork; not splittable by content

reconciliation over 30 windows: window_head 1,253,541 + feed_forward 198,359 + tool_result 1,190,872 + user_text 50,254 + ambiguous 779,353 + shrink 0 = 3,472,379; final occupancy 3,472,379: OK
intervals 740 (= 770 calls - 30 windows): exact 590 (79.7%) + ambiguous 150 (20.3%) [multi_contributor 149, negative_remainder 1] + shrink 0 (0.0%): OK
exact: the interval's one token-relevant contributor (a tool_result or user text) after subtracting the previous call's output. Exact given the feed-forward model; bookkeeping attachments are folded into the single contributor's remainder.
```

```
python3 -m sa spend --since 7d --by agent --limit 3
```

```
spend: 12,985,703 input-side base-token-equivalents over 770 call facts in 30 windows; top agent=agent-a1 1,116,805 (13.2% of 8,475,046 with an agent)
single-call peak context_tokens over the 30 whole windows: 237,966 context tokens at -home-me-workspace-myproject/<session-id>.jsonl:733
spend is paid per call; context shares are not cost shares. What put the tokens there is answered by `sa context` (--by tool, --by head).
population: root ~/.claude/projects; 37 files read (modified within 7d), 30 windows, 770 call facts, 1509 increment facts; 0 lines skipped, 0 duplicate records excluded

by agent       input-side base-token-equivalents    count  share of 8,475,046
agent-a1              1,116,805       68               13.2%
agent-b2              1,089,695       65               12.9%
agent-c3              1,007,906       71               11.9%
+18 more rows         5,260,640      328               62.1%
∅                     4,510,657      238                   -
∅: main windows (no subagent)

output_tokens: 205,711 tokens
cache_write_1h_tokens: 907,861 tokens
cache_write_5m_tokens: 2,304,525 tokens
```

Spend weights cache reads 0.1x, 5m writes 1.25x, 1h writes 2.0x; never
dollars. No estimated attribution (one `ambiguous` row, never a spread),
no summed peaks; a `MISMATCH` exits 1.

## The drill

```
python3 -m sa context
python3 -m sa context --where cause=tool_result --by tool
python3 -m sa context --where tool=Bash --by head
python3 -m sa context --where cause=ambiguous --by fact --limit 2
```

Dims: `project`, `session`, `agent`, `cause`, `tool`, `head`, `reason`.
`--where DIM=VALUE` is repeatable and exact: on
`project`/`session`/`agent` it keeps whole windows; otherwise it is a
drill and the footer shrinks to one line. An unknown dimension or value
(`--where cause=bogus`) is refused, exit 2, naming what is declared.
`--limit N` folds the rest into `+k more rows`. The headline
names the top row of the first table shown, or of `--by`, with its mass
and share base (`of 8,475,046 with an agent` when `∅` is excluded); never
`window_head`, and `--by fact` names none. Tables end with the residual
`∅` row, noted under `by tool`, `by head` and `by agent`. `--by fact`
lists the heaviest leaves as `tokens  file:line  uuid  dimensions` (no
`agent=` on a main-window leaf); an ambiguous leaf lists its
`candidates:` once, one line each with its own cause, tool and head, and
carries a tool only when all candidates share one.

## Layout

`python3 -m pytest tests/` runs synthetic fixtures and the privacy gate
(no real paths, session ids or transcript text in tracked files). `sa/`
is the package, `skills/` and `.claude-plugin/` the plugin, `references/`
the design docs.

## License

MIT
