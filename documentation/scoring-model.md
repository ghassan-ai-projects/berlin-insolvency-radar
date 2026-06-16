# Scoring Model

## Philosophy

The scoring system is:
1. **Simple** — explainable in one sentence
2. **Consistent** — same inputs produce the same score
3. **Actionable** — high score = opportunity worth pursuing

## Formula

```
Score = (A × 0.25) + (B × 0.20) + (C × 0.20) + (D × 0.20) − (E × 0.15)
```

## Dimensions

| Letter | Dimension | Weight | Description |
|--------|-----------|--------|-------------|
| A | Company Value | 25% | Revenue, assets, market position, IP |
| B | Asset Quality | 20% | Tangible assets, customer base, contracts |
| C | Sector Attractiveness | 20% | Growth trends, consolidation potential |
| D | Speed of Action | 20% | Stage of proceedings, urgency |
| E | Legal/Risk Uncertainty | 15% | Complexity, liabilities, disputes *(negative)* |

## Scale

Each dimension scored 1–5:

| Score | Meaning |
|-------|---------|
| 1 | Poor / undesirable |
| 2 | Below average |
| 3 | Average / neutral |
| 4 | Good / above average |
| 5 | Excellent / highly desirable |

Theoretical range: −0.75 to 4.25 (real-world: 1.0 to 3.5).

## Classification

| Score | Category |
|-------|----------|
| ≥ 3.0 | 🔥 Hot |
| 2.5 – 2.9 | ✅ Solid |
| 2.0 – 2.4 | 👀 Interesting |
| < 2.0 | Low Priority (auto-quarantined) |

## Deterministic Enforcement

Scores are computed deterministically in `domain/scoring.py`. The LLM may propose dimensions,
but the final computation, bounds validation, and threshold gating are pure Python functions
with no LLM dependency. This prevents prompt injection from influencing the final score.
