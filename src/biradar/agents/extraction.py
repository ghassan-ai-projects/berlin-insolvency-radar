"""Extraction Agent for structured filing facts."""

import json
import os
from pathlib import Path
from typing import Any

import yaml
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from biradar.config.settings import get_settings
from biradar.observability.logging import get_logger

logger = get_logger(__name__)


class ExtractionResult(BaseModel):
    company_name: str | None = Field(default=None)
    legal_form: str | None = Field(default=None)
    court: str | None = Field(default=None)
    case_number: str | None = Field(default=None)
    filing_date: str | None = Field(default=None)
    administrator: str | None = Field(default=None)
    proceeding_stage: str | None = Field(default=None)
    sector_hints: list[str] = Field(default_factory=list)
    is_consumer_likely: bool = Field(default=False)
    field_confidence_scores: dict[str, float] = Field(default_factory=dict)
    evidence_snippets: dict[str, str] = Field(default_factory=dict)


def load_prompt(name: str) -> str:
    """Load an RCTCO prompt from the prompts directory."""
    settings = get_settings()
    prompt_path = settings.project_root / "src" / "biradar" / "agents" / "prompts" / f"{name}.yaml"
    
    if not prompt_path.exists():
        logger.warning(f"Prompt file not found: {prompt_path}. Using fallback.")
        return f"You are a data extraction specialist. Extract {name}."
        
    with open(prompt_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    # Combine RCTCO components into a single prompt string
    return (
        f"Role:\n{data.get('role', '')}\n\n"
        f"Core Task:\n{data.get('core_task', '')}\n\n"
        f"Context:\n{data.get('context', '')}\n\n"
        f"Constraints:\n{data.get('constraints', '')}\n\n"
        f"Output Format:\n{data.get('output_format', '')}"
    )


def extract_filing_facts(raw_text: str, source_url: str) -> ExtractionResult:
    """
    Extract structured filing facts from raw insolvency notice text.
    
    Falls back to a mock result if DEEPSEEK_API_KEY is not set, allowing
    local development and testing without network calls.
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    api_base = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
    model_name = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    
    if not api_key:
        logger.warning("DEEPSEEK_API_KEY not set. Returning mock extraction result.")
        # Fallback mock for development/testing
        return ExtractionResult(
            company_name="Mock GmbH",
            legal_form="GmbH",
            court="Amtsgericht Charlottenburg",
            case_number="36e IN 123/26",
            filing_date="2026-06-15",
            proceeding_stage="Eröffnungsbeschluss",
            is_consumer_likely=False,
            field_confidence_scores={"company_name": 0.9, "case_number": 0.9},
            evidence_snippets={"company_name": "Mock GmbH", "case_number": "36e IN 123/26"}
        )

    try:
        # DeepSeek is fully OpenAI API compatible
        llm = ChatOpenAI(
            openai_api_key=api_key,
            openai_api_base=api_base,
            model=model_name,
            temperature=0.0
        )
        structured_llm = llm.with_structured_output(ExtractionResult)
        
        prompt_template = PromptTemplate.from_template(
            load_prompt("extraction") + "\n\nRaw Notice Text:\n{text}\nSource URL: {source_url}"
        )
        
        chain = prompt_template | structured_llm
        result = chain.invoke({"text": raw_text, "source_url": source_url})
        
        return result
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        # Return a safe, empty result on failure to prevent pipeline crash
        return ExtractionResult(is_consumer_likely=True)
