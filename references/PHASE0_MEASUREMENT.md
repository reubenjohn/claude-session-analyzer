# Phase 0 measurement: does the raw corpus support attribution joins?

**Question.** v1's data model cannot do attribution because (a) a generation
fact's locator is a single index with no end and no constituent list, and (b)
0 of its 5,911 tool_result facts carry a tool_use_id even though all 5,911
tool_calls do. Hypothesis: the raw transcripts DO carry the join keys and v1
loses them at parse time.

**Verdict: the hypothesis holds. Yes — parse-time joins can be exact.**
Every join key the raw data needs for attribution is present at 100% on the
populations below. What v1 lost, it lost by dropping fields, not because the
data lacks them.

**Population.** Every `*.jsonl` under the corpus root (computed at runtime as
`Path.home()/".claude"/"projects"`), measured 2026-07-28 by
`scripts/probes/probe_attribution_join.py`: **1,845 files, 228,738 parsed
records, 2 unparseable lines skipped, 0 blank lines**. This is one machine's
full live corpus, not a sample. Record counts by type and every uuid-presence
figure below come from a companion sweep over the same 1,845 files. No file
mixes assistant records from more than one `agentId` (0 of 1,845).

## 1. tool_result linkage — 100.00% / 100.00%

Population: all 59,740 tool_result content blocks in all parsed records.

- Carry a `tool_use_id`: **59,740 / 59,740 = 100.00%**.
- That id matches a `tool_use` block seen **earlier in the same file**:
  **59,740 / 59,740 = 100.00%**.

The tool_result→tool_call join is total and needs no fallback path. v1's
0-of-5,911 is entirely a parse-time loss.

## 2. Generation shape — a [start,end) span works over assistant records

Population: all 53,855 distinct `message.id` values on assistant records,
grouped per file (an id was never observed spanning files, but this sweep
grouped within-file only — cross-file id reuse is **unverified**).

- Contiguous run over the **assistant-record subsequence**:
  **53,771 / 53,855 = 99.84%** (84 exceptions — interleaved generations).
- Contiguous run over **all parsed records**: 46,608 / 53,855 = 86.54%; the
  gap is metadata records (attachments, mode changes, queue operations)
  landing physically inside a generation's run of lines.
- Split over more than one record: 42,036 / 53,855 = **78.05%** — same order
  as the 80.5% in `lib_usage.max_merge_usage`'s docstring (different
  population: that one was 46,955 ids on an older corpus). Max-merge remains
  mandatory.

Design consequence: a generation locator can be a `[start,end)` span over the
file's **assistant-record sequence** (99.84% exact), or over raw record
indices with the caveat that the span may contain non-constituent metadata
records — so a span plus a constituent-uuid list is the lossless form. A
single index with no end, v1's form, cannot express 78% of generations.

## 3. Interval contributors — 84.43% have exactly one

Population: **51,933 intervals** between consecutive usage-carrying calls
(assistant records whose `message.usage` has any nonzero token field;
adjacent records sharing one `message.id` collapse into one call) from
53,745 calls in the 1,812 files with at least one call.

| Non-assistant records between calls | Share of intervals |
|---|---|
| 0 | 0 / 51,933 = 0.00% |
| 1 | 43,847 / 51,933 = **84.43%** |
| 2 | 1,652 / 51,933 = 3.18% |
| 3 | 2,097 / 51,933 = 4.04% |
| 4 | 400 / 51,933 = 0.77% |
| 5+ | 3,937 / 51,933 = 7.58% |

ENGINE_CONTRACT's "~77% of intervals have exactly one contributor" reproduces
at the same order of magnitude (84.43% here; different corpus snapshot and a
possibly different interval/contributor definition, so exact agreement was
not expected). Zero intervals are empty: every usage delta has at least one
candidate cause on this corpus.

Contributor kinds over all between-records (population: all records strictly
between consecutive calls, including 169 usage-less assistant records that
are excluded from the per-interval counts above): tool_result-bearing user
records 50,407; metadata (attachment 11,376, queue-operation 6,666, system
3,788, last-prompt 2,924, mode 2,860, ai-title 2,674, permission-mode 997,
file-history-snapshot 684); plain user text 3,489; types outside the known
set 1,310.

## 4. Identifiability — 100% of token-relevant contributors

Population: the 87,175 non-assistant contributor records from (3).

- Identifiable (uuid present + known type + every tool_use_id resolvable to
  an earlier tool_use in the file): **69,060 / 87,175 = 79.22%**.
- **Every failure is a uuid-less metadata record** (18,115 lack uuid, of
  which 1,310 are also types outside the probe's known set — agent-name,
  custom-title, file-history-delta, pr-link, bridge-session, relocated,
  worktree-state, agent-setting, started, result). Zero failures were
  `tool_use_id_unresolvable`.
- The companion sweep confirms the split is clean: **0 / 65,470 user
  records, 0 / 124,498 assistant records, 0 / 4,236 system records, and
  0 / 14,634 attachment records lack a uuid**; every uuid-less type is
  pure bookkeeping that carries no tokens. Therefore every conversational
  contributor (tool_result user record or user text) in (3) is identifiable
  — derived from those two total counts, not separately instrumented.
- Intervals with exactly one contributor **and** that contributor
  identifiable: 43,847 / 51,933 = **84.43%** — identical to the
  exactly-one rate; identifiability never subtracts from it.

## 5. Identity traps (owner-flagged shapes, same 1,845-file population)

- Embedded `sessionId` set excludes the filename stem in **1,587 / 1,844
  files with any sessionId = 86.06%** — but this decomposes completely:
  1,588 files have **non-UUID filename stems** (sidechain/agent transcript
  files; 1,586 of the 1,587 mismatching ones have `agentId` on every
  assistant record) and carry the *parent* session's id, while **0 of the
  257 UUID-stem session files** mismatch. The curated adversary shape — a
  session file whose embedded id differs from its filename id — was **not
  reproduced in the current corpus** (unverified whether that session aged
  out or the shape is version-gated); the trap that IS live everywhere is
  that a filename is not a session id for 86% of files, and sessionId groups
  a forest, not a file.
- Duplicate uuid occurrences **within** a file: 395 / 208,816 uuid-bearing
  records = 0.19%. Within-file dedup by uuid is needed but cheap.
- uuids appearing in **more than one** file: 2,767 / 205,003 distinct uuids
  = **1.35%** — resumed/forked sessions replay records, so forest-level
  aggregation without cross-file dedup double-counts. (Whether the replayed
  copies carry identical usage is **unverified** here; v1's 94% inflation
  figure is the motivating claim, not this probe's measurement.)

## What a data-model designer must know about raw shape

- `message.content` is a string on some user records and a block list on
  others; both occur routinely.
- 21 record types exist in the wild, most undocumented bookkeeping
  (queue-operation, last-prompt, ai-title, mode, agent-name, pr-link, ...);
  only user/assistant/system/attachment carry uuids. A parser must tolerate
  unknown types without dying and without granting them identity.
- Metadata records interleave *inside* a generation's physical run of lines
  (drops all-records contiguity to 86.54%), so spans must be defined over a
  filtered sequence or carry constituent lists.
- Sidechain files (non-UUID stems, 1,588 of 1,845 files) embed the parent's
  sessionId; filename identity and session identity diverge by design.
- 2 unparseable lines exist even in a healthy corpus; skip-and-count is the
  right posture. Physical line numbers survive skipping only if recorded at
  read time.

All figures above were measured on this one machine's corpus on 2026-07-28
and are expected to drift with Claude Code versions; re-run the probe rather
than quoting these numbers for a future corpus.
