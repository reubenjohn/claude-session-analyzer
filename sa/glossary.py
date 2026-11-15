"""The glossary: every term the output prints, in plain words, and why its
number might surprise (D-PLAIN-TERMS). It drives ``sa explain``, the key
under the tables, the ``°`` markers and ``--help``; a test holds that every
declared term has an entry.

A term is its internal key (``schema``'s spelling); ``PRINTED`` names the
few the output spells otherwise, and ``explain`` accepts either. ``marked``
terms, the irreducible concepts, print with ``MARKER``; ``brief`` is the
one clause the key prints for an entry, the full text staying here.
"""
from typing import Dict, NamedTuple

from . import schema
from .schema import SchemaError

RESIDUAL_LABEL = "∅"
EXACT = "exact"
DRILL = "drill"
MARKER = "°"

# The output's spelling of a key, where it differs: the column and the
# total say "context tokens", the counts "changes" and "calls".
PRINTED = {schema.CONTEXT_DELTA: "context tokens", schema.INCREMENT: schema.PLURAL[schema.INCREMENT],
           schema.CALL: schema.PLURAL[schema.CALL]}


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
        " is read but is no window", True),
    schema.STARTED_BY_DIM: Term("what began the window: " + ", ".join(schema.STARTS),
                                "a compaction starts a new window in the same file; its starting"
                                " context re-counts the system prompt"),
    schema.CALL: Term("one assistant message, its split records merged: what spend is read from",
                      "a message written as several records counts once"),
    schema.INCREMENT: Term("one booked change of a window's context between two calls:"
                           " what context tokens are read from",
                           "one ambiguous change can name several tool results"),
    schema.CONTEXT_DELTA: Term(
        "context tokens booked to what put them in a window; summed, they equal the"
        " windows' final sizes",
        "it is net: what a compaction or other shrink removed is not counted, so a window"
        " that grew to 700K and compacted to 70K reports 70K"),
    schema.SPEND: Term("what the calls billed, as input tokens weighted by price: cache reads"
                       " x0.1, cache writes x1.25 (5-minute) or x2.0 (1-hour); output excluded",
                       "every call re-reads its whole context, so spend grows with context times"
                       " calls; it is never quoted in dollars"),
    schema.CONTEXT_TOKENS: Term("one call's context size; a peak, so only its largest call is shown",
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
    schema.SUBAGENT_DIM: Term("a subagent's id; a main window has none",
                              "main windows are the ∅ row of by subagent"),
    schema.CAUSE_DIM: Term("what kind of thing put the tokens in the context",
                           "starting_context is often the largest and cannot be split further"),
    schema.TOOL_DIM: Term("the tool whose result put the tokens there",
                          "context the model wrote or you typed has no tool: it is ∅"),
    schema.COMMAND_DIM: Term("<tool>:<summary>: a Bash command's first command word (Bash:git) or"
                             " a file tool's file extension (Read:py)",
                             "never a path; python3 x.py is Bash:python3"),
    schema.REASON_DIM: Term("why a change is ambiguous", "only ambiguous changes have one"),
    schema.STARTING_CONTEXT: Term(
        "the context a window's first call already had, less what it inherited: system prompt,"
        " tools, CLAUDE.md and first message, or a compaction's summary",
        "often the largest cause; the transcript does not record its contents, so it is"
        " not split further", True, "what the first call already had, never split"),
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
        " candidates", True, "growth with no one contributor, never spread"),
    schema.SHRINK: Term("a window that got smaller between two calls (often, not always, a"
                        " compaction): a negative row",
                        "excluded from every share, always in the checks"),
    schema.SEVERAL: Term("several results or texts entered between two calls",
                         "the tokens are not split between them"),
    schema.LESS_THAN_REPLY: Term("the window grew by less than the previous call's reply",
                                 "rare; the whole change stays ambiguous"),
    schema.UNEXPLAINED: Term("the context grew with nothing recorded to explain it",
                             "declared so it is labelled should it appear"),
    RESIDUAL_LABEL: Term("the part of a table's total with no value for its dimension;"
                         " the key says why, per table",
                         "often most of the total: starting_context has no tool", True),
    EXACT: Term("a gap between two calls with one contributor that grew by at least the"
                " previous call's reply: booked to it after subtracting that reply",
                "exact given that model; bookkeeping attachments fold into the remainder"),
    DRILL: Term("a --where pin on cause, tool, command or reason: narrows the changes inside"
                " the windows kept",
                "the checks still cover the whole windows, not the drill"),
}

_KEYS = {printed: key for key, printed in PRINTED.items()}


def key_of(term: str) -> str:
    """The internal key of a term as printed or as keyed, marker stripped."""
    term = term.rstrip(MARKER)
    return _KEYS.get(term, term)


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
