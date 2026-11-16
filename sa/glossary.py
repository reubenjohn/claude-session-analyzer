"""The glossary: every term the output prints, in plain words, and why its
number might surprise. It drives ``sa explain``, the key
under the tables, the ``*`` markers and ``--help``; a test holds that every
declared term has an entry.

A term is its internal key (``schema``'s spelling); ``PRINTED`` names the
few the output spells otherwise, and ``explain`` accepts either. ``marked``
terms, the irreducible concepts, print with ``MARKER``; ``brief`` is the
one clause the key prints for an entry, the full text staying here.
"""
from typing import Dict, NamedTuple

from . import schema
from .schema import SchemaError

RESIDUAL_LABEL = "unassigned"  # the residual row: never in a share, never hidden
EXACT = "exact"
DRILL = "drill"
GROWTH = "growth"  # the headline's line for what the windows added after their start
GAP = "gap"  # the checks' unit: one call to the next
AVERAGE = "average_context_per_call"  # the headline's level: what a call held, averaged
MARKER = "*"  # a footnote: the term is explained below
PROG = "python3 -m sa"  # the real invocation, wherever a runnable command prints

# The output's spelling of a key, where it differs: the column and the
# total say "context tokens", the counts "changes" and "calls".
PRINTED = {schema.CONTEXT_DELTA: "context tokens", schema.CONTEXT_HELD: "avg per call", schema.INCREMENT: schema.PLURAL[schema.INCREMENT],
           schema.CALL: schema.PLURAL[schema.CALL], GAP: "gaps between calls"}


class Term(NamedTuple):
    meaning: str
    surprise: str
    marked: bool = False
    brief: str = ""  # the key's one clause; the meaning when empty


GLOSSARY: Dict[str, Term] = {
    schema.WINDOW_DIM: Term(
        "one context window: from a session start, subagent, fork, replay or compaction to"
        " its file's end or the next compaction; named by a short hash",
        "a file holds one window per compaction that a call follows; a file with no call"
        " is read but is no window", True,
        "one context window, from its start to its file's end or the next compaction"),
    schema.STARTED_BY_DIM: Term("what began the window: " + ", ".join(schema.STARTS),
                                "a compaction starts a new window in the same file; its starting"
                                " context re-counts the system prompt; %s explain fork, replayed" % PROG),
    schema.PEAK_DIM: Term("how full the window got: the band its largest call's context fell in, "
                          + ", ".join(schema.BANDS) + " tokens (K = 1,000; a band includes its lower"
                          " edge, so 200,000 is 200K+)",
                          "a band of the window, not of a call: a 200K+ window's calls are"
                          " counted there from its first, small ones too"),
    schema.FORK: Term("a window that began as a copy of another window's context: a forked"
                      " session or subagent, its file opening with the parent's records",
                      "the copy is one inherited change, counted in the parent when the parent"
                      " is in view; with the parent missing (deleted, or outside --since) or its"
                      " branch call not found, the copy counts as the fork's own, which the scope"
                      " warns of when the fork's file marks it one; an unmarked fork with its"
                      " parent missing reads as subagent_start, unwarned"),
    schema.REPLAYED: Term("a main window whose file opens by repeating another file's records"
                          " (a branched or continued session), then goes on",
                          "the repeated records count once, in the file that holds them first;"
                          " the copy is one inherited change; without that file it reads as a"
                          " session start, its copy its own, unwarned: only the parent shows it", True,
                          "a session that opens by repeating another's records (resumed or branched)"),
    schema.CALL: Term("one assistant message, its split records merged: what spend is read from",
                      "a message written as several records counts once"),
    schema.INCREMENT: Term("one booked change of a window's context, at its start (its starting"
                           " context) or between two calls: what context tokens are read from",
                           "one ambiguous change can name several tool results", True,
                           "one change of a window's context, at its start or between two calls,"
                           " booked to its cause"),
    schema.CONTEXT_DELTA: Term(
        "context tokens booked to what put them in a window; summed, they equal the"
        " windows' final sizes",
        "it is net: what a compaction or other shrink removed is not counted, so a window"
        " that grew to 700K and compacted to 70K reports 70K"),
    schema.SPEND: Term("what the calls billed, as input tokens weighted by price: cache reads"
                       " x0.1, cache writes x1.25 (5-minute) or x2.0 (1-hour); output excluded",
                       "every call re-reads its whole context, so spend grows with context times"
                       " calls; it is never quoted in dollars", True),
    AVERAGE: Term(
        "what a call held (its context size), averaged over the calls in view: the size the"
        " model reasoned over at a typical call",
        "not what a call added: every call re-reads its whole window, so long windows hold most"
        " calls; a mean of one population, never summed or averaged with another's", True,
        "what a call held, averaged over these calls; never added per call, never summed"),
    schema.CONTEXT_HELD: Term(
        "a row's part of the average context per call: its changes' tokens times the calls"
        " that held them (from the call each entered at to the window's end), over the calls"
        " in view; a table's rows add up to the average",
        "a change early in a long window weighs most: every later call held it. Per call of"
        " this view only: never summed or compared with another view's, whose calls differ"),
    schema.CONTEXT_TOKENS: Term("one call's context size: what it held; shown averaged over the"
                                " calls and as each window's peak band",
                                "never summed: a sum counts a token once per call that re-read it"),
    "output_tokens": Term("tokens the calls generated",
                          "the next call reads them back, as replies"),
    "cache_write_1h_tokens": Term("tokens written to the 1-hour prompt cache (billed x2.0)",
                                  "each call writes one cache tier only"),
    "cache_write_5m_tokens": Term("tokens written to the 5-minute prompt cache (billed x1.25)",
                                  "each call writes one cache tier only"),
    schema.PROJECT_DIM: Term("the project directory the session ran in, path-encoded (/ as -),"
                             " home printed as ~",
                             "a long name prints as its tail in a default table; --by prints it whole"),
    schema.SESSION_DIM: Term("a session id: its main window and every subagent window",
                             "--where session= keeps the subagents too; --where window= isolates one"),
    schema.SUBAGENT_DIM: Term("a subagent: its type and the first 8 of its id where the transcripts"
                              " record the type, else its id; --where takes either; a main window has none",
                              "main windows are the unassigned row of by subagent"),
    schema.CAUSE_DIM: Term("what kind of thing put the tokens in the context",
                           "starting_context is often the largest and cannot be split further"),
    schema.TOOL_DIM: Term("the tool whose result put the tokens there",
                          "context the model wrote or you typed has no tool: it is unassigned"),
    schema.COMMAND_DIM: Term("<tool>:<summary>: a Bash command's first command word (Bash:git) or"
                             " a file tool's file extension (Read:py)",
                             "never a path; python3 x.py is Bash:python3"),
    schema.REASON_DIM: Term("why a change is ambiguous", "only ambiguous changes have one"),
    schema.STARTING_CONTEXT: Term(
        "what a window held at its first call: the system prompt, tools, CLAUDE.md and the first"
        " message or prompt, or a compaction's summary; a fork's copy of its parent is counted"
        " apart, as inherited",
        "it is not split by content: the transcript records no size for each part. The lever is"
        " how many windows start (subagent starts are usually most of it) and what each start"
        " loads", True, "what a window held at its first call: system prompt, tools, CLAUDE.md,"
        " first message or summary"),
    schema.INHERITED: Term("what a fork or replayed window copied: its parent window's size at"
                           " the branch call",
                           "counted once: left out of the total when the parent window is kept;"
                           " its breakdown is the parent's up to that call"),
    schema.REPLIES: Term("Claude's replies, tool-call inputs included, read back by the next call",
                         "it is what the model wrote, not what a tool returned"),
    schema.TOOL_RESULT: Term("a tool's output, booked exactly to its tool and command",
                             "the part you can act on: drill it with --where tool="),
    schema.USER_TEXT: Term("text typed into the window (by you or a hook)",
                           "usually small: typing rarely fills a window"),
    schema.AMBIGUOUS: Term(
        "the growth between two calls not booked to one contributor: " + ", ".join(
            "%s (%s)" % r for r in ((schema.SEVERAL, "more than one entered"),
                                    (schema.LESS_THAN_REPLY, "grew by less than the previous call's reply"),
                                    (schema.UNEXPLAINED, "none did")))
        + "; never spread over them",
        "it still names a tool when every candidate came from one; --by fact lists the"
        " candidates", True, "growth with no one contributor, left undivided; a tool's row"
        " counts it when every candidate is that tool's"),
    schema.SHRINK: Term("a window that got smaller between two calls (often, not always, a"
                        " compaction): a negative row",
                        "excluded from every share, always in the checks", True,
                        "the window got smaller (often a compaction); negative, in no share"),
    schema.SEVERAL: Term("several results or texts entered between two calls",
                         "the tokens are not split between them"),
    schema.LESS_THAN_REPLY: Term("the window grew by less than the previous call's reply",
                                 "rare; the whole change stays ambiguous"),
    schema.UNEXPLAINED: Term("the context grew with nothing recorded to explain it",
                             "declared so it is labelled should it appear"),
    RESIDUAL_LABEL: Term("the part of a table's total with no value for its dimension",
                         "often most of the total: starting_context has no tool", True,
                         "no value for this table's dimension (what it holds ends its row); in no share"),
    EXACT: Term("a gap between two calls with one contributor that grew by at least the"
                " previous call's reply: booked to it after subtracting that reply",
                "exact given that model; bookkeeping attachments fold into the remainder"),
    GROWTH: Term("what the windows added after their start: every change between two calls,"
                 " shrinks aside. Its line names the largest tool and its tokens, then (→) the"
                 " largest command within that tool; '; top command' names a larger one elsewhere",
                 "its share is of every token added, starting context included, so it often looks"
                 " small: it is the part a tool or command can cut"),
    GAP: Term("the step from one call to the next in a window: N calls make N - 1 gaps; each"
              " gap's growth is booked to one source (exact), left ambiguous, or shrank",
              "a gap can book two changes (the previous reply, then the rest) and each window's"
              " start is one more, so changes outnumber gaps"),
    DRILL: Term("a --where pin on cause, tool, command or reason: narrows the changes inside"
                " the windows kept",
                "the checks still cover the whole windows, not the drill"),
}

_KEYS = {printed: key for key, printed in PRINTED.items()}


def key_of(term: str) -> str:
    """The internal key of a term as printed or as keyed, marker stripped."""
    term = term.rstrip(MARKER)
    term = _KEYS.get(term, term)
    return term if term in GLOSSARY else term.replace(" ", "_")  # ``starting context`` as printed


def explain(term: str) -> Term:
    try:
        return GLOSSARY[key_of(term)]
    except KeyError:
        raise SchemaError("unknown term %r; known: %s"
                          % (term, ", ".join(PRINTED.get(t, t) for t in GLOSSARY)))


def printed(term: str) -> str:
    return PRINTED.get(term, term)


def marked(term: str) -> str:
    """The term as printed, with the explain marker when the glossary marks it."""
    entry = GLOSSARY.get(term)
    return printed(term) + MARKER if entry and entry.marked else printed(term)


def brief(term: str) -> str:
    entry = GLOSSARY[term]
    return entry.brief or entry.meaning
