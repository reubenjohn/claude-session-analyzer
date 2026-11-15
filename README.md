# claude-session-analyzer

Two questions about your Claude Code sessions, from the JSONL
transcripts under `~/.claude/projects`: **where is my context going?**
(`sa context`) and **what did it cost?** (`sa spend`). Every figure names
its population; `context` reconciles: the changes sum to the windows'
final sizes. A Claude Code plugin or plain `python3 -m sa`; stdlib,
Python 3.8+.

## Install

```
claude plugin marketplace add reubenjohn/claude-session-analyzer
claude plugin install claude-session-analyzer@reubenjohn
```

## Usage

```
python3 -m sa context --by cause
```

<!-- example: context --by cause -->
```
read: 4 files modified in the last 7d (default) under ~/.claude/projects, 0 lines skipped, 0 duplicates excluded
in view: 3 windows°, 33 changes

context tokens: 4,560 = the 3 windows' final sizes summed (% of the 4,860 added)
  starting_context° 3,000 (61.7%) at window start: session_start 2,000, fork 1,000
  growth 1,860 (38.3%): tool=Bash 750 (15.4%), command=Bash:pytest 750 (100.0% of Bash, 15.4%)
largest single-call context 1,520 tokens (of 3 windows), window=aadeccf6

by cause          context tokens  changes  share of 4,860 added
starting_context           3,000        3   61.7%
tool_result                  750        3   15.4%
ambiguous                    606        9   12.5%
user_text                    255        3    5.2%
replies                      249       12    5.1%
shrink (signed)             -300        3       -
= total                    4,560       33  ✓ = final window sizes

key (°: sa explain TERM)
  starting_context° already in the first call, not assigned to any tool
  ambiguous°        growth with no one contributor, left undivided

✓ checks: 18 gaps between calls (21 calls - 3 windows): 6 exact (33.3%), 9 ambiguous (50.0%), 3 shrink (16.7%)
```

`--since 30d` or `--since all` widens the window; `sa explain [TERM]`
says what a term means. `python3 -m sa spend --by subagent`:

<!-- example: spend --by subagent | by subagent -->
```
by subagent  spend  calls  share of 988 (all but ∅)
agent-fake1    988      7  100.0%
∅            1,976     14       -
```

Spend weights cache reads 0.1x, 5m writes 1.25x, 1h writes 2x; never
dollars. No estimated attribution (one `ambiguous` row, never a spread),
no summed peaks; a failed check is a bug, exit 1.

## The drill

```
python3 -m sa context --where cause=tool_result --by tool
python3 -m sa context --where tool=Bash --by command
python3 -m sa context --where cause=ambiguous --by fact --limit 2
```

`--where DIM=VALUE` pins (project, session, subagent, window,
started_by, cause, tool, command, reason), repeatable, exact: the first
five keep whole windows (`window=<hex>` isolates one; `--by window`
lists them); the rest drill, named on the headline with the windows
hit. `cause=bogus` or `tool=bash` (absent) exits 2, naming what is
declared or present. A command is a Bash call's first command word
(`Bash:pytest`) or a file tool's extension (`Read:py`). Under one total
the headline gives the starting context by `started_by` (what entered,
not a window size), then the growth: the top tool, its largest command
(`of Bash`), then a larger command `under` another tool (`spend`: the
top subagent), whatever `--by` shows, never a cause or window row;
shares are of the mass added. A pin omits what it implies; a table that
repeats the one above row for row prints as one line. `--limit` (5)
never folds the cause table, `∅` or a signed row. `--by fact` lists the
leaves with `file:line  uuid  dimensions`, an ambiguous one's
`candidates:` under it.

On a terminal the output is styled (`--color always|never|auto`,
`NO_COLOR`, `FORCE_COLOR`); a pipe gets the same text, unstyled. Each
of the top three tools keeps one hue wherever it prints.

A window is one context window: from a session start, subagent, fork,
replay or compaction to its file's end or the next compaction. A fork's
copied context is one `inherited` change, left out of the total when
its parent window is kept.

## Layout

`sa/` the package, `skills/` and `.claude-plugin/` the plugin,
`references/` the design docs; tests: `python3 -m pytest tests/`.

## License

MIT
