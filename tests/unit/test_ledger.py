from datetime import date

import pytest

from reference.accounting.journal import (
    Account,
    AccountingError,
    AccountType,
    ChartOfAccounts,
    JournalEntry,
    make_line,
)
from reference.accounting.ledger import Ledger


def _ledger() -> Ledger:
    chart = ChartOfAccounts()
    chart.add(Account(id="cash", name="Cash", type=AccountType.ASSET))
    chart.add(Account(id="equity", name="Equity", type=AccountType.EQUITY))
    return Ledger(chart=chart)


def test_post_rejects_unknown_account():
    ledger = _ledger()
    entry = JournalEntry(
        id="e1",
        date=date(2026, 1, 1),
        lines=(make_line("cash", debit="100.00"), make_line("unknown_account", credit="100.00")),
    )
    with pytest.raises(AccountingError, match="unknown account"):
        ledger.post(entry)


def test_post_rejects_duplicate_entry_id():
    ledger = _ledger()
    entry = JournalEntry(
        id="e1", date=date(2026, 1, 1), lines=(make_line("cash", debit="100.00"), make_line("equity", credit="100.00"))
    )
    ledger.post(entry)
    with pytest.raises(AccountingError, match="Duplicate journal entry id"):
        ledger.post(entry)


def test_post_rejects_entry_into_closed_period():
    ledger = _ledger()
    ledger.close_period(date(2026, 1, 31))
    entry = JournalEntry(
        id="e1", date=date(2026, 1, 15), lines=(make_line("cash", debit="100.00"), make_line("equity", credit="100.00"))
    )
    with pytest.raises(AccountingError, match="closed period"):
        ledger.post(entry)


def test_close_period_cannot_move_backwards():
    ledger = _ledger()
    ledger.close_period(date(2026, 1, 31))
    with pytest.raises(AccountingError, match="backwards"):
        ledger.close_period(date(2026, 1, 1))


def test_reversal_restores_balances():
    ledger = _ledger()
    ledger.post(
        JournalEntry(
            id="e1",
            date=date(2026, 1, 1),
            lines=(make_line("cash", debit="100.00"), make_line("equity", credit="100.00")),
        )
    )
    ledger.post(
        JournalEntry(
            id="e1-reversal",
            date=date(2026, 1, 2),
            lines=(make_line("cash", credit="100.00"), make_line("equity", debit="100.00")),
        )
    )
    balances = ledger.balances_as_of(date(2026, 1, 2))
    assert balances["cash"]["ending_balance"].is_zero()
    assert balances["equity"]["ending_balance"].is_zero()
