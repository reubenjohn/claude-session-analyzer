# claude-session-analyzer

Answers two questions about your Claude Code sessions, read from the JSONL
transcripts under `~/.claude/projects`:

- **Where is my context going?** (`context_delta`)
- **What did it cost?** (`spend`)

**Status: build in progress.** Design rulings landed 2026-09-30 (see
[`references/DECISION_LOG.md`](references/DECISION_LOG.md)); the build is
under way on branch `v2-build`. Nothing is runnable yet.

## Layout

- `scripts/`: the ported engine (`sa_schema.py`, `lib/`) and measurement
  probes (`probes/`) that run against your local corpus
- `tests/`: a synthetic fixture generator and smoke tests (`pytest tests/`)
- `references/`: the design brief, decision log, competing designs, and
  measurement notes

## License

MIT
