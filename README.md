# claude-session-analyzer

Answers two questions about your Claude Code sessions, read from the JSONL
transcripts under `~/.claude/projects`:

- **Where is my context going?** (`context_delta`)
- **What did it cost?** (`spend`)

**Status: design phase.** Nothing is ready to use yet. The rebuild is waiting
on design rulings; start with [`references/DESIGN_BRIEF.md`](references/DESIGN_BRIEF.md)
and [`references/DECISION_LOG.md`](references/DECISION_LOG.md).

## Layout

- `scripts/`: the ported engine (`sa_schema.py`, `lib/`) and measurement
  probes (`probes/`) that run against your local corpus
- `tests/`: a synthetic fixture generator and smoke tests (`pytest tests/`)
- `references/`: the design brief, decision log, competing designs, and
  measurement notes

## License

MIT
