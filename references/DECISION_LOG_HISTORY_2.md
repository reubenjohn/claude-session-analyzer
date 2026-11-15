# session-analyzer v2 — decision log history, part 2: rows moved verbatim
out of `DECISION_LOG.md` (2026-11-15) to make room; the pointer line there
keeps each ruling's verdict.

**R5-BUILTINS — output-less shell builtins are skipped like keywords.**
RULED 2026-10-01, closing R5-BASENAME's logged gap: a loop body that opens
with a label (`for f in …; do echo "== $f"; cat "$f"; done`) had yielded
`Bash:echo`, although `echo` never produces the tokens the increment books.
Measured basis, live corpus (40 files, 32 windows, 2026-10-01, `--where
tool=Bash --by head`): before, `Bash:echo` carried 167,401 tokens over 23
increments (the #2 Bash head) and `Bash:cat` 238,494 over 37; after,
`Bash:echo` and `Bash:printf` (2,440) carry nothing and `Bash:cat` is
448,448 over 57 (48.0% of 935,044 with a head). One declared tuple in
`heads.py`, `BUILTINS = ("echo", "printf", "true", "false", "set",
"export", "unset", "shift")`: a builtin is skipped with its own arguments up
to the next separator, so the head is the next command word (`echo hi && pytest` ->
`Bash:pytest`, `printf '%s' x | sort` -> `Bash:sort`) and a command that is
only builtins yields `Bash:other`. The interpreter-plus-script gap
(`python3 scripts/x.py` -> `Bash:python3`) stays logged, not widened. Same
pass: a table's mass column is headed by the metric name
(`context_delta`, `spend`) rather than its unit, which the headline already
states once; spend's 33-character unit had overflowed the column and
misaligned `by agent`. Extended 2026-10-01 (fourteenth judge): the
principle is negligible output, not the builtin list, so a second declared
tuple `SILENT = ("mkdir", "touch", "mv", "cp", "rm", "chmod", "sleep",
"ln")` is skipped the same way (`mkdir -p x && cat > f <<EOF` ->
`Bash:cat`); measured basis, live corpus 2026-10-01: `Bash:mkdir` carried
59,586 context tokens over 13 increments, one increment of 23,390 tokens
that mkdir did not print. Amended 2026-10-01 (fifteenth judge): the
tokenizer is the standard library's `shlex` (posix; a run of `();|&` is
one word), so quoting is modelled (`echo "a; b"; make` -> `Bash:make`), a
nested `$(...)` collapses from the inside, and a builtin's arguments run to
the next separator, never a reserved word (`echo if x; make` ->
`Bash:make`); heredocs and function definitions are still not.

**D-HEADLINE-SPECIFIC — the headline names the most specific unpinned
table's top row as a share of the total.** RULED 2026-10-01, same judge.
`sa context` had led with "top cause=tool_result 33%", the "mostly tools"
category PURPOSE calls true and useless. Now the lead is the top regular
row of the most specific dimension shown that `--where` did not pin, in the
order head, tool, cause, agent, session, project — declared once as
`schema.DIMENSIONS` reversed, general to specific — so `sa context` leads
with "top head=Bash:cat 554,879 (13.2% of the 4,188,015 total)" and `sa
spend` with the top agent; `--by` still overrides. The share is of the
headline TOTAL, named "of the N total"; the table's own `share of <base>`
column stays over its base, so the two differ whenever a residual or
signed row exists and each names what it is over. Same pass, three fixes
the judge measured: `--where cause=shrink` had been refused ("no facts
carry cause=shrink") because the present values were read from a table's
regular rows, which file shrink as signed — they now come from the carrier
facts themselves, by descending |mass|, and the closed-vocabulary guard is
parametrized over EVERY declared value; `--by fact` sorted by signed mass,
so a shrink leaf fell last under `--limit` — now by |mass|; and
`heads.bash_head` treats a newline and either parenthesis as separators,
drops a bare separator, skips `timeout`'s options (`VALUED` take a
word) before its duration, skips a `[`…`]` / `[[`…`]]` test, and skips
`exit` as a builtin (`cd x || exit 1; make` is `Bash:make`, re-pinned).
AMENDED 2026-10-01, seventh judge: picking the lead by position had led
a subagent window (72% of its mass ambiguous, sharing a tool but no head)
with `head=Edit:py 19,214` while `tool=Bash` carried 99,422 below it.
Levers are declared per view (`render.View.levers`): context `tool` and
`head`, spend `agent`; never `cause` (categories) nor a window dimension
(local corpus, 46 files, 2026-10-01: the top project row is 81.0% of the
context total; on a window drill each window table's one row is 100%).
AMENDED (judge 8): `--by` had made its table the lever, so
`spend --by session` and `context --by window` led with a population row
and `--by cause` with a category. Now the headline is grouped from the
levers alone, whatever `--by` shows (`fact` too), and since a head row
can never exceed its tool row it walks down: the top tool with its share
of the total, then `within it` the top head when it lies under that tool
(a top head under another tool ends the walk); a pinned lever drops out.
AMENDED 2026-10-01, ninth judge: `within it head=Bash:cat 839,141
(15.4%)` was a share of the total that read as a share of Bash, and a
top head under another tool was silent. Now the refining clause is the
largest head of the top tool's facts, grouped once, with both bases
(`47.0% of Bash, 15.4% of the total`), and when the largest head overall
lies elsewhere it follows: `top head=Read:py N (x% of the total) under
tool=Read`. A `--where` pin omits every default table and lever whose
facts all share one value (a pinned head implies its tool, a pinned
window its agent, session and project; `--by` still prints on request).
Same pass: `cd` joined `BUILTINS` in place of its own branch (`cd -P /x
&& make` -> `Bash:make`; a lone `cd /x` -> `Bash:other`, like `echo
done`); `query.Selection` dropped the CLI's root, since and corpus,
which `cli` now hands to `render.population`.
