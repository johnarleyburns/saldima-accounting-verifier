"""Trial balance generation and the fundamental debits == credits invariant."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from reference.accounting.journal import AccountingError, ChartOfAccounts
from reference.accounting.ledger import Ledger
from reference.accounting.rounding import ZERO


@dataclass(frozen=True)
class TrialBalanceLine:
    account_id: str
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True)
class TrialBalance:
    scenario_id: str
    period: str
    as_of: date
    lines: dict[str, TrialBalanceLine]

    @property
    def total_debit(self) -> Decimal:
        return sum((line.debit for line in self.lines.values()), ZERO)

    @property
    def total_credit(self) -> Decimal:
        return sum((line.credit for line in self.lines.values()), ZERO)

    def assert_balanced(self) -> None:
        if self.total_debit != self.total_credit:
            raise AccountingError(
                f"Trial balance for {self.scenario_id!r} at {self.period!r} does not "
                f"balance: total_debit={self.total_debit} total_credit={self.total_credit}"
            )


def generate(ledger: Ledger, chart: ChartOfAccounts, as_of: date, scenario_id: str, period: str) -> TrialBalance:
    balances = ledger.balances_as_of(as_of)
    lines: dict[str, TrialBalanceLine] = {}
    for account_id in chart.accounts:
        net = balances[account_id]["debit"] - balances[account_id]["credit"]
        if net >= ZERO:
            lines[account_id] = TrialBalanceLine(account_id, debit=net, credit=ZERO)
        else:
            lines[account_id] = TrialBalanceLine(account_id, debit=ZERO, credit=-net)
    tb = TrialBalance(scenario_id=scenario_id, period=period, as_of=as_of, lines=lines)
    tb.assert_balanced()
    return tb
