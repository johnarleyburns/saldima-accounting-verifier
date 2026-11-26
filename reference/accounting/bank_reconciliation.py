"""Bank reconciliation: the classic identity that a cash account's book
balance must equal the bank statement balance once timing differences
are accounted for.

`CORE-003`'s "Cash and reconciliation" validation target (docs/plan.md
section 19). This is a correctness check in the same spirit as
`cash_flow.py`'s `assert_reconciles()` -- not a journal-entry-producing
event -- so it mirrors that module's shape directly: a frozen result
dataclass with an `assert_reconciles()` method, and a `generate()`
function that reads the book balance from the existing `Ledger` and
raises if the two sides don't match exactly.

Scope boundary (see docs/accounting-policy.md): `bank_statement_balance`,
`deposits_in_transit`, and `outstanding_checks` are *declared* by the
scenario author, as if transcribed from an actual bank statement and
check register -- this module verifies the reconciliation arithmetic, not
bank-statement import or transaction matching.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from reference.accounting.journal import AccountingError, ChartOfAccounts
from reference.accounting.ledger import Ledger


@dataclass(frozen=True)
class BankReconciliation:
    scenario_id: str
    period: str
    as_of: date
    cash_account_id: str
    book_balance: Decimal
    bank_statement_balance: Decimal
    deposits_in_transit: Decimal
    outstanding_checks: Decimal

    @property
    def adjusted_bank_balance(self) -> Decimal:
        return self.bank_statement_balance + self.deposits_in_transit - self.outstanding_checks

    def assert_reconciles(self) -> None:
        if self.adjusted_bank_balance != self.book_balance:
            raise AccountingError(
                f"Bank reconciliation for {self.scenario_id!r} ({self.cash_account_id!r} at "
                f"{self.as_of}) does not reconcile: book_balance={self.book_balance} "
                f"adjusted_bank_balance={self.adjusted_bank_balance} (bank_statement_balance="
                f"{self.bank_statement_balance} + deposits_in_transit={self.deposits_in_transit} "
                f"- outstanding_checks={self.outstanding_checks})"
            )


def generate(
    ledger: Ledger,
    chart: ChartOfAccounts,
    cash_account_id: str,
    as_of: date,
    bank_statement_balance: Decimal,
    deposits_in_transit: Decimal,
    outstanding_checks: Decimal,
    scenario_id: str,
    period: str,
) -> BankReconciliation:
    if cash_account_id not in chart:
        raise AccountingError(f"Unknown cash account for bank reconciliation: {cash_account_id!r}")
    book_balance = ledger.balances_as_of(as_of)[cash_account_id]["ending_balance"]
    reconciliation = BankReconciliation(
        scenario_id=scenario_id,
        period=period,
        as_of=as_of,
        cash_account_id=cash_account_id,
        book_balance=book_balance,
        bank_statement_balance=bank_statement_balance,
        deposits_in_transit=deposits_in_transit,
        outstanding_checks=outstanding_checks,
    )
    reconciliation.assert_reconciles()
    return reconciliation
