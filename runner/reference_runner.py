"""Runs the independent reference model over a loaded scenario.

Produces, for every requested reporting period, the normalized
trial-balance / income-statement / balance-sheet / (optionally) cash-flow
dicts described by schemas/financial-statement.schema.json. This is the
"expected results" side of the comparison engine (runner/compare.py) --
it must never consult Saldima production code (docs/plan.md section 2.1).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from reference.accounting import (
    balance_sheet,
    bank_reconciliation,
    cash_flow,
    closing,
    income_statement,
    trial_balance,
)
from reference.accounting.rounding import money
from reference.reporting import statements
from runner import period as period_mod
from runner.scenario_runner import LoadedScenario


def apply_closing_entries(scenario: LoadedScenario) -> None:
    closing_cfg = scenario.raw.get("closing")
    if not closing_cfg:
        return
    retained_earnings_account_id = closing_cfg.get("retained_earnings_account")
    partner_allocations_raw = closing_cfg.get("partner_allocations")
    # Partnership scenarios (Phase 5) allocate net income/loss across
    # multiple partner capital accounts by ratio instead of sweeping it
    # into one retained-earnings account -- see docs/accounting-policy.md.
    partner_allocations = (
        {account_id: money(ratio) for account_id, ratio in partner_allocations_raw.items()}
        if partner_allocations_raw is not None
        else None
    )
    for close_date_str in closing_cfg["dates"]:
        close_date = date.fromisoformat(close_date_str)
        fy_start = period_mod.fiscal_year_start(close_date)
        closing.close_period(
            scenario.ledger,
            scenario.chart,
            period_start=fy_start,
            period_end=close_date,
            retained_earnings_account_id=retained_earnings_account_id,
            entry_id=f"closing-{close_date.isoformat()}",
            partner_allocations=partner_allocations,
        )


def generate_period_reports(scenario: LoadedScenario, period: str) -> dict[str, Any]:
    start, end = period_mod.parse_period(period)
    fy_start = period_mod.fiscal_year_start(end)

    tb = trial_balance.generate(scenario.ledger, scenario.chart, end, scenario.id, period)
    income = income_statement.generate(
        scenario.ledger, scenario.chart, start, end, scenario.id, period
    )
    bs = balance_sheet.generate(scenario.ledger, scenario.chart, end, fy_start, scenario.id, period)

    result = {
        "trial_balance": statements.trial_balance_to_dict(tb),
        "income_statement": statements.income_statement_to_dict(income),
        "balance_sheet": statements.balance_sheet_to_dict(bs),
    }

    if scenario.cash_account_ids:
        cf = cash_flow.generate(
            scenario.ledger,
            scenario.chart,
            start,
            end,
            scenario.cash_account_ids,
            scenario.id,
            period,
        )
        lines = {
            "net_income": {"ending_balance": f"{cf.net_income:.2f}"},
            **{aid: {"ending_balance": f"{v:.2f}"} for aid, v in cf.operating_adjustments.items()},
            "operating_cash_flow": {"ending_balance": f"{cf.operating_cash_flow:.2f}"},
        }
        # investing_activities/financing_activities are empty dicts for any
        # scenario with no account tagged that CashFlowCategory (every
        # Phase 1/2 scenario), so these lines only appear once a scenario
        # actually has investing/financing activity -- see
        # docs/reference-model.md's "Phase 3 adds investing/financing
        # classification" section. This keeps Phase 1/2's reviewed fixtures
        # byte-for-byte unchanged.
        if cf.investing_activities:
            lines.update(
                {aid: {"ending_balance": f"{v:.2f}"} for aid, v in cf.investing_activities.items()}
            )
            lines["investing_cash_flow"] = {"ending_balance": f"{cf.investing_cash_flow:.2f}"}
        if cf.financing_activities:
            lines.update(
                {aid: {"ending_balance": f"{v:.2f}"} for aid, v in cf.financing_activities.items()}
            )
            lines["financing_cash_flow"] = {"ending_balance": f"{cf.financing_cash_flow:.2f}"}
        lines["beginning_cash"] = {"ending_balance": f"{cf.beginning_cash:.2f}"}
        lines["ending_cash"] = {"ending_balance": f"{cf.ending_cash:.2f}"}
        result["cash_flow"] = {
            "scenario_id": cf.scenario_id,
            "period": cf.period,
            "statement_type": "cash_flow",
            "lines": lines,
        }

    return result


def generate_bank_reconciliations(scenario: LoadedScenario) -> dict[str, dict[str, Any]]:
    """CORE-003 scope: a scenario may declare zero or more bank
    reconciliations (see schemas/scenario.schema.json's
    `bank_reconciliations`). Each one is returned as its own "period"
    entry -- `reconciliation-<cash_account_id>-<as_of>` -- alongside
    `generate_period_reports`'s ordinary periods, so it reuses the exact
    same fixture/comparison machinery (runner/compare.py,
    tests/integration/test_core_scenarios.py) with no changes to either.
    """
    results: dict[str, dict[str, Any]] = {}
    for entry in scenario.raw.get("bank_reconciliations", []):
        cash_account_id = entry["cash_account_id"]
        as_of = date.fromisoformat(entry["as_of"])
        rec = bank_reconciliation.generate(
            scenario.ledger,
            scenario.chart,
            cash_account_id,
            as_of,
            money(entry["bank_statement_balance"]),
            money(entry["deposits_in_transit"]),
            money(entry["outstanding_checks"]),
            scenario.id,
            f"reconciliation-{cash_account_id}-{as_of.isoformat()}",
        )
        period = f"reconciliation-{cash_account_id}-{as_of.isoformat()}"
        results[period] = {"bank_reconciliation": statements.bank_reconciliation_to_dict(rec)}
    return results


def run(scenario: LoadedScenario) -> dict[str, dict[str, Any]]:
    apply_closing_entries(scenario)
    reports = {
        period: generate_period_reports(scenario, period) for period in scenario.report_periods
    }
    reports.update(generate_bank_reconciliations(scenario))
    return reports
