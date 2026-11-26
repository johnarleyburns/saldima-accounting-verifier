from datetime import date
from decimal import Decimal

import pytest

from reference.accounting import bank_reconciliation
from reference.accounting.journal import (
    Account,
    AccountingError,
    AccountType,
    ChartOfAccounts,
    JournalEntry,
    make_line,
)
from reference.accounting.ledger import Ledger

AS_OF = date(2026, 12, 31)


def _ledger_with_checking(balance: str) -> tuple[ChartOfAccounts, Ledger]:
    chart = ChartOfAccounts()
    chart.add(Account(id="checking", name="Checking", type=AccountType.ASSET))
    chart.add(Account(id="owner_equity", name="Owner's Equity", type=AccountType.EQUITY))
    ledger = Ledger(chart=chart)
    ledger.post(
        JournalEntry(
            id="e1",
            date=AS_OF,
            lines=(make_line("checking", debit=balance), make_line("owner_equity", credit=balance)),
        )
    )
    return chart, ledger


def test_reconciles_when_the_identity_holds():
    chart, ledger = _ledger_with_checking("1000.00")
    rec = bank_reconciliation.generate(
        ledger,
        chart,
        "checking",
        AS_OF,
        Decimal("900.00"),
        Decimal("300.00"),
        Decimal("200.00"),
        "test",
        "2026",
    )
    # adjusted_bank_balance = 900.00 + 300.00 - 200.00 = 1000.00 = book_balance.
    assert rec.adjusted_bank_balance == Decimal("1000.00")
    assert rec.book_balance == Decimal("1000.00")


def test_raises_when_the_identity_does_not_hold():
    chart, ledger = _ledger_with_checking("1000.00")
    with pytest.raises(AccountingError, match="does not reconcile"):
        bank_reconciliation.generate(
            ledger,
            chart,
            "checking",
            AS_OF,
            Decimal("900.00"),
            Decimal("300.00"),
            Decimal("199.00"),  # off by 1.00 from the case above
            "test",
            "2026",
        )


def test_unknown_cash_account_raises():
    chart, ledger = _ledger_with_checking("1000.00")
    with pytest.raises(AccountingError, match="Unknown cash account"):
        bank_reconciliation.generate(
            ledger,
            chart,
            "nonexistent",
            AS_OF,
            Decimal("0.00"),
            Decimal("0.00"),
            Decimal("0.00"),
            "test",
            "2026",
        )


def test_zero_outstanding_items_reconciles_trivially():
    chart, ledger = _ledger_with_checking("500.00")
    rec = bank_reconciliation.generate(
        ledger,
        chart,
        "checking",
        AS_OF,
        Decimal("500.00"),
        Decimal("0.00"),
        Decimal("0.00"),
        "test",
        "2026",
    )
    assert rec.adjusted_bank_balance == rec.book_balance == Decimal("500.00")
