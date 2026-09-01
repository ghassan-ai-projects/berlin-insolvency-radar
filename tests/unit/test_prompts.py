"""Unit tests for prompt loading and LLM response JSON parsing."""

import pytest

from biradar.utils.prompts import load_prompt, robust_json_parse


def test_load_prompt_returns_fallback_for_a_missing_prompt_file():
    prompt = load_prompt("definitely_not_a_real_prompt")

    assert "data extraction specialist" in prompt
    assert "definitely_not_a_real_prompt" in prompt


def test_load_prompt_renders_the_rctco_sections_of_an_existing_prompt():
    prompt = load_prompt("extraction")

    assert prompt.startswith("Role:\n")
    assert "Core Task:" in prompt
    assert "Context:" in prompt
    assert "Constraints:" in prompt
    assert "Output Format:" in prompt


def test_robust_json_parse_reads_json_surrounded_by_prose():
    assert robust_json_parse('Sure! {"a": 1} hope that helps') == {"a": 1}


def test_robust_json_parse_accepts_plain_json_arrays():
    assert robust_json_parse("[1, 2, 3]") == [1, 2, 3]


def test_robust_json_parse_raises_for_content_without_json():
    with pytest.raises(ValueError, match="Expecting"):
        robust_json_parse("no json here at all")
