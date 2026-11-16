---
name: session-analyzer
description: Measures what Claude Code sessions cost and, cost aside, whether context degrades the model (context rot) and what fills it, from transcripts; use when the user asks "where is my context going", "is my context too big", "what did this session cost", "which subagent or tool was expensive".
---

# session-analyzer

Two questions from `~/.claude/projects`: what did it cost; then, cost
aside, is context degrading the model (every call reasons over its
whole window: context rot), what fills it, what to cut.

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m sa spend     # what did it cost
cd "${CLAUDE_PLUGIN_ROOT}" && python3 -m sa context   # cost aside: is context a problem
```

One grammar: `python3 -m sa spend|context [by DIM | by change | by call]
[DIM=VALUE ...] [-v] [--since Nd|all]`. Every screen ends with
`→ next: <command>`: paste it as printed.

| Word | Meaning |
|---|---|
| `DIM=VALUE` | a pin, repeatable, as a table prints the value; `project` `session` `subagent` `window` `started_by` `peak` keep whole windows; `cause` `tool` `command` `reason` drill |
| `by DIM` | that one table, every row (default screen: 5 rows, then `+N more` and its command) |
| `by change` / `by call` | the facts: one change (spend: call) per row, `file:line`, `calls held`, its pins, evidence under |
| `-v` | how this screen's figures are computed and what its `*` words mean |
| `--since 30d` | files modified in the last N days (default 7d; `all`: every file) |

## What each command answers

**`context`** books every change of a window's context with one
`cause`, and prints its `part of avg`: its tokens times the calls that
held it, over ALL calls in view, so a table's rows add up to the average
context per call. Causes: `starting_context` (what a window held at its
first call; a fork's copy is `inherited` apart), `replies` (Claude's
replies, tool-call inputs included), `tool_result`, `user_text`,
`ambiguous` (not traced to one source; `reason`: `several`, `less_than_reply`,
`unexplained`) and `shrink` (a window that got smaller, signed).

**`spend`** sums each call's price-weighted input tokens: uncached
input, cache writes (1h 2.0x, 5m 1.25x), cache reads 0.1x; output
apart (`-v`: `not in spend`). Context shares are not cost shares.

The `context` headline opens with `average context per call* N tokens,
over C calls in W windows` (what a call held; never summed, never "added
per call"), then the starting context by `started_by` and the `growth`:
`largest:` the top tool, `of which` its largest command. A drill pin's headline
says its part: `Bash: 214 of the 84,709-token average call, over 21
calls in 3 windows`, then its changes. A pin omits tables that would have one row.

## The path: is it a problem -> what -> where -> what to fix

```bash
python3 -m sa context                        # average, its tables
python3 -m sa context tool=Bash              # where: top tool, its commands
python3 -m sa context tool=Bash by change    # file:line
python3 -m sa context peak=200K+ tool=Bash   # all pins hold: Bash in the fullest
```

`by change` names the directory the files share once, then groups the
changes by window (its file under it, `window=`), each row
`part of avg  tokens  calls held  :line` and its dims as pins; an ambiguous
one's `candidates:` under it. It ends `Σ N changes: X tokens × calls held ÷ C
calls = Y ✓ the headline's Y`. A `command` is a Bash call's first
command word (`Bash:pytest`) or a file tool's extension (`Read:py`);
never a path. A mistake exits 2 in two lines, naming the nearest valid
input (`tool=bash`, `cause=reply`, `spend cause=replies`: calls carry
only window dims).

## Reading the output

The scope is `read:` (files, `--since`, root; lines skipped and
duplicates excluded when any: corpus-wide) and `in view where <window pins>:` (windows,
`changes` or `calls`). Quote both with a figure. Each table: the metric
(`part of avg`, `spend`), its count, `share`; `= 100%` is the base of the
shares; the catch-all row (`no tool`, `main`: facts lacking the
dimension) shows its parts; `shrink` is signed, in no share. The
`context` cause table ends `= average call  ✓ = mean call size`. The
default screen shows the cause, tool and command tables, then the
command for the rest (`by DIM`, `also by` the others) and for `-v`. Sessions print as 8 hex, like
subagents and windows; `session=` takes any unique prefix. The checks
say what is checked, in plain words, then the `ambiguous` share of the
average (what could not be traced); `-v` works them in this run's numbers:

<!-- example: context -v | ✓ numbers add up -->
```
✓ numbers add up over 3 windows in view: rows to the average call, changes to final window sizes
  each change's tokens × calls held         1,778,890
  ÷ calls in view                                  21
  = average call                               84,709  ✓ same as the mean measured call size
  tokens added 254,860 - tokens shrunk 300  = 254,560  ✓ same as the final window sizes
  18 calls after their window's first = 21 calls - 3 windows, counted (not tokens)
    = 6 (33.3%) one source + 9 (50.0%) ambiguous + 3 shrank  ✓
```

A material `ambiguous` (10%+ of the average) or `shrink` (1%+) gets a
`!` line with the command that shows it. A failure prints `MISMATCH` in
full, a bug in this tool, exit 1. A drill's checks name the whole
windows they apply to.

## Refusals

No dollars; no estimated attribution (one `ambiguous` row, never a
spread); no summed peaks.

## Answering a user

1. Run the matching command, narrowed (`--since`, `project=`,
   `session=`) to what was asked.
2. Report the headline, the scope lines and the checks line's rate.
3. Follow `→ next:` one step past the headline; name the heaviest change
   with its `file:line` (`by change`).
4. End with the action the numbers suggest, or say the attribution is too
   ambiguous (quote the rate).
