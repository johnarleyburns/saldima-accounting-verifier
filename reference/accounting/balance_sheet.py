"""Balance sheet generation and the fundamental accounting-equation invariant.

Revenue and expense accounts are not part of the balance sheet, but until
they are closed into retained earnings (see closing.py) they represent
unrecognized equity. To keep the accounting equation true at *any* reporting
date -- not only immediately after a year-end close -- this module computes
the current fiscal year's unclosed net income and reports it as a synthetic
equity line, `current_period_earnings`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from reference.accounting import income_statement
from reference.accounting.journal import AccountingError, AccountType, ChartOfAccounts
from reference.accounting.ledger import Ledger
from reference.accounting.rounding import ZERO

CURRENT_PERIOD_EARNINGS_LINE = "current_period_earnings"


@dataclass(frozen=True)
class BalanceSheet:
    scenario_id: str
    period: str
    as_of: date
    assets: dict[str, Decimal]
    liabilities: dict[str, Decimal]
    equity: dict[str, Decimal]

    @property
    def total_assets(self) -> Decimal:
        return sum(self.assets.values(), ZERO)

    @property
    def total_liabilities(self) -> Decimal:
        return sum(self.liabilities.values(), ZERO)

    @property
    def total_equity(self) -> Decimal:
        return sum(self.equity.values(), ZERO)

    def assert_balances(self) -> None:
        lhs = self.total_assets
        rhs = self.total_liabilities + self.total_equity
        if lhs != rhs:
            raise AccountingError(
                f"Balance sheet for {self.scenario_id!r} at {self.period!r} fails the "
                f"accounting equation: assets={lhs} liabilities+equity={rhs}"
            )


def generate(
    ledger: Ledger,
    chart: ChartOfAccounts,
    as_of: date,
    fiscal_year_start: date,
    scenario_id: str,
    period: str,
) -> BalanceSheet:
    balances = ledger.balances_as_of(as_of)
    assets: dict[str, Decimal] = {}
    liabilities: dict[str, Decimal] = {}
    equity: dict[str, Decimal] = {}
    for account in chart.accounts.values():
        ending = balances[account.id]["ending_balance"]
        if account.type == AccountType.ASSET:
            assets[account.id] = ending
        elif account.type == AccountType.LIABILITY:
            liabilities[account.id] = ending
        elif account.type == AccountType.EQUITY:
            equity[account.id] = ending

    # Earnings already swept into retained earnings by a closing entry must
    # not also be counted here, or equity would double-count them (the
    # retained-earnings account balance above already reflects the closing).
    # So the unclosed-earnings window starts the day after the most recent
    # closing on or before `as_of`, not always at the fiscal year start.
    last_closing = ledger.last_closing_date_through(as_of)
    window_start = last_closing + timedelta(days=1) if last_closing else fiscal_year_start

    current_income = income_statement.generate(
        ledger, chart, window_start, as_of, scenario_id, period
    )
    equity[CURRENT_PERIOD_EARNINGS_LINE] = current_income.net_income

    bs = BalanceSheet(
        scenario_id=scenario_id, period=period, as_of=as_of, assets=assets, liabilities=liabilities, equity=equity
    )
    bs.assert_balances()
    return bs
