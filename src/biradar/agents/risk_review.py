"""Risk Review Agent for compliance and legal gatekeeping."""

import json
import os
from typing import Any

import yaml
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from biradar.config.settings import get_settings
from biradar.observability.logging import get_logger

logger = get_logger(__name__)


class RiskReviewResult(BaseModel):
    passed_review: bool = Field(description="Whether the candidate passed the risk review.")
    rejection_reasons: list[str] | None = Field(default=None, description="Reasons for rejection if failed.")
    actionable_feedback_for_analyst: str | None = Field(default=None, description="Feedback for the analyst agent to fix the draft.")
    flagged_unsupported_claims: list[str] = Field(default_factory=list, description="Specific claims lacking evidence.")
    confidence_in_review: float = Field(ge=0.0, le=1.0, description="Confidence in this review decision.")


def load_prompt(name: str) -> str:
    """Load an RCTCO prompt from the prompts directory."""
    settings = get_settings()
    prompt_path = settings.project_root / "src" / "biradar" / "agents" / "prompts" / f"{name}.yaml"
    
    if not prompt_path.exists():
        logger.warning(f"Prompt file not found: {prompt_path}. Using fallback.")
        return f"You are a risk review specialist. Review for {name}."
        
    with open(prompt_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    return (
        f"Role:\n{data.get('role', '')}\n\n"
        f"Core Task:\n{data.get('core_task', '')}\n\n"
        f"Context:\n{data.get('context', '')}\n\n"
        f"Constraints:\n{data.get('constraints', '')}\n\n"
        f"Output Format:\n{data.get('output_format', '')}"
    )


def review_candidate_risk(
    candidate_data: dict[str, Any], 
    extraction_data: dict[str, Any],
    enrichment_data: dict[str, Any],
    draft_thesis: str
) -> RiskReviewResult:
    """
    Review a candidate's drafted intelligence for compliance, legal, and evidence risks.
    
    Falls back to passing if DEEPSEEK_API_KEY is not set.
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    api_base = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
    model_name = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    
    if not api_key:
        logger.warning("DEEPSEEK_API_KEY not set. Risk review passing by default (mock).")
        return RiskReviewResult(
            passed_review=True,
            confidence_in_review=0.5
        )

    try:
        # DeepSeek is fully OpenAI API compatible
        llm = ChatOpenAI(
            openai_api_key=api_key,
            openai_api_base=api_base,
            model=model_name,
            temperature=0.0
        )
        structured_llm = llm.with_structured_output(RiskReviewResult)
        
        review_context = (
            f"Candidate Data: {json.dumps(candidate_data, default=str)}\n"
            f"Extraction Data: {json.dumps(extraction_data, default=str)}\n"
            f"Enrichment Data: {json.dumps(enrichment_data, default=str)}\n"
            f"Draft Thesis: {draft_thesis}"
        )
        
        prompt_template = PromptTemplate.from_template(
            load_prompt("risk_review") + "\n\nCandidate Context:\n{context}"
        )
        
        chain = prompt_template | structured_llm
        result = chain.invoke({"context": review_context})
        
        return result
    except Exception as e:
        logger.error(f"Risk review failed: {e}")
        # Fail closed: if review fails, we quarantine to be safe
        return RiskReviewResult(
            passed_review=False,
            rejection_reasons=[f"Review system error: {str(e)}"],
            confidence_in_review=0.0
        )
