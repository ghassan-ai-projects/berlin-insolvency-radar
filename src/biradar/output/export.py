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
    now_str = issue_data.get("generated_at", datetime.now(timezone.utc).isoformat())
    source_run_id = issue_data.get("source_run_id")
    run_warnings = issue_data.get("warnings", [])
    audit_summary = issue_data.get("audit_summary", {})
    
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
    if source_run_id:
        lines.extend([f"Source Run: `{source_run_id}`", ""])
    if audit_summary:
        lines.extend(
            [
                "## Run Summary",
                f"- Raw Records: {audit_summary.get('total_raw_records', 0)}",
                f"- Candidates Evaluated: {audit_summary.get('total_candidates', 0)}",
                f"- Publish Ready: {audit_summary.get('publish_ready_candidates', 0)}",
                f"- Quarantined: {audit_summary.get('quarantined_candidates', 0)}",
                f"- Errors: {audit_summary.get('error_count', 0)}",
                f"- Warnings: {audit_summary.get('warning_count', 0)}",
                "",
            ]
        )
    if run_warnings:
        lines.extend(["## Run Notes", *[f"- {warning}" for warning in run_warnings], ""])
    
    for i, candidate in enumerate(candidates, 1):
        name = candidate.get("company_name", "Unknown Company")
        legal_form = candidate.get("legal_form", "")
        score_info = candidate.get("score", {})
        computed_score = score_info.get("computed_score", "N/A")
        category = score_info.get("category", "unrated")
        export_confidence = candidate.get("export_confidence", "N/A")
        source_url = candidate.get("source_url")
        evidence_summary = candidate.get("evidence_summary", {})
        enrichment_claims = candidate.get("enrichment_claims", [])
        content_sections = candidate.get("content_sections", {})
        factual_fields = content_sections.get("facts", {})
        editorial = content_sections.get("editorial", {})
        
        lines.append(f"### {i}. {name} ({legal_form})")
        lines.append(f"- **Radar Score:** {computed_score} ({category})")
        lines.append(f"- **Confidence:** {export_confidence}")
        lines.append(f"- **Status:** {candidate.get('status', 'unknown')}")
        if source_url:
            lines.append(f"- **Source URL:** {source_url}")
        if evidence_summary:
            lines.append("- **Evidence:**")
            for field, snippet in evidence_summary.items():
                lines.append(f"  - `{field}`: {snippet}")
        if factual_fields:
            lines.append("- **Facts:**")
            for field, value in factual_fields.items():
                lines.append(f"  - `{field}`: {value}")
        if enrichment_claims:
            lines.append("- **Inferences:**")
            for claim in enrichment_claims:
                lines.append(
                    f"  - `{claim.get('field')}` = {claim.get('value')} ({claim.get('classification', 'unknown')})"
                )
        if editorial:
            lines.append("- **Editorial Context:**")
            lines.append(f"  - Thesis: {editorial.get('thesis', 'N/A')}")
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
            "generated_at": issue_data.get("generated_at", datetime.now(timezone.utc).isoformat()),
            "total_candidates": len(clean_candidates),
            "disclaimer": "Not financial advice. Sourced from public registers.",
            "source_run_id": issue_data.get("source_run_id"),
            "warnings": issue_data.get("warnings", []),
            "audit_summary": issue_data.get("audit_summary", {}),
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
