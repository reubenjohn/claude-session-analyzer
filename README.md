# claude-session-analyzer

Answers two questions about your Claude Code sessions from the JSONL
transcripts under `~/.claude/projects`: **where is my context going?**
(`sa context`) and **what did it cost?** (`sa spend`). Every figure names
its population, every table shows its residual, and `context` ends with a
reconciliation proving the increments add up to the windows' final
occupancy. A Claude Code plugin whose skill drives the CLI, and a plain
`python3 -m sa` for your terminal. Standard library only, Python 3.8+.

## Install

```
claude plugin marketplace add reubenjohn/claude-session-analyzer
claude plugin install claude-session-analyzer@reubenjohn
```

(or the same two `/plugin ...` commands inside Claude Code; update with
`claude plugin update claude-session-analyzer@reubenjohn`). Then ask Claude
"where is my context going?" and the skill runs the commands below.

## The two commands

From a clone or the plugin root:

```
python3 -m sa context --since 7d --by cause
```

```
context_delta: 2,103,920 context tokens = the 21 windows' final occupancies summed; top cause=window_head 44.7%
population: 28 files read (modified within 7d), 21 windows, 396 call facts, 770 increment facts; 0 lines skipped, 0 duplicate records excluded

by cause        context tokens    count  share of 2,103,920
window_head            941,138       21               44.7%
tool_result            507,658      271               24.1%
ambiguous              463,859       81               22.0%
feed_forward           170,223      374                8.1%
user_text               21,042       23                1.0%

reconciliation over 21 windows: window_head 941,138 + feed_forward 170,223 + tool_result 507,658 + user_text 21,042 + ambiguous 463,859 + shrink 0 = 2,103,920; final occupancy 2,103,920: OK
intervals 375 (= 396 calls - 21 windows): exact 294 (78.4%) + ambiguous 81 (21.6%) [multi_contributor 80, negative_remainder 1] + shrink 0 (0.0%): OK
exact: the interval's one token-relevant contributor (a tool_result or user text) after subtracting the previous call's output; bookkeeping attachments in the interval fold into its remainder [OPEN]
```

```
python3 -m sa spend --since 7d --by agent --limit 3
```

```
spend: 6,625,987 input-side base-token-equivalents over 396 call facts in 21 windows; top project=-home-me-workspace-myproject 52.5%
population: 28 files read (modified within 7d), 21 windows, 396 call facts, 770 increment facts; 0 lines skipped, 0 duplicate records excluded

by agent           input-side base-token-equivalents    count  share of 6,625,987
main                      3,694,708      205               55.8%
a0ed59226a99bd981           920,382       71               13.9%
aae4c61e9c6679977           498,293       29                7.5%
+10 more rows             1,512,604       91               22.8%

output_tokens: 177,276 tokens
cache_write_1h_tokens: 842,768 tokens
cache_write_5m_tokens: 960,399 tokens
context_tokens: largest single call 189,879 context tokens, at ~/.claude/projects/-home-me-workspace-myproject/<session-id>.jsonl:477
```

Spend is input-side base-token-equivalents (cache reads 0.1x, 5m writes
1.25x, 1h writes 2.0x), never dollars. Footer rates are measured per run,
never hard-coded.

## The drill

Each step narrows the population; the last lands on a transcript line.

```
python3 -m sa context                           # every table
python3 -m sa context --by cause                # one table
python3 -m sa context --where cause=tool_result --by tool
python3 -m sa context --where tool=Bash --by head   # first command word
python3 -m sa context --where tool=Bash --where head=cat --by fact
```

Dimensions: `project`, `session`, `agent`, `cause`, `tool`, `head`,
`reason`, `candidate_count`. `--where DIM=VALUE` is repeatable and exact
(after dedup): on `project`/`session`/`agent` it keeps whole windows; on
any other it is a drill, the footer becomes a one-line note, and a
dimension the view's facts never carry (`spend --where cause=...`) is
refused with exit 2. `--since Nd` is the only file-level pre-filter
(modification time). `--by fact` lists the heaviest leaf facts with
`file:line` and uuid; `--limit N` folds the rest into `+k more rows`.

## What it refuses to do

No dollars, no estimated attribution (an interval with several candidates
is one `ambiguous` row, never a spread), and peaks are never summed. A
reconciliation `MISMATCH` exits 1.

## Tests

```
python3 -m pytest tests/
```

Synthetic fixtures plus the privacy gate (no real paths, session ids or
transcript text in tracked files).

## Layout

- `sa/` — `corpus.py` (read, dedup), `walk.py` (calls, intervals,
  attribution), `schema.py` (the metrics table), `query.py` (group,
  reconcile), `cli.py`, `usage.py` (usage corrections)
- `tests/` — fixtures and tests
- `skills/session-analyzer/` — the plugin skill; `.claude-plugin/` — manifests
- `references/` — design brief, decision log, measurements

## License

MIT
