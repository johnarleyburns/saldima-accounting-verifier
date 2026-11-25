"""Compares two normalized statement dicts (schemas/financial-statement.schema.json)
and produces a comparison.schema.json result. No floating-point tolerances --
see docs/plan.md section 12.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def compare_statement(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    if expected["scenario_id"] != actual["scenario_id"] or expected["period"] != actual["period"]:
        raise ValueError("Cannot compare statements for different scenarios/periods")

    discrepancies = []
    expected_lines = expected["lines"]
    actual_lines = actual["lines"]

    for account_id in sorted(set(expected_lines) | set(actual_lines)):
        exp_line = expected_lines.get(account_id)
        act_line = actual_lines.get(account_id)
        if exp_line is None or act_line is None:
            discrepancies.append(
                {
                    "statement_type": expected["statement_type"],
                    "account_id": account_id,
                    "expected": _summarize(exp_line),
                    "actual": _summarize(act_line),
                    "difference": "n/a (missing on one side)",
                }
            )
            continue
        for field in ("debit", "credit", "ending_balance"):
            if field not in exp_line and field not in act_line:
                continue
            exp_val = Decimal(exp_line.get(field, "0.00"))
            act_val = Decimal(act_line.get(field, "0.00"))
            if exp_val != act_val:
                discrepancies.append(
                    {
                        "statement_type": expected["statement_type"],
                        "account_id": f"{account_id}.{field}",
                        "expected": str(exp_val),
                        "actual": str(act_val),
                        "difference": str(act_val - exp_val),
                    }
                )

    return {
        "scenario_id": expected["scenario_id"],
        "period": expected["period"],
        "status": "FAIL" if discrepancies else "PASS",
        "discrepancies": discrepancies,
    }


def _summarize(line: dict[str, Any] | None) -> str:
    return "absent" if line is None else str(line)
