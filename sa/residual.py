"""What the residual row, ``unassigned``, holds in a table by each
dimension: the cases ``-v`` lists, and the one note a
table prints on that row, naming the cases its own facts fall in."""
from typing import Callable, Dict, List, Sequence, Tuple

from . import heads, schema

Case = Tuple[str, Callable[[dict], bool]]  # a reading of a residual fact, and the dims it holds for


def _cause(cause: str) -> Callable[[dict], bool]:
    return lambda dims: dims.get(schema.CAUSE_DIM) == cause


# What the residual row of a table by each dimension can hold, printed by
# ``-v``, and summed into parts on the row. An ambiguous change is residual when its candidates share no one
# tool (by tool) or no one command (by command); a tool_result, when its
# tool_use did not resolve (by tool) or its tool has no command (by command).
RESIDUAL_NOTES: Dict[str, Tuple[str, List[Case]]] = {
    schema.SUBAGENT_DIM: ("main windows", []),
    schema.TOOL_DIM: ("no tool", [(c, _cause(c)) for c in (
        schema.STARTING_CONTEXT, schema.REPLIES, schema.USER_TEXT, schema.INHERITED,
        schema.AMBIGUOUS)] + [("an unresolved %s" % schema.TOOL_RESULT, _cause(schema.TOOL_RESULT))]),
    schema.COMMAND_DIM: ("no command", [
        ("no tool", lambda dims: schema.TOOL_DIM not in dims),
        ("not %s" % "/".join(sorted(heads.EXTRACTORS)),
         lambda dims: schema.TOOL_DIM in dims and _cause(schema.TOOL_RESULT)(dims)),
        (schema.AMBIGUOUS, lambda dims: schema.TOOL_DIM in dims and _cause(schema.AMBIGUOUS)(dims))]),
    schema.REASON_DIM: ("not %s" % schema.AMBIGUOUS, [  # shrink is the signed row, never residual
        (c, _cause(c)) for c in schema.CAUSES if c not in (schema.AMBIGUOUS, schema.SHRINK)]),
}


def residual_note(dim: str, residual: Sequence[dict]) -> str:
    """What the residual row of a table by ``dim`` holds: the cases some of
    the ``residual`` facts' dimensions satisfy."""
    meaning, cases = RESIDUAL_NOTES[dim]
    held = [text for text, holds in cases if any(holds(dims) for dims in residual)]
    return meaning + (": " + ", ".join(held) if held else "")


def residual_cases(dim: str) -> str:
    """Every case the catch-all row of a table by ``dim`` can hold: for
    ``-v``, after its label."""
    return ", ".join(text for text, _ in RESIDUAL_NOTES[dim][1])


def label(dim: str) -> str:
    """The catch-all row's label in a table by ``dim``: what its facts
    lack (``no tool``, ``main windows``). Printed as is, it pins that row:
    ``query.select`` reads its value as None."""
    return RESIDUAL_NOTES[dim][0] if dim in RESIDUAL_NOTES else "no " + dim
