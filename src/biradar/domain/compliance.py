"""Deterministic compliance filtering for insolvency records."""

# Allowed corporate legal forms in Germany
ALLOWED_LEGAL_FORMS = {
    "GMBH",
    "UG",
    "AG",
    "KG",
    "OHG",
    "GMBH & CO. KG",
    "GMBH & CO KG",
    "EG",
    "SE",
    "LTD",
}

# Keywords that strongly indicate consumer/personal filings (quarantine candidates)
CONSUMER_INDICATORS = {
    "verbraucherschutz",
    "consumer",
    "privatinsolvenz",
    "natural person",
    "e.k.",  # Eingetragener Kaufmann (sole proprietor)
    "e.kfm.",
    "e.kfr.",
}


def is_allowed_corporate_form(legal_form: str | None) -> bool:
    """Check if the legal form is an allowed corporate entity."""
    if not legal_form:
        return False
    normalized = legal_form.strip().upper().replace(".", "")
    return normalized in ALLOWED_LEGAL_FORMS


def has_consumer_indicators(raw_text: str | None, company_name: str | None) -> bool:
    """Check for indicators of consumer/personal insolvency."""
    text_to_check = ""
    if raw_text:
        text_to_check += " " + raw_text.lower()
    if company_name:
        text_to_check += " " + company_name.lower()

    for indicator in CONSUMER_INDICATORS:
        if indicator in text_to_check:
            return True
    return False


def evaluate_compliance(
    legal_form: str | None,
    raw_text: str | None = None,
    company_name: str | None = None,
) -> tuple[bool, str | None]:
    """
    Evaluate compliance of a record.

    Returns:
        (is_allowed, reason_if_rejected)
    """
    if has_consumer_indicators(raw_text, company_name):
        return False, "consumer_or_personal_indicator_detected"

    if not is_allowed_corporate_form(legal_form):
        return False, "missing_or_unsupported_legal_form"

    return True, None
