# claude-session-analyzer

Two questions about your Claude Code sessions, from the JSONL
transcripts under `~/.claude/projects`: **where is my context going?**
(`sa context`) and **what did it cost?** (`sa spend`). Every figure names
its population; `context` reconciles: the increments sum to the final
occupancy. A Claude Code plugin or plain `python3 -m sa`; stdlib,
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
read: 4 files modified in the last 7d (default) under ~/.claude/projects
      0 lines skipped, 0 duplicate records excluded
kept: 3 windows°, 33 increment facts

context_delta: 4,560 context tokens = the 3 windows' final occupancies summed
  starting context 3,000 (61.7% of the 4,860 added) entered as windows started, not a window size: session_start 2,000, fork 1,000
  growth 1,860 (38.3% of the added); top tool=Bash 750 (15.4% of the added); within it head=Bash:pytest 750 (100.0% of Bash, 15.4% of the added)
single-call peak context_tokens over the 3 whole windows: 1,520 context tokens at ~-work-app/sess-0001.jsonl:14

by cause            context_delta  increments  share of 4,860 added
window_head                 3,000           3                 61.7%
tool_result                   750           3                 15.4%
ambiguous                     606           9                 12.5%
user_text                     255           3                  5.2%
feed_forward                  249          12                  5.1%
shrink (signed)              -300           3                     -
= total                     4,560          33  ✓ matches the final window sizes

key (°: sa explain TERM)
  window_head°   the context a window's first call already had, less what it inherited: system prompt, tools, CLAUDE.md and first message, or a compaction's summary
  ambiguous°     an interval not booked to one contributor: more than one entered, none did, or it grew by less than the previous call's output; never spread over them (by reason: multi_contributor, negative_remainder, no_contributor)

✓ checks: 18 intervals (21 calls - 3 windows) = exact 6 (33.3%) + ambiguous 9 (50.0%) + shrink 3 (16.7%)
```

`--since 30d` or `--since all` widens the window; `sa explain [TERM]`
says what a term means. `python3 -m sa spend --by agent`:

<!-- example: spend --by agent | by agent -->
```
by agent                spend  calls  share of 988 with an agent
agent-fake1               988      7                      100.0%
∅                       1,976     14                           -
```

Spend weights cache reads 0.1x, 5m writes 1.25x, 1h writes 2x; never
dollars. No estimated attribution (one `ambiguous` row, never a spread),
no summed peaks; a failed check is a bug, exit 1.

## The drill

```
python3 -m sa context --where cause=tool_result --by tool
python3 -m sa context --where tool=Bash --by head
python3 -m sa context --where cause=ambiguous --by fact --limit 2
```

`--where DIM=VALUE` (project, session, agent, window, start, cause,
tool, head, reason) repeats, exact: on the first five it keeps whole
windows (`window=<hex>` isolates one; `--by window` lists them);
otherwise it drills, named on the headline with the windows hit. `cause=bogus` or `tool=bash` (absent)
exits 2, naming what is declared or present. A head is a Bash call's
first command word (`Bash:pytest`) or a file tool's extension
(`Read:py`). The headline names the top tool with its share of the
total, `within it` that tool's largest head (share of the tool and of
the total), then a larger head `under` another tool (`spend`: the top
agent), whatever `--by` shows, never a cause or window row; a pin
omits what it implies. `--by fact` lists the leaves
with `file:line  uuid  dimensions`, an ambiguous one's `candidates:`
under it.

A window is one context window: from a session start, subagent, fork,
replay or compaction to its file's end or the next compaction. A fork's
copied context is one `inherited` increment, left out of the total when
its parent window is kept.

## Layout

`sa/` the package, `skills/` and `.claude-plugin/` the plugin,
`references/` the design docs; tests: `python3 -m pytest tests/`.

## License

MIT
