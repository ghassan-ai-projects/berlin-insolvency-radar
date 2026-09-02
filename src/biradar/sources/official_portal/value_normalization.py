"""Normalization helpers for portal field values."""

from datetime import datetime


def _infer_legal_form(company_name: str) -> str | None:
    """Infer a corporate legal form from the company name."""
    normalized = company_name.upper()
    canonical_forms = {
        "GMBH & CO. KG": "GmbH & Co. KG",
        "GMBH & CO KG": "GmbH & Co KG",
        "GMBH": "GmbH",
        "UG": "UG",
        "AG": "AG",
        "KG": "KG",
        "OHG": "OHG",
        "EG": "eG",
        "SE": "SE",
        "LTD": "Ltd",
    }
    for legal_form, canonical in canonical_forms.items():
        if legal_form in normalized:
            return canonical
    return None


def _normalize_publication_date(value: str) -> str:
    """Normalize portal date strings to ISO format when possible."""
    try:
        return datetime.strptime(value, "%d.%m.%Y").date().isoformat()
    except ValueError:
        return value
