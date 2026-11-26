"""Statement of cash flows -- indirect method, with investing/financing classification.

This module reconciles the net change in cash to net income plus changes in
every other balance-sheet account. That reconciliation is an exact
restatement of the balanced-journal-entry invariant (see the proof sketch in
docs/reference-model.md), so it is used in tests as a correctness check, not
just a report.

Each non-cash account's delta is classified into operating/investing/
financing by its `Account.cash_flow_category` (reference/accounting/
journal.py), which defaults to OPERATING -- every Phase 1/2 account used
that default (there was no investing/financing activity in any scenario
yet), so `investing_activities`/`financing_activities` are empty dicts for
every Phase 1/2 scenario and `operating_adjustments` is unchanged from what
Phase 1 produced. See docs/reference-model.md's "Phase 3 adds investing/
financing classification" section.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from reference.accounting.journal import (
    AccountingError,
    AccountType,
    CashFlowCategory,
    ChartOfAccounts,
)
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
    investing_activities: dict[str, Decimal] = field(default_factory=dict)
    financing_activities: dict[str, Decimal] = field(default_factory=dict)

    @property
    def net_change_in_cash(self) -> Decimal:
        return self.ending_cash - self.beginning_cash

    @property
    def operating_cash_flow(self) -> Decimal:
        return self.net_income + sum(self.operating_adjustments.values(), ZERO)

    @property
    def investing_cash_flow(self) -> Decimal:
        return sum(self.investing_activities.values(), ZERO)

    @property
    def financing_cash_flow(self) -> Decimal:
        return sum(self.financing_activities.values(), ZERO)

    def assert_reconciles(self) -> None:
        total = self.operating_cash_flow + self.investing_cash_flow + self.financing_cash_flow
        if total != self.net_change_in_cash:
            raise AccountingError(
                f"Cash flow statement for {self.scenario_id!r} at {self.period!r} does not "
                f"reconcile: operating_cash_flow={self.operating_cash_flow} "
                f"investing_cash_flow={self.investing_cash_flow} "
                f"financing_cash_flow={self.financing_cash_flow} "
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

    by_category: dict[CashFlowCategory, dict[str, Decimal]] = {
        CashFlowCategory.OPERATING: {},
        CashFlowCategory.INVESTING: {},
        CashFlowCategory.FINANCING: {},
    }
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
            by_category[account.cash_flow_category][account.id] = -delta
        else:
            # An increase in a liability or equity account is a source of cash.
            by_category[account.cash_flow_category][account.id] = delta

    statement = CashFlowStatement(
        scenario_id=scenario_id,
        period=period,
        start=start,
        end=end,
        beginning_cash=beginning_cash,
        ending_cash=ending_cash,
        net_income=income.net_income,
        operating_adjustments=by_category[CashFlowCategory.OPERATING],
        investing_activities=by_category[CashFlowCategory.INVESTING],
        financing_activities=by_category[CashFlowCategory.FINANCING],
    )
    statement.assert_reconciles()
    return statement
