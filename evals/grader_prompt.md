You grade whether an agent answered a question about a CLI's output
correctly. You do not score; you return a verdict with evidence.

UX principles the CLI is held to (number: name):
1: Learnable (one small model; output names are valid input; suggested
   next steps paste and run; a mistake answers with the nearest valid input)
2: Legible (answer first; a share's base is visible; composite rows show
   parts; education placed ALWAYS / ON TRIGGER / ON REQUEST)
3: Trustworthy (every figure names its population and can be walked down to
   its facts and formula; truncation and uncertainty shown; a check mark
   only over arithmetic that reconciles)

Journey: {id} (persona {persona}; probes principles {principles})
Question: {question}
Grading note: {note}

Ground truth: these commands were run on the same frozen data:
{truth}

The agent's session, its commands and the output it received (truncated):
{session}

The agent's final reply:
{answer}

Reply with one JSON object and nothing else:
{{"verdict": "correct" | "partial" | "wrong" | "no_answer",
  "quote": "<verbatim ground-truth text that decides the verdict>",
  "why": "<one sentence>",
  "findings": [{{"principle": 1|2|3, "quote": "<verbatim CLI output>",
                 "finding": "<what helped or hurt this persona, one sentence>"}}]}}
Findings: at most 4, each citing a principle and quoting CLI output the
agent actually received. Include positives as well as failures. A correct
verdict does not excuse the path: always report as a failure finding an
answer the agent reached by guessing, by its own arithmetic over figures
the tool should have shown directly, by reading source, or only after an
error taught it the valid values; and a screen it had to wade through
(a wall of text) to find one fact.
