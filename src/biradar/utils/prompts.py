"""Shared prompt loading for LLM agents."""

import json
import logging
import re
from typing import Any

import yaml

from biradar.config.settings import get_settings

logger = logging.getLogger(__name__)


def load_prompt(name: str) -> str:
    """Load an RCTCO prompt from the prompts directory."""
    settings = get_settings()
    prompt_path = settings.project_root / "src" / "biradar" / "agents" / "prompts" / f"{name}.yaml"

    if not prompt_path.exists():
        logger.warning(f"Prompt file not found: {prompt_path}. Using fallback.")
        return f"You are a data extraction specialist. Extract {name}."

    with open(prompt_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return (
        f"Role:\n{data.get('role', '')}\n\n"
        f"Core Task:\n{data.get('core_task', '')}\n\n"
        f"Context:\n{data.get('context', '')}\n\n"
        f"Constraints:\n{data.get('constraints', '')}\n\n"
        f"Output Format:\n{data.get('output_format', '')}"
    )


def robust_json_parse(content: str) -> Any:
    """Extract and parse JSON from an LLM response, with regex fallback."""
    json_match = re.search(r"\{.*\}|\[.*\]", content, re.DOTALL)
    json_str = json_match.group(0) if json_match else content.strip()
    return json.loads(json_str)
