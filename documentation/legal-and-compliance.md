# Legal & Compliance

## GDPR Considerations

### Corporate vs Personal Data

The central compliance rule: **skip consumer insolvencies entirely.**

- Corporate insolvencies (GmbH, UG, AG, GmbH & Co. KG, e.K., OHG, KG) are public record
  and can be processed, analyzed, and published
- Consumer/natural person insolvencies contain personal data protected under GDPR
- The compliance filter (`domain/compliance.py`) is a pure deterministic function that
  checks `legal_form` against a corporate-only allowlist and scans `raw_text` for
  consumer indicators ("Privatinsolvenz", "Verbraucherinsolvenz", natural person names)

### Data Processing

- All data is processed locally (DuckDB on disk)
- LLM API calls (DeepSeek) process notice text that is already public record
- No personal data of natural persons is intentionally processed or stored

## German Press Law (Pressekodex)

The newsletter format falls under press-like publishing. Key considerations:

- **Fact vs opinion:** Clearly separate extraction facts (evidence-backed) from editorial
  commentary and inferences
- **Right of reply:** Companies mentioned in the newsletter have a right to respond
- **Disclaimer:** Every export includes a disclaimer stating the content is for informational
  purposes only and does not constitute financial or legal advice

## UWG (Commercial Communications)

The newsletter is a commercial communication under German unfair competition law (UWG):

- Must be clearly identifiable as commercial content
- Must include sender identification and contact information
- Must honor opt-out requests promptly

## Corporate-Only Filter

The deterministic compliance filter in `domain/compliance.py`:

### Allowed Corporate Forms
- GmbH, UG (haftungsbeschränkt), AG, GmbH & Co. KG, e.K., OHG, KG, KGaA, SE, PartG, e.G.

### Consumer Indicators (→ quarantine)
- "Privatinsolvenz", "Verbraucherinsolvenz", "Regelinsolvenz" (when paired with natural person)
- Natural person name patterns (no corporate suffix)
- "Nachlassinsolvenz" (estate insolvency)

### Rejected Forms
- All natural person filings
- Associations (e.V.) — not corporate insolvencies in the investment sense
