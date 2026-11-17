"""The glossary: every term the output prints, in plain words, and why its
number might surprise. It drives ``-v`` (``notes``), the ``*`` markers
and a cause row's gloss; a test holds that every declared term has an
entry. It shrinking is progress (UX_PRINCIPLES 2).

A term is its internal key (``schema``'s spelling); ``PRINTED`` names the
few the output spells otherwise, and ``key_of`` accepts either. ``marked``
terms, the irreducible concepts, print with ``MARKER``. A ``meaning`` is
one sentence, read first; ``surprise`` holds the edge cases, read after.
"""
from typing import Dict, NamedTuple

from . import schema
from .schema import SchemaError

GROWTH = "growth"  # the headline's line for what the windows added after their start
AVERAGE = "average_context_per_call"  # the headline's level: what a call held, averaged
AVG_CALL = "avg_call"  # a window row's own average call size, beside its part of the average
# D-NO-VERDICT: where to start, in plain words; no measured rot threshold exists, so no number.
FULLEST = "Larger windows are where models are most likely to lose track, so start with the fullest band"
MARKER = "*"  # a footnote: the term is explained below
EXAMPLE_WINDOW = "window=1a2b3c4d"  # -v prints a window of the screen's own in its place (``notes.define``)
PROG = "python3 -m sa"  # the real invocation, wherever a runnable command prints

# The output's spelling of a key, where it differs: the column and the
# total say "context tokens", the counts "changes" and "calls", the call
# totals as spend's formula names them.
PRINTED = {schema.CONTEXT_DELTA: "context tokens", schema.CONTEXT_HELD: "part of avg", AVG_CALL: "avg call",
           schema.INCREMENT: schema.PLURAL[schema.INCREMENT],
           schema.CALL: schema.PLURAL[schema.CALL], "output_tokens": "output",
           "cache_write_1h_tokens": "1h cache writes", "cache_write_5m_tokens": "5m cache writes",
           "input_tokens": "uncached input", "cache_read_tokens": "cache reads"}


class Term(NamedTuple):
    meaning: str
    surprise: str
    marked: bool = False
    gloss: str = ""  # a cause's few words beside its row, where the line has room


GLOSSARY: Dict[str, Term] = {
    schema.WINDOW_DIM: Term(
        "one context window, from its start to its file's end or the next compaction",
        "it starts at a session start, subagent, fork, replay or compaction; pin one as %s;"
        " a file with no call is read but is no window" % EXAMPLE_WINDOW, True),
    schema.STARTED_BY_DIM: Term("what began the window: " + ", ".join(schema.STARTS),
                                "a compaction starts a new window in the same file; its starting"
                                " context re-counts the system prompt"),
    schema.PEAK_DIM: Term("how full the window got: the band its largest call's context fell in, "
                          + ", ".join(schema.BANDS) + " tokens (K = 1,000; a band includes its lower"
                          " edge, so 200,000 is 200K+)",
                          "a band of the window, not of a call: a 200K+ window's calls are"
                          " counted there from its first, small ones too. " + FULLEST),
    schema.FORK: Term("a window that began as a copy of another window's context: a forked"
                      " session or subagent, its file opening with the parent's records",
                      "the copy is one inherited change, held by the fork's calls; with the parent missing (deleted, or outside --since) or its"
                      " branch call not found, the copy counts as the fork's own, which the scope"
                      " warns of when the fork's file marks it one; an unmarked fork with its"
                      " parent missing reads as subagent_start, unwarned"),
    schema.REPLAYED: Term("a session that opens by repeating another's records (resumed or branched)",
                          "the repeated records count once, in the file that holds them first;"
                          " the copy is one inherited change; without that file it reads as a"
                          " session start, its copy its own, unwarned: only the parent shows it", True),
    schema.CALL: Term("one assistant message, its split records merged: what spend is read from",
                      "a message written as several records counts once"),
    schema.INCREMENT: Term("one change of a window's context, at its start or between two calls",
                           "the step between two calls can book two (the previous reply, then the"
                           " rest), so changes outnumber calls", True),
    schema.CONTEXT_DELTA: Term(
        "context tokens booked to what put them in a window; summed, they equal the"
        " windows' final sizes",
        "it is net: what a compaction or other shrink removed is not counted, so a window"
        " that grew to 700K and compacted to 70K reports 70K"),
    schema.SPEND: Term("a call's input tokens, each kind weighted by its price, as worked under the ✓",
                       "output excluded; every call re-reads its whole context, so spend grows with"
                       " context times calls; it is never quoted in dollars", True),
    AVERAGE: Term(
        "what a call held (its context size), averaged over the calls in view",
        "every context figure is a part of it: each change's tokens × calls held, over"
        " those calls, so a table's rows add up to it; not what a call added: every call re-reads"
        " its whole window, so long windows hold most calls; never summed across populations", True),
    schema.CONTEXT_HELD: Term(
        "a row's part of the average context per call, not its own average: its changes'"
        " tokens times the calls that held them (from the call each entered at to the window's"
        " end), over ALL the calls in view; a table's rows add up to the average",
        "a change early in a long window weighs most: every later call held it. Per call of"
        " this view only: never summed or compared with another view's, whose calls differ"),
    AVG_CALL: Term("a window row's own average call size: its calls' sizes over its own calls;"
                   " its part of avg divides the same tokens by every call in view instead",
                   "a mean: never summed, so a +N more row prints -; under a drill, of the whole"
                   " windows with a matching change"),
    schema.CONTEXT_TOKENS: Term("one call's context size: what it held; shown averaged over the"
                                " calls and as each window's peak band",
                                "never summed: a sum counts a token once per call that re-read it"),
    "output_tokens": Term("tokens the calls generated",
                          "the next call reads them back, as replies"),
    "input_tokens": Term("input tokens neither read from nor written to the prompt cache (billed ×1)",
                         "full price: ten times a cache read"),
    "cache_read_tokens": Term("tokens read back from the prompt cache (billed ×0.1)",
                              "a tenth of an uncached token's price"),
    "cache_write_1h_tokens": Term("tokens written to the 1-hour prompt cache (billed ×2.0)",
                                  "each call writes one cache tier only"),
    "cache_write_5m_tokens": Term("tokens written to the 5-minute prompt cache (billed ×1.25)",
                                  "each call writes one cache tier only"),
    schema.PROJECT_DIM: Term("the project directory the session ran in, path-encoded (/ as -),"
                             " home printed as ~",
                             "a long name widens its table"),
    schema.SESSION_DIM: Term("a session id: its main window and every subagent window",
                             "session= keeps the subagents too; window= isolates one"),
    schema.SUBAGENT_DIM: Term("a subagent: its type and the first 8 of its id where the transcripts"
                              " record the type, else its id; a pin takes either; a main window has none",
                              "main windows are the catch-all row of by subagent, main: pin them with subagent=main"),
    schema.CAUSE_DIM: Term("what kind of thing put the tokens in the context",
                           "starting_context is often the largest and cannot be split further"),
    schema.TOOL_DIM: Term("the tool whose result put the tokens there",
                          "context the model wrote or you typed has no tool: its row is no tool"),
    schema.COMMAND_DIM: Term("<tool>:<summary>: a Bash command's first command word (Bash:git) or"
                             " a file tool's file extension (Read:py)",
                             "never a path; python3 x.py is Bash:python3"),
    schema.REASON_DIM: Term("why a change is ambiguous", "only ambiguous changes have one"),
    schema.STARTING_CONTEXT: Term(
        "what a window held at its first call: system prompt, tools, CLAUDE.md, prompt",
        "not split by content: the transcript records no size per part; the lever is how many windows"
        " start (subagent_start is usually most) and what each loads",
        True, gloss="held at a window's first call"),
    schema.INHERITED: Term("what a fork or replayed window copied: its parent window's size at"
                           " the branch call",
                           "every fork call held it, so the average counts it per fork call, as the"
                           " parent's own calls count theirs; a row only when such a fork is in"
                           " view; its breakdown is the parent's up to that call", gloss="a fork's copy of its parent"),
    schema.REPLIES: Term("Claude's replies, tool-call inputs included, read back by the next call",
                         "it is what the model wrote, not what a tool returned",
                         gloss="Claude's replies, read back"),
    schema.TOOL_RESULT: Term("a tool's output, booked exactly to its tool and command",
                             "the part you can act on: pin it with tool=", gloss="tools' output"),
    schema.USER_TEXT: Term("text typed into the window (by you or a hook)",
                           "usually small: typing rarely fills a window", gloss="typed by you or a hook"),
    schema.AMBIGUOUS: Term(
        "growth between two calls not traced to one source, left undivided",
        ", ".join("%s (%s)" % r for r in ((schema.SEVERAL, "more than one entered"),
                                          (schema.LESS_THAN_REPLY, "grew by less than the previous call's reply"),
                                          (schema.UNEXPLAINED, "none did")))
        + "; never spread over them; it still names a tool when every candidate came from one;"
        " by change lists the candidates", True, gloss="not traced to one source"),
    schema.SHRINK: Term("a window that got smaller between two calls (often, not always, a compaction)",
                        "a negative row in no share: growth before shrink and each = 100% row leave it"
                        " out, so they exceed the average call by it; the checks count it", True,
                        gloss="the window got smaller; in no share"),
    schema.SEVERAL: Term("several results or texts entered between two calls",
                         "the tokens are not split between them"),
    schema.LESS_THAN_REPLY: Term("the window grew by less than the previous call's reply",
                                 "rare; the whole change stays ambiguous"),
    schema.UNEXPLAINED: Term("the context grew with nothing recorded to explain it",
                             "declared so it is labelled should it appear"),
    GROWTH: Term("what the windows added after their start: every change between two calls,"
                 " shrinks aside. Its line names its largest part, a tool, then (of which) the"
                 " largest command within that tool; '; top command' names a larger one elsewhere",
                 "its share is of the average before shrink, starting context included, so it often"
                 " looks small: it is the part a tool or command can cut"),
}

_KEYS = {printed: key for key, printed in PRINTED.items()}


def key_of(term: str) -> str:
    """The internal key of a term as printed or as keyed, marker stripped."""
    term = term.rstrip(MARKER)
    term = _KEYS.get(term, term)
    return term if term in GLOSSARY else term.replace(" ", "_")  # ``starting context`` as printed


def entry(term: str) -> Term:
    try:
        return GLOSSARY[key_of(term)]
    except KeyError:
        raise SchemaError("unknown term %r; known: %s"
                          % (term, ", ".join(PRINTED.get(t, t) for t in GLOSSARY)))


def printed(term: str) -> str:
    return PRINTED.get(term, term)


def marked(term: str) -> str:
    """The term as printed, with the marker when the glossary marks it."""
    entry = GLOSSARY.get(term)
    return printed(term) + MARKER if entry and entry.marked else printed(term)
