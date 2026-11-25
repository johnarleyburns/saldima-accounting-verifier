"""Human-readable rendering of comparison results (schemas/comparison.schema.json)."""

from __future__ import annotations

from typing import Any


def render_comparison(result: dict[str, Any]) -> str:
    lines = [f"Scenario: {result['scenario_id']}", f"Period: {result['period']}", ""]
    if result["status"] == "PASS":
        lines.append("PASS")
        return "\n".join(lines)

    for d in result["discrepancies"]:
        lines.append(f"FAIL: {d['statement_type']}")
        lines.append("")
        lines.append(f"Account: {d['account_id']}")
        lines.append(f"Expected: {d['expected']}")
        lines.append(f"Actual:   {d['actual']}")
        lines.append(f"Difference: {d['difference']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def render_scenario_summary(scenario_id: str, period_statuses: dict[str, str]) -> str:
    lines = [f"Scenario: {scenario_id}", ""]
    for period, status in period_statuses.items():
        lines.append(f"{period}: {status}")
    return "\n".join(lines)
