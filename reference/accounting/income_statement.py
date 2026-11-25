"""Income statement: revenue and expense activity for a reporting period.

Phase 1 scope: flat revenue/expense totals and net income. Contra-revenue,
COGS/gross-profit, and other-income-and-expense sections are added in later
phases alongside the scenarios that require them (see docs/plan.md section
18, Phase 2/3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from reference.accounting.journal import Account, AccountType, ChartOfAccounts
from reference.accounting.ledger import Ledger
from reference.accounting.rounding import ZERO


@dataclass(frozen=True)
class IncomeStatement:
    scenario_id: str
    period: str
    start: date
    end: date
    revenue: dict[str, Decimal]
    expenses: dict[str, Decimal]

    @property
    def total_revenue(self) -> Decimal:
        return sum(self.revenue.values(), ZERO)

    @property
    def total_expenses(self) -> Decimal:
        return sum(self.expenses.values(), ZERO)

    @property
    def net_income(self) -> Decimal:
        return self.total_revenue - self.total_expenses


def _signed_period_total(account: Account, activity: dict[str, Decimal]) -> Decimal:
    if account.type == AccountType.REVENUE:
        return activity["credit"] - activity["debit"]
    return activity["debit"] - activity["credit"]


def generate(
    ledger: Ledger,
    chart: ChartOfAccounts,
    start: date,
    end: date,
    scenario_id: str,
    period: str,
) -> IncomeStatement:
    activity = ledger.period_activity(start, end)
    revenue: dict[str, Decimal] = {}
    expenses: dict[str, Decimal] = {}
    for account in chart.accounts.values():
        if account.type == AccountType.REVENUE:
            revenue[account.id] = _signed_period_total(account, activity[account.id])
        elif account.type == AccountType.EXPENSE:
            expenses[account.id] = _signed_period_total(account, activity[account.id])
    return IncomeStatement(
        scenario_id=scenario_id, period=period, start=start, end=end, revenue=revenue, expenses=expenses
    )
