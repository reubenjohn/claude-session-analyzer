# claude-session-analyzer

[![ci](https://github.com/reubenjohn/claude-session-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/reubenjohn/claude-session-analyzer/actions/workflows/ci.yml)
[![license](https://img.shields.io/github/license/reubenjohn/claude-session-analyzer)](LICENSE)
[![python](https://img.shields.io/badge/python-3.8%2B-blue)](pyproject.toml)

Reads your Claude Code transcripts (`~/.claude/projects`) and answers
two questions. **What did my sessions cost?** (`spend`): each call pays
for the context it sends, cache reads discounted. Cost aside, **is
context degrading the model?** (`context`): a fuller window reasons
worse (context rot), so it shows what an average call held and what put
it there. Stdlib only, Python 3.8+; every figure names its population.

## Install

```
pip install git+https://github.com/reubenjohn/claude-session-analyzer
```

Or as a Claude Code plugin (its skill runs the same commands):

```
claude plugin marketplace add reubenjohn/claude-session-analyzer
claude plugin install claude-session-analyzer@reubenjohn
```

## Use

```
python3 -m sa              # the guide: both questions, the grammar, examples
python3 -m sa context      # is context degrading the model? what fills it
python3 -m sa spend        # what did my sessions cost?
```

Each answers broadly first; its `→ next:` line is a command to paste
that narrows it, run by run, to something you can fix:

<!-- example: context | average context per call -->
```
average context per call* 84,709 tokens, over 21 calls in 3 windows
  starting context*      84,333  99.5%  = session_start 84,000 + fork 333
  growth before shrink*     433   0.5%  largest: Bash 214, of which Bash:pytest 214
→ next: python3 -m sa context tool=Bash
```

One grammar: `python3 -m sa spend|context [by DIM] [DIM=VALUE ...] [-v]`.

```
python3 -m sa context tool=Bash                # pin a row you saw: its commands
python3 -m sa context tool=Bash by change      # the changes, file:line
python3 -m sa context peak=200K+ tool=Bash     # all pins hold: Bash in the fullest
python3 -m sa context -v                       # how each figure is computed
```

A table's rows are the values you can pin (`DIM=VALUE`, as printed);
`by DIM` prints one table whole:

<!-- example: context by peak | by peak -->
```
by peak         part of avg  windows  calls  avg call  share
200K+                83,811        1      7   251,376   98.9%
0-50K                   955        2     14     1,376    1.1%
= 100%               84,766        3     21         -  shares' base: the rows above
shrink                  -57        -      -         -       -
= average call       84,709        3     21         -        ✓ = mean call size
```

`--since 30d` or `--since all` widens the window (default 7d).
`python3 -m sa spend by subagent`:

<!-- example: spend by subagent | by subagent -->
```
by subagent    spend  calls  share
agent-fake1      988      7  100.0%
= 100%           988      7  shares' base: the rows above, not the main row
main         176,976     14       -  = session_start 176,976
```

Spend weights cache reads 0.1x, writes 1.25x (5m) or 2x (1h); no
dollars. No estimated attribution (one `ambiguous` row, never a
spread), no summed peaks. The last line checks the arithmetic (`-v`
works it in your numbers); a failed check is a bug, exit 1.

## Pins and tables

`DIM=VALUE` pins (project, session, subagent, window, started_by, peak,
cause, tool, command, reason), repeatable: different dimensions AND.
The first six keep whole windows; the rest drill, the headline naming
the pin as a part of the average. Closed values match in any case or
by prefix (`peak=200k`), a session by any unique prefix; a catch-all
row pins by its label (`subagent=main`). A command is a Bash call's
first command word (`Bash:pytest`) or a file tool's extension
(`Read:py`). A mistake exits 2 in two lines: the nearest valid input,
and where the choices live.

A default table shows 5 rows, the rest folded into `+N more` and the
command that prints them; each ends with `= 100%`, its shares' base.
`shrink` (a window that got smaller) is signed, in no share. `by
change` (spend: `by call`) lists the facts, each with `calls held` and
its pins, then a Σ line reconciling to the headline.

A window is one context window: from a session start, subagent, fork,
replay or compaction to its file's end or the next compaction; its
`peak` is the band of its largest call (`0-50K` ... `200K+`). Every
`context` figure is a part of the average context per call: each change
times the calls that held it, over the calls in view. A fork's copied
context is one `inherited` change, held by the fork's calls.

## More

`CHANGELOG.md` the releases; `sa/` the package (each module's
docstring is its spec); `skills/`, `.claude-plugin/` the plugin;
`references/` the design. Tests: `python3 -m pytest`. License: MIT.
