"""Export generators for local artifact packages."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from biradar.observability.logging import get_logger

logger = get_logger(__name__)


def generate_markdown_draft(issue_data: dict[str, Any], export_dir: Path) -> str:
    """Generate a Markdown draft for the weekly issue."""
    title = issue_data.get("title", "Berlin Insolvency Radar")
    candidates = issue_data.get("candidates", [])
    now_str = datetime.now(timezone.utc).isoformat()
    
    lines = [
        f"# {title}",
        f"*Generated: {now_str}*",
        "",
        "## Disclaimer",
        "This document is for informational purposes only and does not constitute financial, legal, or investment advice. All data is sourced from public registers.",
        "",
        "## Ranked Opportunities",
        ""
    ]
    
    for i, candidate in enumerate(candidates, 1):
        name = candidate.get("company_name", "Unknown Company")
        legal_form = candidate.get("legal_form", "")
        score_info = candidate.get("score", {})
        computed_score = score_info.get("computed_score", "N/A")
        category = score_info.get("category", "unrated")
        
        lines.append(f"### {i}. {name} ({legal_form})")
        lines.append(f"- **Radar Score:** {computed_score} ({category})")
        lines.append(f"- **Status:** {candidate.get('status', 'unknown')}")
        lines.append("")
        
    lines.append("---")
    lines.append("*End of Report*")
    
    markdown_content = "\n".join(lines)
    
    # Ensure export directory exists
    export_dir.mkdir(parents=True, exist_ok=True)
    
    # Write to file
    now_fmt = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f"issue_draft_{now_fmt}.md"
    export_path = export_dir / filename
    
    export_path.write_text(markdown_content, encoding="utf-8")
    logger.info("Markdown draft exported", extra={"path": str(export_path)})
    
    return str(export_path)


def generate_json_package(issue_data: dict[str, Any], export_dir: Path) -> str:
    """Generate a structured JSON package for the issue."""
    export_dir.mkdir(parents=True, exist_ok=True)
    
    # Filter out quarantined candidates for the final package
    clean_candidates = [
        c for c in issue_data.get("candidates", []) 
        if c.get("status") != "quarantined"
    ]
    
    package = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_candidates": len(clean_candidates),
            "disclaimer": "Not financial advice. Sourced from public registers."
        },
        "candidates": clean_candidates
    }
    
    now_fmt = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f"issue_data_{now_fmt}.json"
    export_path = export_dir / filename
    
    with open(export_path, "w", encoding="utf-8") as f:
        json.dump(package, f, indent=2)
        
    logger.info("JSON package exported", extra={"path": str(export_path)})
    return str(export_path)
