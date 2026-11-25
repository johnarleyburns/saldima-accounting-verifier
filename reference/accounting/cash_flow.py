"""Statement of cash flows -- indirect method, operating activities only.

Phase 1 scope: this module reconciles the net change in cash to net income
plus changes in every other balance-sheet account, all lumped into a single
"operating" section. That reconciliation is an exact restatement of the
balanced-journal-entry invariant (see the proof sketch in
docs/reference-model.md), so it is used in tests as a correctness check, not
just a report.

Investing and financing activity classification (section 7.2 of docs/plan.md)
requires per-account cash-flow-category metadata that is introduced in Phase
3 (fixed assets) and Phase 4 (debt) scenarios, and is intentionally not
implemented yet -- see docs/test-categories.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from reference.accounting.journal import AccountingError, AccountType, ChartOfAccounts
from reference.accounting.ledger import Ledger
from reference.accounting.rounding import ZERO


@dataclass(frozen=True)
class CashFlowStatement:
    scenario_id: str
    period: str
    start: date
    end: date
    beginning_cash: Decimal
    ending_cash: Decimal
    net_income: Decimal
    operating_adjustments: dict[str, Decimal]

    @property
    def net_change_in_cash(self) -> Decimal:
        return self.ending_cash - self.beginning_cash

    @property
    def operating_cash_flow(self) -> Decimal:
        return self.net_income + sum(self.operating_adjustments.values(), ZERO)

    def assert_reconciles(self) -> None:
        if self.operating_cash_flow != self.net_change_in_cash:
            raise AccountingError(
                f"Cash flow statement for {self.scenario_id!r} at {self.period!r} does not "
                f"reconcile: operating_cash_flow={self.operating_cash_flow} "
                f"net_change_in_cash={self.net_change_in_cash}"
            )


def generate(
    ledger: Ledger,
    chart: ChartOfAccounts,
    start: date,
    end: date,
    cash_account_ids: set[str],
    scenario_id: str,
    period: str,
) -> CashFlowStatement:
    from reference.accounting import income_statement as income_statement_mod

    day_before_start = start - timedelta(days=1)
    opening = ledger.balances_as_of(day_before_start, exclude_closing=True)
    closing_balances = ledger.balances_as_of(end, exclude_closing=True)

    beginning_cash = sum((opening[aid]["ending_balance"] for aid in cash_account_ids), ZERO)
    ending_cash = sum((closing_balances[aid]["ending_balance"] for aid in cash_account_ids), ZERO)

    income = income_statement_mod.generate(ledger, chart, start, end, scenario_id, period)

    adjustments: dict[str, Decimal] = {}
    for account in chart.accounts.values():
        if account.id in cash_account_ids:
            continue
        if account.type not in (AccountType.ASSET, AccountType.LIABILITY, AccountType.EQUITY):
            continue
        delta = closing_balances[account.id]["ending_balance"] - opening[account.id]["ending_balance"]
        if delta == ZERO:
            continue
        if account.type == AccountType.ASSET:
            # An increase in a non-cash asset is a use of cash.
            adjustments[account.id] = -delta
        else:
            # An increase in a liability or equity account is a source of cash.
            adjustments[account.id] = delta

    statement = CashFlowStatement(
        scenario_id=scenario_id,
        period=period,
        start=start,
        end=end,
        beginning_cash=beginning_cash,
        ending_cash=ending_cash,
        net_income=income.net_income,
        operating_adjustments=adjustments,
    )
    statement.assert_reconciles()
    return statement
