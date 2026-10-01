# claude-session-analyzer

Answers two questions about your Claude Code sessions, measured from the
JSONL transcripts under `~/.claude/projects`: **where is my context going?**
(`sa context`) and **what did it cost?** (`sa spend`). Every figure names
the population it was counted over, every table shows its residual, and the
`context` view ends with a reconciliation that proves the increments add up
to the windows' final occupancy. It is a Claude Code plugin whose skill
drives the CLI for you, and a plain `python3 -m sa` for your own terminal.
Standard library only, Python 3.8+.

## Install

```
claude plugin marketplace add reubenjohn/claude-session-analyzer
claude plugin install claude-session-analyzer@reubenjohn
```

(or `/plugin marketplace add reubenjohn/claude-session-analyzer` then
`/plugin install claude-session-analyzer@reubenjohn` inside Claude Code).
Update later with `claude plugin update claude-session-analyzer@reubenjohn`.
Once installed, ask Claude "where is my context going?" or "what did this
session cost?" and the `session-analyzer` skill runs the commands below.

## The two commands

From a clone, or from the installed plugin root:

```
python3 -m sa context --since 7d
```

```
context_delta: 1,733,257 context tokens; top cause=window_head 48.3%
population: 26 files read, 18 windows, 327 call facts, 635 increment facts; 0 lines skipped, 0 duplicate records dropped

by cause        context tokens    count   share
window_head            836,574       18   48.3%
tool_result            550,990      260   31.8%
ambiguous              172,800       29   10.0%
feed_forward           158,984      308    9.2%
user_text               13,909       20    0.8%

reconciliation over 18 windows: window_head 836,574 + feed_forward 158,984 + tool_result 550,990 + user_text 13,909 + ambiguous 172,800 + shrink 0 = 1,733,257; final occupancy 1,733,257: OK
intervals 309: exact 280 (90.6%), ambiguous 29 (9.4%) [multi_contributor 28, negative_remainder 1], shrink 0 (0.0%)
```

```
python3 -m sa spend --since 7d --by agent --limit 3
```

```
spend: 5,579,351 base-token-equivalents; top project=-home-me-workspace-myproject 43.6%
population: 26 files read, 18 windows, 332 call facts, 645 increment facts; 0 lines skipped, 0 duplicate records dropped

by agent           base-token-equivalents    count   share
main                      3,497,585      196   62.7%
a0ed59226a99bd981           920,382       71   16.5%
a588780b792ecfb89           222,054       11    4.0%

output_tokens: 166,147 tokens
cache_write_1h_tokens: 817,222 tokens
cache_write_5m_tokens: 691,010 tokens
context_tokens: largest single window 189,879 context tokens, in <file>
```

Spend is in base-token-equivalents (cache reads 0.1x, 5m writes 1.25x, 1h
writes 2.0x), never dollars. The footer's exact/ambiguous/shrink rates are
measured on every run, never hard-coded.

## The drill

Each step narrows the population; the last one lands on a transcript line.

```
python3 -m sa context --since 7d                                 # every table
python3 -m sa context --since 7d --by cause                      # one table
python3 -m sa context --since 7d --where cause=tool_result --by tool
python3 -m sa context --since 7d --where tool=Bash --by head     # first command word
python3 -m sa context --since 7d --where tool=Bash --where head=cat --by fact
```

Dimensions: `project`, `session`, `agent`, `cause`, `tool`, `head`,
`reason`, `candidate_count`. `--where` is repeatable; `--by fact` prints the
heaviest leaf facts with `file:line` and uuid. See `python3 -m sa context
--help` for the rest.

## What it refuses to do

No dollars, no estimated attribution (an interval with several candidate
contributors is one labelled `ambiguous` row, never a spread), and peaks are
never summed. A reconciliation `MISMATCH` exits 1.

## Tests

```
python3 -m pytest tests/
```

The suite runs on synthetic fixtures and includes the privacy gate (no real
paths, session ids or transcript text in tracked files); the pre-push hook
runs it.

## Layout

- `sa/` — the package: `corpus.py` (read, dedup), `walk.py` (calls,
  intervals, attribution), `schema.py` (the one metrics table), `query.py`
  (group, reconcile), `cli.py`, `usage.py` (measured usage corrections)
- `tests/` — fixtures and tests
- `skills/session-analyzer/` — the plugin skill that drives the CLI
- `.claude-plugin/` — plugin and marketplace manifests
- `references/` — design brief, decision log, measurement notes

## License

MIT
