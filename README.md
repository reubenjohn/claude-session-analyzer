# claude-session-analyzer

Reads your Claude Code transcripts (`~/.claude/projects`) and helps
answer two questions. **What did my sessions cost?** (`sa spend`):
each call pays for the context it sends, the cache deciding what is
paid again (reads discounted), so the calls' costs add up. Then, cost
aside (were inference free), **is context degrading the model?**
(`sa context`): every call reasons over its whole window, and a fuller
window reasons worse (context rot), so it shows what calls held (the
average context per call), what put it there, and a path to what to
cut. Both start broad and narrow down. Every figure names its
population; `context` reconciles. A Claude Code plugin or plain
`python3 -m sa`; stdlib, Python 3.8+.

## Install

```
claude plugin marketplace add reubenjohn/claude-session-analyzer
claude plugin install claude-session-analyzer@reubenjohn
```

## Usage

Is it a problem, what causes it, where, what exactly to fix:

```
python3 -m sa context                                       # average context per call, by peak
python3 -m sa context --where peak=200K+                    # what fills the fullest windows
python3 -m sa context --where peak=200K+ --where tool=Bash  # their top tool
python3 -m sa context --where peak=200K+ --where command=Bash:cat --by fact  # file:line
```

<!-- example: context | average context per call -->
```
average context per call* 84,709 tokens, over 21 calls in 3 windows
  starting context*  84,333  99.5%  = session starts 84,000 + forks 333
  growth                433   0.5%  from Bash 214 → Bash:pytest 214
→ next: add --where peak=200K+
```

<!-- example: context | by peak -->
```
by peak          part of avg  windows  calls  avg call  share of 84,766 before shrink
200K+                 83,811        1      7   251,376   98.9%
0-50K                    955        2     14     1,376    1.1%
shrink (signed)          -57        -      -         -       -
by session, project: the rows above, labelled sess-0002 / ~-work-lib, sess-0001 / ~-work-app
```

`--since 30d` or `--since all` widens the window; `python3 -m sa explain [TERM]`
says what a term means. `python3 -m sa spend --by subagent`:

<!-- example: spend --by subagent | by subagent -->
```
by subagent    spend  calls  share of 988 (all but unassigned)
agent-fake1      988      7  100.0%
unassigned*  176,976     14       -  main windows
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
started_by, peak, cause, tool, command, reason), repeatable, exact: the
first six keep whole windows (`window=<hex>` isolates one; `--by window`
lists them); the rest drill, named on the headline with the windows
hit; an absent value exits 2, naming what is present. A command is a Bash call's first command word
(`Bash:pytest`) or a file tool's extension (`Read:py`). Under the
average the headline's block gives the starting context by `started_by`,
then the growth: the top tool, `→` its largest command, then a larger
`top command` (`spend`: the top subagent, as `<type> <8 hex>`), whatever
`--by` shows, never a cause or window row; shares are of the average
before shrink. A pin omits what it implies; a table that
repeats the one above row for row prints as one line. `--limit` (5)
never folds the cause table, `unassigned` or a signed row. `--by fact` lists the
leaves, each its part of the average then its raw tokens, with
`file:line  uuid  dimensions`, an ambiguous one's `candidates:` under it.

On a terminal the output is styled (`--color always|never|auto`,
`NO_COLOR`, `FORCE_COLOR`); a pipe gets the same text, unstyled. A
row's figures are a heatmap of its share, green to red on a log scale
(bold from 25%), and each of the top two tools keeps one hue.

A window is one context window: from a session start, subagent, fork,
replay or compaction to its file's end or the next compaction. Its
`peak` is the band of its largest call: `0-50K`, `50-100K`, `100-200K`,
`200K+`, lower edge inclusive. The average context per call is what a
call held, averaged over the calls in view; never summed. Every
`context` figure is a part of it: each change times the calls that held
it, over the calls in view (a drill's too), so a table's rows add up to
it. A fork's copied context is one `inherited` change, held by the
fork's calls; with the parent missing (or out of
`--since`) or its branch call not found, the copy counts as the
fork's own; the scope says how many, and why.

## Layout

`sa/` the package, `skills/` and `.claude-plugin/` the plugin,
`references/` the design docs; tests: `python3 -m pytest tests/`.

## License

MIT
