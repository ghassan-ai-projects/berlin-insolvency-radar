"""Markdown rendering for issue drafts."""

from typing import Any

_CATEGORY_EMOJI = {"hot": "🔥", "solid": "✅"}
_DISCLAIMER_LINES = [
    "---",
    "**Disclaimer:** This newsletter is for informational purposes only and "
    "does not constitute financial or investment advice. All data is sourced "
    "from public registers.",
]


def _render_draft_markdown(
    title: str,
    week: str,
    tier: str,
    candidates_data: list[dict[str, Any]],
    include_disclaimer: bool,
) -> str:
    """Render the newsletter draft as Markdown."""
    md_lines = [
        f"# {title}",
        f"**Week:** {week} | **Tier:** {tier.capitalize()}",
        "",
        "---",
        "",
    ]
    for idx, item in enumerate(candidates_data, start=1):
        md_lines.extend(_candidate_section(idx, item))
    if include_disclaimer:
        md_lines.extend(_DISCLAIMER_LINES)
    return "\n".join(md_lines)


def _candidate_section(idx: int, item: dict[str, Any]) -> list[str]:
    """Render one ranked candidate block."""
    cand = item["candidate"]
    score = item["score"]
    return [
        f"### {_category_emoji(score['category'])} #{idx} — "
        f"{cand['canonical_company_name']} ({cand['legal_form']})",
        f"- **Court:** {cand['court'] or 'N/A'}",
        f"- **Case Number:** {cand['case_number'] or 'N/A'}",
        f"- **Opportunity Score:** {score['computed_score']:.2f} "
        f"({score['category'].replace('_', ' ').title()})",
        f"- **Source:** {item['evidence'][0]['source_url'] if item['evidence'] else 'N/A'}",
        "",
    ]


def _category_emoji(category: str) -> str:
    """Pick the section emoji; anything but hot/solid gets watching eyes."""
    return _CATEGORY_EMOJI.get(category, "👀")
