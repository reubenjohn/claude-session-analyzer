# Agent evals: can a cold agent learn `sa` from its output alone?

Implements "Evaluating against them" in `references/UX_PRINCIPLES.md`: two
personas, findings per journey and per principle, never one aggregate score.

```sh
python3 scripts/agent_eval.py --label try1 --dry-run          # build, print commands
python3 scripts/agent_eval.py --label try1 --tasks top-filler --personas hurried
python3 scripts/agent_eval.py --label try2 --baseline evals/runs/<date>-try1
python3 scripts/agent_eval.py --label final --include-held-out --rev HEAD
```

Results land in `evals/runs/<date>-<label>/` (gitignored: they hold real
transcript output): `scorecard.md`, `results.json`, `truth.json`, and per
run `<persona>-<journey>-rN.jsonl` (transcript), `.sa.jsonl` (what the CLI
printed) and `.grade.json`. `--repeat N` runs each cell N times, shown side
by side, never averaged. The temp dir is deleted at the end unless `--keep`.

## How a run works

1. A temp dir outside the repo, so no project AGENTS.md/CLAUDE.md loads.
   `claude -p` also runs with no setting sources, MCP, skills or saved session.
2. A frozen snapshot: `~/.claude/projects` files modified in `--days`
   (default 7), copied with their mtimes into the temp dir. Eval runs' own
   `claude -p` transcripts land in `~/.claude/projects` too, as temp-dir
   projects (`-tmp-sa-...`); the snapshot skips every `-tmp-` project.
3. `bin/python3` routes `python3 -m sa` to `sa_wrapper.py`, which runs the
   real CLI on the snapshot, adding `--root` where the CLI's own help says it
   goes, and logs each invocation's argv, exit, lines and width as PRINTED,
   before any pipe the agent adds. (`bin/sa` is the same, for truth commands.)
   `--rev REV` runs the package from a git worktree of REV (for when the
   tree is mid-rewrite).
4. The agent may use only Bash(`python3 -m sa ...`; pipes allowed) and Read.
   Its prompt (`agent_prompt.md` + `personas/*.md`) says only that the
   command analyzes
   Claude Code transcripts: no flags, subcommands or help hints. Reading
   source is discouraged, not blocked, and measured.
5. Each task's `truth` commands run once on the snapshot; a grader
   `claude -p` (`grader_prompt.md`) sees the question, the agent's session
   and reply, and that output, and returns a verdict with a quote plus
   findings, each citing a principle. No score.

## Auditing the screens yourself

`python3 scripts/screens.py [--root DIR] [--since all]` prints every screen
an audit reads (bare, `-h`, both defaults, a pin, a table, `by change`,
`-v`, three refusals), each as `===== $ cmd`, its output and `[exit N]`.
Read it line by line before and after a change; the eval finds what you miss.

## Measures (per persona x journey, side by side, never summed)

verdict; first command and what the agent saw; sa commands; how many the
agent piped or redirected; error exits; permission denials; source reads
(Read on `sa/`, with the journey that drove it); and, from the wrapper log,
most lines and widest line printed and gate failures (a line over 100
columns, an error over 2 lines, `-h` over 25 lines, MISMATCH, exit 1);
turns, seconds, dollars; the agent's own FRICTION quotes.
`--baseline` adds a regressions table: each measure that got worse, with its
paired measure (commands vs verdict, ...) next to it.

## Tasks (`tasks.json`)

`id`, `personas`, `principles` (1 Learnable, 2 Legible, 3 Trustworthy),
`question` (grammar-agnostic unless `gives_command`), `truth` (sa commands:
update them when the grammar changes), `note` for the grader. Three are
`held_out`: never iterate the design against them; run them only for final
checks (`--include-held-out`, or name them in `--tasks`).
`tests/test_agent_eval.py` checks these files without calling claude.
