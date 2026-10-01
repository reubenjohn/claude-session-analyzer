"""sa.usage: each helper honours its docstring on a minimal synthetic usage
dict, and every function body is the ported one."""
import ast
import hashlib
from pathlib import Path

from sa import usage as L

# sha256 prefix of each ported function body with its docstring removed.
# Docstrings may change by ruling; a body change here is the recorded
# failure mode and needs a new measurement plus a logged ruling.
PORTED_BODIES = {
    "usage_context": "6cd87dea08b2fe13",
    "_cache_creation_tiers": "1de2fd93b04bfbf8",
    "usage_spend": "6b24d2d5c3596e24",
    "context_delta": "cc285c61b0efc9af",
    "max_merge_usage": "6851868ac33864ad",
}


def function_bodies(path):
    """``{name: source lines of the function with its docstring removed}``."""
    text = path.read_text(encoding="utf-8").splitlines()
    out = {}
    for node in ast.parse("\n".join(text)).body:
        if isinstance(node, ast.FunctionDef):
            lines = text[node.lineno - 1:node.end_lineno]
            if ast.get_docstring(node) is not None:
                doc = node.body[0]
                del lines[doc.lineno - node.lineno:doc.end_lineno - node.lineno + 1]
            out[node.name] = "\n".join(lines)
    return out


def test_every_function_body_is_the_ported_one():
    bodies = function_bodies(Path(L.__file__))
    assert {n: hashlib.sha256(b.encode()).hexdigest()[:16]
            for n, b in bodies.items()} == PORTED_BODIES
    assert all('"""' not in b for b in bodies.values())  # the strip removed the docstrings


def test_usage_context_sums_three_input_classes():
    u = {"input_tokens": 1, "cache_read_input_tokens": 2,
         "cache_creation_input_tokens": 3}
    assert L.usage_context(u) == 6
    assert L.usage_context(None) == 0


def test_usage_spend_weights_by_tier():
    u = {"input_tokens": 10, "cache_read_input_tokens": 100,
         "cache_creation_input_tokens": 4,
         "cache_creation": {"ephemeral_5m_input_tokens": 4}}
    assert L.usage_spend(u) == 10 + 0.1 * 100 + 1.25 * 4
    assert L.usage_spend({"cache_creation_input_tokens": 3,
                          "cache_creation": {"ephemeral_1h_input_tokens": 3}}) == 2.0 * 3
    # Untiered cache writes are priced at the 5m default.
    assert L.usage_spend({"cache_creation_input_tokens": 8}) == 1.25 * 8
    assert L.usage_spend(None) == 0.0


def test_context_delta_signed_and_head_of_sequence():
    assert L.context_delta(None, {"input_tokens": 7}) == 7
    assert L.context_delta({"input_tokens": 10}, {"input_tokens": 7}) == -3


def test_max_merge_usage_fieldwise_max_with_nested_cache_creation():
    merged = L.max_merge_usage([
        {"input_tokens": 1, "cache_creation": {"ephemeral_1h_input_tokens": 2}},
        {"input_tokens": 3, "output_tokens": 2,
         "cache_creation": {"ephemeral_5m_input_tokens": 4}},
        "not-a-dict",
    ])
    assert merged["input_tokens"] == 3
    assert merged["output_tokens"] == 2
    assert merged["cache_creation"] == {"ephemeral_1h_input_tokens": 2,
                                        "ephemeral_5m_input_tokens": 4}
    assert L.max_merge_usage([]) == {}
