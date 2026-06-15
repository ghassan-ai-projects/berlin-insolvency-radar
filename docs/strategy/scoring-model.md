# Opportunity Scoring Framework

**Date:** 2026-06-15
**Status:** Draft — to be refined after 3 manual test issues

---

## Philosophy

The scoring system must be:
1. **Simple enough to explain in one sentence**
2. **Consistent** — same inputs produce same score
3. **Actionable** — high score = opportunity worth pursuing

---

## Score Formula (v1)

```
Opportunity Score = (A × 0.25) + (B × 0.20) + (C × 0.20) + (D × 0.20) − (E × 0.15)
```

### Dimensions

| Letter | Dimension | Weight | Description |
|--------|-----------|--------|-------------|
| A | Company Value | 25% | Revenue, assets, market position, IP |
| B | Asset Quality | 20% | Tangible assets, customer base, contracts, inventory |
| C | Sector Attractiveness | 20% | Growth trends, consolidation potential, strategic value |
| D | Speed of Action | 20% | Stage of proceedings, urgency, competition for assets |
| E | Legal/Risk Uncertainty | 15% | Complexity, liabilities, stakeholder disputes (negative) |

### Scoring Scale

Each dimension scored 1–5:

| Score | Meaning |
|-------|---------|
| 1 | Poor / undesirable |
| 2 | Below average |
| 3 | Average / neutral |
| 4 | Good / above average |
| 5 | Excellent / highly desirable |

Max possible: 4.25 (theoretical; real-world max ~3.5–4.0)
Min possible: -0.75 (theoretical)

### Classification

| Score | Category | Meaning |
|-------|----------|---------|
| 3.0+ | 🔥 Hot | Prioritize investigation |
| 2.5–2.9 | ✅ Solid | Worth a look |
| 2.0–2.4 | 👀 Interesting | Monitor |
| < 2.0 | ⏸️ Low Priority | Not actionable |

---

## Dimension Breakdown

### A: Company Value (25%)

| Score | Criteria |
|-------|----------|
| 5 | €10M+ revenue, strong market position, IP portfolio, brand value |
| 4 | €3–10M revenue, solid market position, some IP |
| 3 | €0.5–3M revenue, niche position |
| 2 | €50K–500K revenue, micro-business |
| 1 | Negligible revenue, no identifiable value |

### B: Asset Quality (20%)

| Score | Criteria |
|-------|----------|
| 5 | Real estate, significant equipment inventory, valuable contracts |
| 4 | Good equipment, customer contracts, some real estate |
| 3 | Moderate assets, ongoing operations |
| 2 | Limited assets, primarily service-based |
| 1 | Essentially no assets |

### C: Sector Attractiveness (20%)

| Score | Criteria |
|-------|----------|
| 5 | High-growth sector with consolidation potential (tech, green energy, healthcare) |
| 4 | Growing sector, active M&A |
| 3 | Stable sector, moderate interest |
| 2 | Declining sector, low M&A interest |
| 1 | Sector in crisis (exceptions: distressed M&A can still find opportunity here) |

### D: Speed of Action (20%)

| Score | Criteria |
|-------|----------|
| 5 | Pre-insolvency / early stage — time to evaluate and negotiate |
| 4 | Insolvency filed but restructuring likely |
| 3 | Active proceedings, investor process underway |
| 2 | Late stage — quick decision required |
| 1 | Proceedings nearly complete, limited opportunity |

### E: Legal/Risk Uncertainty (15%) — Negative

| Score | Criteria |
|-------|----------|
| 5 | Complex multi-stakeholder, litigation, contingent liabilities |
| 4 | Significant uncertainty, ownership disputes |
| 3 | Moderate risk, some open questions |
| 2 | Standard insolvency risk, manageable |
| 1 | Clean, straightforward proceeding |

---

## Example Scoring

### High-Quality Opportunity
```
A=4 (€4M revenue, strong brand, IP)
B=4 (equipment + contracts)
C=4 (manufacturing tech — growing sector)
D=3 (early proceedings, time to act)
E=2 (standard complexity)

Score = (4×0.25) + (4×0.20) + (4×0.20) + (3×0.20) − (2×0.15)
      = 1.00 + 0.80 + 0.80 + 0.60 − 0.30
      = 2.90 → ✅ Solid (borderline 🔥 Hot)
```

### Low-Quality Opportunity
```
A=2 (micro-business)
B=2 (few assets)
C=2 (commodity sector)
D=2 (late stage)
E=3 (some complexity)

Score = (2×0.25) + (2×0.20) + (2×0.20) + (2×0.20) − (3×0.15)
      = 0.50 + 0.40 + 0.40 + 0.40 − 0.45
      = 1.25 → ⏸️ Low Priority
```

---

## Future Improvements

After 10–20 scored companies, audit:
- Are high scores correlating with actual acquisition interest?
- Are any dimensions over/under-weighted?
- Should sector have an "exceptions" modifier (e.g., declining sector but dominant position)?
- Should we add a "buyer fit" dimension (tied to subscriber profile)?

**Rule:** Refine with data, not intuition. Run the first 3 issues manually, then analyze score patterns.
