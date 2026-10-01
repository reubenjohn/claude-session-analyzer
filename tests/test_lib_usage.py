"""Smoke tests for lib_usage: the module imports cleanly and each helper
honours its docstring on a minimal synthetic usage dict."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "lib"))

import lib_usage as L  # noqa: E402


def test_usage_context_sums_three_input_classes():
    u = {"input_tokens": 1, "cache_read_input_tokens": 2,
         "cache_creation_input_tokens": 3}
    assert L.usage_context(u) == 6
    assert L.usage_context(None) == 0


def test_usage_cache_tier_per_call():
    assert L.usage_cache_tier({"cache_creation": {"ephemeral_1h_input_tokens": 5}}) == "1h"
    assert L.usage_cache_tier({"cache_creation": {"ephemeral_5m_input_tokens": 5}}) == "5m"
    assert L.usage_cache_tier({"cache_creation": {
        "ephemeral_1h_input_tokens": 1, "ephemeral_5m_input_tokens": 1}}) == "mixed"
    assert L.usage_cache_tier({}) == "none"
    assert L.usage_cache_tier(None) == "none"


def test_usage_spend_weights_by_tier():
    u = {"input_tokens": 10, "cache_read_input_tokens": 100,
         "cache_creation_input_tokens": 4,
         "cache_creation": {"ephemeral_5m_input_tokens": 4}}
    assert L.usage_spend(u) == 10 + 0.1 * 100 + 1.25 * 4
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
