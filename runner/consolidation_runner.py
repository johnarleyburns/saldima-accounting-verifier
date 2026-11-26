"""Runs consolidated reporting for a known multi-entity group (MULTI-001/
002, docs/plan.md section 19). Not a general-purpose multi-entity
scenario loader -- there are only two of these, ever planned (see
docs/accounting-policy.md's consolidation scope boundaries), so the
entity-file-paths-plus-elimination-pairs wiring is a small, explicit,
hardcoded registry rather than a new YAML schema.

Each entity in a group is an ordinary scenario, loaded and closed through
the completely unmodified `runner/scenario_runner.py` and `runner/
reference_runner.apply_closing_entries` -- consolidation only combines
already-closed entity books (see `reference/accounting/consolidation.py`
docstrings for why that's required).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from reference.accounting import consolidation
from reference.reporting import statements
from runner import period as period_mod
from runner import reference_runner
from runner.scenario_runner import load_scenario

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = REPO_ROOT / "scenarios" / "multi-entity"


@dataclass(frozen=True)
class ConsolidationGroup:
    id: str
    entity_scenario_files: tuple[str, ...]
    eliminations: tuple[consolidation.EliminationPair, ...]
    report_periods: tuple[str, ...]


GROUPS: dict[str, ConsolidationGroup] = {
    "multi-001-intercompany-transactions": ConsolidationGroup(
        id="multi-001-intercompany-transactions",
        entity_scenario_files=("multi-001-parent.yaml", "multi-001-subsidiary.yaml"),
        eliminations=(
            consolidation.EliminationPair("investment_in_subsidiary", "common_stock"),
            consolidation.EliminationPair("intercompany_receivable", "intercompany_payable"),
            consolidation.EliminationPair(
                "intercompany_interest_expense", "intercompany_interest_income"
            ),
        ),
        report_periods=("2026", "2027"),
    ),
    "multi-002-multi-entity-reporting": ConsolidationGroup(
        id="multi-002-multi-entity-reporting",
        entity_scenario_files=("multi-002-parent.yaml", "multi-002-subsidiary.yaml"),
        eliminations=(
            consolidation.EliminationPair("investment_in_subsidiary", "common_stock"),
            consolidation.EliminationPair("intercompany_receivable", "intercompany_payable"),
            consolidation.EliminationPair(
                "intercompany_interest_expense", "intercompany_interest_income"
            ),
            consolidation.EliminationPair(
                "intercompany_management_fee_expense", "intercompany_management_fee_revenue"
            ),
        ),
        report_periods=("2026", "2027", "2028", "2029", "2030"),
    ),
}


def run(group_id: str) -> dict[str, dict[str, Any]]:
    group = GROUPS[group_id]
    entities: list[consolidation.Entity] = []
    for filename in group.entity_scenario_files:
        loaded = load_scenario(SCENARIOS_DIR / filename)
        reference_runner.apply_closing_entries(loaded)
        entities.append((loaded.chart, loaded.ledger))

    eliminations = list(group.eliminations)
    results: dict[str, dict[str, Any]] = {}
    for period in group.report_periods:
        start, end = period_mod.parse_period(period)
        tb = consolidation.consolidated_trial_balance(entities, eliminations, end, group.id, period)
        income = consolidation.consolidated_income_statement(
            entities, eliminations, start, end, group.id, period
        )
        bs = consolidation.consolidated_balance_sheet(entities, eliminations, end, group.id, period)
        results[period] = {
            "trial_balance": statements.trial_balance_to_dict(tb),
            "income_statement": statements.income_statement_to_dict(income),
            "balance_sheet": statements.balance_sheet_to_dict(bs),
        }
    return results
