# Changelog

The version lives in `sa/__init__.py` (`python3 -m sa -h` prints it);
the plugin manifests match it, pinned by `tests/test_docs.py`.

## 2.0.0 (2026-11-16)

First release of v2, a rewrite; v1's numbers and commands do not carry over.

- **Two questions** from `~/.claude/projects`, read-only, stdlib, Python
  3.8+: `spend` (what did my sessions cost: price-weighted input tokens
  per call, cache reads 0.1x, writes 1.25x/2x, no dollars) and `context`
  (cost aside, is context degrading the model: the average context per
  call, split into starting context and the changes that grew it).
- **One grammar**: `python3 -m sa spend|context [by DIM] [DIM=VALUE ...]
  [-v] [--since Nd|all]`. Pins are the rows you read; `by DIM` prints a
  table whole; `by change` / `by call` lists the facts, `file:line`;
  `-v` explains the screen in your numbers. Every screen ends with a
  `→ next:` command that pastes and runs; a mistake exits 2 in two lines,
  naming the nearest valid input.
- **Checks**: every screen ends with its `✓` lines: rows add up to the
  headline, changes reconcile to the windows' final sizes. A failed
  check is a bug, exit 1. No estimated attribution (one `ambiguous`
  row), no summed peaks; transcripts are deduplicated across files.
- Install: `pip install` from GitHub (`python3 -m sa`, no console
  script), or the Claude Code plugin.
