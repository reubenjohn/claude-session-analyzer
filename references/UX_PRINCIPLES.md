# UX principles — binding on every screen the CLI prints and every file the repo holds

Ruled by the owner (D-UX-PRINCIPLES). Three principles; every UX rule, test and
grader finding is an INSTANCE of one. A rule met by breaking a principle is a
failure: a `values` subcommand makes values listable and breaks principle 1.
When two principles pull apart, name the tension; the owner rules.

**1. Learnable: one small model, and the screen is its manual.**
A newcomer learns a few nouns and verbs once; everything else comes from
combining them. Whatever the output names is valid input, verbatim.
- Values are the rows of the tables you already read; no listing command.
- A suggested next step pastes and runs as printed.
- A new command, flag or term must retire one.
- A mistake answers with the nearest valid input and where the choices live.

**2. Legible: attention is the budget.**
Make a thing self-evident before explaining it. Answer first; depth is one
obvious step away. Every piece of education is placed on purpose:
ALWAYS (needed to read this screen right), ON TRIGGER (the data makes it
relevant: a shrink, a pin, a large ambiguous share), ON REQUEST (the user's
question surfaces it).
- A composite row shows its parts; a share's base is visible on screen.
- Values keep their typable names; a gloss beside them, never a synonym.
- The glossary shrinking is progress; adding a term is a cost.

**3. Trustworthy: every number shows where it came from.**
Each figure names its population and can be walked down, by one uniform
step, to the facts it sums and its formula in the user's own numbers.
Nothing is hidden silently. Source code is the last rung, not the only one.
- Fact rows carry what a figure needs to be recomputed.
- Truncation says what it cut; negative rows and material uncertainty show.
- A ✓ is printed only over arithmetic that reconciles.

## Budgets — hard gates, not principles to weigh

Principles 1 and 3 add text; only 2 removes it. So 2 is enforced as fixed
per-screen budgets, measured by pytest. Budgets only shrink unless a ruling
raises one: new text is paid for by removing text.

| Screen | Budget |
|---|---|
| default `context`, `spend` (fixture and `tests/corpora.realistic`) | 46 lines, 3,228 chars (D-OUTPUT-CAP) |
| `-h` | 25 lines |
| one term's explanation | 6 lines |
| an error | 2 lines |
| any line | 100 columns |

Also measured, never grown without a ruling: lines repeated on every run,
coined terms per screen.

## The project is a screen too

The same three principles bind the repo: its files, modules and docs are
what the next agent or contributor reads.
1. Learnable: one concept lives in one place; `AGENTS.md` is the manual and
   every other file is reachable from it; modules compose (a stage takes
   facts and returns facts) rather than special-casing.
2. Legible: a file earns its place. Superseded proposals, feedback logs and
   one-off designs are folded into the ruling they produced, then deleted
   (git keeps them). File-size caps are budgets; fewer files is progress.
3. Trustworthy: every claim in a doc is pinned by a test or a dated
   measurement; a stale doc is a bug.

## Smell tests (how the owner reads a screen)
- "How would a user even know that?" It must be visible on screen, not in a doc.
- "That's a wall." More than one idea per line, or a block nobody reads.
- "That's a new concept." It must retire one; patches per complaint are rejected.
- "You're hiding it." Depth is an invitation: one announced, learnable step away.
  The curious user's details (how a number is checked) are what make the tool
  worth learning; lay them out to be learned, never cut them.
- "Is it a slide?" One message, then its evidence, then the way deeper.

## Tensions to expect
1 vs 3: fewer concepts vs a path to every figure.
2 vs 3: shorter screens vs completeness.

## Evaluating against them
Two personas, judged separately: HURRIED (minutes, skims, wants one lever)
and SCIENTIFIC (wants each figure's formula and population, reproduces it).
Score per principle, per persona, per journey; never one aggregate number.
Every finding cites its principle and quotes the output. Accounting
unchanged and every figure naming its population are hard gates.
