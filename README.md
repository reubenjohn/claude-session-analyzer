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

```
read: 9 files modified in the last 7d (default) under ~/.claude/projects
      0 lines skipped, 0 duplicate records excluded
kept: 8 windows° (files with a call), 471 increment facts

context_delta: 793,922 context tokens = the 8 windows' final occupancies summed
  top tool=Bash 223,025 (28.1% of the 793,922 total)
  within it head=Bash:git 50,904 (22.8% of Bash, 6.4% of the total)
single-call peak context_tokens over the 8 whole windows: 164,074 context tokens at -home-me-workspace-myproject/<session-id>.jsonl:247

by cause         context_delta  increments  share of total
window_head            335,056           8           42.2%
tool_result            211,715         183           26.7%
feed_forward           168,046         231           21.2%
ambiguous               72,972          26            9.2%
user_text                6,133          23            0.8%
= total                793,922         471  ✓ matches the final window sizes

key (°: sa explain TERM)
  window_head°   the context a window's first call already had: system prompt, tools, CLAUDE.md and first message, or the context a fork or resume inherited
  ambiguous°     an interval whose tokens more than one contributor (or none) could have put there; never spread over them (by reason: multi_contributor, negative_remainder, no_contributor)

✓ checks: 232 intervals (240 calls - 8 windows) = exact 206 (88.8%) + ambiguous 26 (11.2%) + shrink 0 (0.0%)
```

`--since 30d` or `--since all` widens the window; `sa explain [TERM]`
says what a term means. `python3 -m sa spend --by agent --limit 3`:

```
by agent                spend  calls  share of 1,615,785 with an agent
agent-a1              672,796     42                             41.6%
agent-b2              581,118     55                             36.0%
agent-c3              255,305     21                             15.8%
+1 more row           106,566      8                              6.6%
∅                   1,674,748    116                                 -
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

`--where DIM=VALUE` (project, session, agent, window, cause, tool,
head, reason) repeats, exact: on the first four it keeps whole
windows (`window`, a root-relative file name, isolates a main window);
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

## Layout

`sa/` the package, `skills/` and `.claude-plugin/` the plugin,
`references/` the design docs; tests: `python3 -m pytest tests/`.

## License

MIT
