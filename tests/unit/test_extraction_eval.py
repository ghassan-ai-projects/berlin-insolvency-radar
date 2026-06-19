"""Fixture-backed extraction and compliance evaluation cases."""

import json
import os
from pathlib import Path

import pytest

from biradar.agents.extraction import extract_filing_facts
from biradar.domain.compliance import evaluate_compliance

FIXTURE_PATH = (
    Path(__file__).parent.parent
    / "fixtures"
    / "evals"
    / "extraction_compliance_cases.json"
)


def _load_eval_cases() -> list[dict]:
    with open(FIXTURE_PATH, encoding="utf-8") as handle:
        return json.load(handle)


@pytest.mark.parametrize(
    "case",
    _load_eval_cases(),
    ids=[case["case_id"] for case in _load_eval_cases()],
)
def test_extraction_and_compliance_eval_cases(monkeypatch, case):
    original_env = {
        "BIRADAR_LLM_API_KEY": os.environ.get("BIRADAR_LLM_API_KEY"),
        "BIRADAR_LLM_MODEL": os.environ.get("BIRADAR_LLM_MODEL"),
    }
    os.environ["BIRADAR_LLM_API_KEY"] = "test-key"
    os.environ["BIRADAR_LLM_MODEL"] = "test-model"

    class FakeLLM:
        def invoke(self, *_args, **_kwargs):
            return type(
                "Resp",
                (),
                {"content": json.dumps(case["expected_extraction"])},
            )()

    monkeypatch.setattr("biradar.agents.extraction.build_chat_llm", lambda: FakeLLM())

    try:
        result = extract_filing_facts(case["raw_text"], case["source_url"])
    finally:
        for name, value in original_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    expected = case["expected_extraction"]
    assert result.company_name == expected["company_name"]
    assert result.legal_form == expected["legal_form"]
    assert result.case_number == expected["case_number"]
    assert result.is_consumer_likely is expected["is_consumer_likely"]

    allowed, reason = evaluate_compliance(
        legal_form=result.legal_form,
        raw_text=case["raw_text"],
        company_name=result.company_name,
    )
    assert allowed is case["expected_compliance"]["allowed"]
    assert reason == case["expected_compliance"]["reason"]
