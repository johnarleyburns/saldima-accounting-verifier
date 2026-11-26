"""Normalizes reference-model statements into the financial-statement.schema.json shape.

This is the boundary the comparison engine (runner/compare.py) operates on:
both the reference model and any system adapter must produce dicts in this
shape so they can be compared account-by-account.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from reference.accounting import balance_sheet, bank_reconciliation, income_statement, trial_balance


def _fmt(value: Decimal) -> str:
    return f"{value:.2f}"


def trial_balance_to_dict(tb: trial_balance.TrialBalance) -> dict[str, Any]:
    return {
        "scenario_id": tb.scenario_id,
        "period": tb.period,
        "statement_type": "trial_balance",
        "lines": {
            account_id: {"debit": _fmt(line.debit), "credit": _fmt(line.credit)}
            for account_id, line in tb.lines.items()
        },
    }


def income_statement_to_dict(stmt: income_statement.IncomeStatement) -> dict[str, Any]:
    lines = {aid: {"ending_balance": _fmt(v)} for aid, v in stmt.revenue.items()}
    lines.update({aid: {"ending_balance": _fmt(v)} for aid, v in stmt.expenses.items()})
    lines["net_income"] = {"ending_balance": _fmt(stmt.net_income)}
    return {
        "scenario_id": stmt.scenario_id,
        "period": stmt.period,
        "statement_type": "income_statement",
        "lines": lines,
    }


def balance_sheet_to_dict(bs: balance_sheet.BalanceSheet) -> dict[str, Any]:
    lines = {aid: {"ending_balance": _fmt(v)} for aid, v in bs.assets.items()}
    lines.update({aid: {"ending_balance": _fmt(v)} for aid, v in bs.liabilities.items()})
    lines.update({aid: {"ending_balance": _fmt(v)} for aid, v in bs.equity.items()})
    return {
        "scenario_id": bs.scenario_id,
        "period": bs.period,
        "statement_type": "balance_sheet",
        "lines": lines,
    }


def bank_reconciliation_to_dict(rec: bank_reconciliation.BankReconciliation) -> dict[str, Any]:
    return {
        "scenario_id": rec.scenario_id,
        "period": rec.period,
        "statement_type": "bank_reconciliation",
        "lines": {
            "book_balance": {"ending_balance": _fmt(rec.book_balance)},
            "bank_statement_balance": {"ending_balance": _fmt(rec.bank_statement_balance)},
            "deposits_in_transit": {"ending_balance": _fmt(rec.deposits_in_transit)},
            "outstanding_checks": {"ending_balance": _fmt(rec.outstanding_checks)},
            "adjusted_bank_balance": {"ending_balance": _fmt(rec.adjusted_bank_balance)},
        },
    }
