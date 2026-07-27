#!/usr/bin/env python
"""Enforce the per-layer coverage targets declared in AGENTS.md.

`--cov-fail-under` only applies one global threshold, which would let a
well-covered layer mask a bare one. This reads coverage.json and checks each
layer against its own target.

Usage:
    python scripts/check_coverage.py [coverage.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Targets from AGENTS.md "Coverage targets by layer". Keep the two in sync.
LAYER_TARGETS: dict[str, float] = {
    "domain": 95.0,
    "services": 85.0,
    "graph": 75.0,
    "storage": 70.0,
    "agents": 50.0,
    "output": 50.0,
}

# Thin transport/entrypoint layers are "best effort" in AGENTS.md and are
# reported without being enforced.
UNENFORCED_LAYERS = ("mcp", "cli", "config", "observability", "sources", "utils")


def layer_of(path: str) -> str | None:
    """Return the package directory directly under biradar/, if any."""
    parts = Path(path).parts
    if "biradar" not in parts:
        return None
    idx = parts.index("biradar")
    if len(parts) <= idx + 1:
        return None
    candidate = parts[idx + 1]
    # Top-level modules (biradar/__init__.py) belong to no layer.
    return None if candidate.endswith(".py") else candidate


def main(argv: list[str]) -> int:
    report_path = Path(argv[1] if len(argv) > 1 else "coverage.json")
    if not report_path.exists():
        print(f"ERROR: {report_path} not found. Run `make coverage` first.")
        return 2

    data = json.loads(report_path.read_text())
    totals: dict[str, list[int]] = {}

    for path, info in data["files"].items():
        layer = layer_of(path)
        if layer is None:
            continue
        summary = info["summary"]
        covered, total = totals.setdefault(layer, [0, 0])
        totals[layer] = [
            covered + summary["covered_lines"],
            total + summary["num_statements"],
        ]

    failures: list[str] = []
    rows: list[tuple[str, float, str]] = []

    for layer in sorted(totals):
        covered, total = totals[layer]
        if total == 0:
            continue
        pct = 100.0 * covered / total
        target = LAYER_TARGETS.get(layer)
        if target is None:
            rows.append((layer, pct, "best effort"))
            continue
        status = "OK" if pct >= target else "FAIL"
        rows.append((layer, pct, f"target {target:.0f}% [{status}]"))
        if pct < target:
            failures.append(
                f"  {layer}/: {pct:.1f}% is below the {target:.0f}% target "
                f"({covered}/{total} statements)"
            )

    width = max(len(r[0]) for r in rows) if rows else 10
    print("Per-layer coverage (targets from AGENTS.md):")
    for layer, pct, note in rows:
        print(f"  {layer + '/':<{width + 1}}  {pct:6.1f}%   {note}")

    missing = [
        layer
        for layer in LAYER_TARGETS
        if layer not in totals or totals[layer][1] == 0
    ]
    if missing:
        failures.append(
            "  no measured statements for layer(s): " + ", ".join(sorted(missing))
        )

    if failures:
        print("\nCoverage targets not met:")
        print("\n".join(failures))
        return 1

    print("\nAll enforced layer targets met.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
