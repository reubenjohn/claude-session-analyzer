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
python3 -m sa context --since 7d --by cause
```

```
context_delta: 3,872,684 context tokens = the 32 windows' final occupancies summed; top tool=Bash 1,049,312 (27.1% of the 3,872,684 total); within it head=Bash:cat 554,879 (52.9% of Bash, 14.3% of the total)
single-call peak context_tokens over the 32 whole windows: 255,333 context tokens at -home-me-workspace-myproject/<session-id>.jsonl:807
read: root ~/.claude/projects, 39 files (modified within 7d), 0 lines skipped, 0 duplicate records excluded
kept: 32 windows, 1,693 increment facts

by cause         context_delta  increments  share of 3,872,684
window_head          1,323,189          32               34.2%
tool_result          1,287,069         591               33.2%
ambiguous              998,551         200               25.8%
feed_forward           205,510         830                5.3%
user_text               58,365          40                1.5%
window_head: first call's context: boot prompt + first message, or context inherited from a parent (fork, resume or branch); not splittable by content
ambiguous: intervals not attributable to one contributor (by reason: multi_contributor, negative_remainder, no_contributor); never spread; --by fact lists them

reconciliation over 32 windows: window_head 1,323,189 + feed_forward 205,510 + tool_result 1,287,069 + user_text 58,365 + ambiguous 998,551 + shrink 0 = 3,872,684; final occupancy 3,872,684: OK; holds by construction (walk.py), so a mismatch is a bug in this tool
intervals 831 (= 863 calls - 32 windows): exact 631 (75.9%) + ambiguous 200 (24.1%) [multi_contributor 199, negative_remainder 1] + shrink 0 (0.0%): OK
exact: the interval's one token-relevant contributor (a tool_result or user text) after subtracting the previous call's output. Exact given the feed-forward model; bookkeeping attachments are folded into the single contributor's remainder.
```

```
python3 -m sa spend --since 7d --by agent --limit 3
```

```
spend: 14,626,322 input-side base-token-equivalents over 863 call facts in 32 windows; top agent=agent-a1 1,116,805 (7.6% of the 14,626,322 total)
single-call peak context_tokens over the 32 whole windows: 255,333 context tokens at -home-me-workspace-myproject/<session-id>.jsonl:807
spend is paid per call; context shares are not cost shares. What put the tokens there is answered by `sa context` (--by tool, --by head).
read: root ~/.claude/projects, 39 files (modified within 7d), 0 lines skipped, 0 duplicate records excluded
kept: 32 windows, 863 call facts

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

Spend weights cache reads 0.1x, 5m writes 1.25x, 1h writes 2x; never
dollars. No estimated attribution (one `ambiguous` row, never a spread),
no summed peaks; `MISMATCH` is a bug, exit 1.

## The drill

```
python3 -m sa context --where cause=tool_result --by tool
python3 -m sa context --where tool=Bash --by head
python3 -m sa context --where cause=ambiguous --by fact --limit 2
```

`--where DIM=VALUE` (dims: project, session, agent, window, cause, tool,
head, reason) is repeatable, exact: on the first four it keeps whole
windows (`window`, a root-relative file name, isolates a main window);
otherwise it drills, named on the headline with the windows hit. `cause=bogus` (undeclared) or `tool=bash` (absent)
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
