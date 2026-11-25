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
from reference.accounting.rounding import money


def test_balanced_entry_is_accepted():
    entry = JournalEntry(
        id="e1",
        date=date(2026, 1, 1),
        lines=(make_line("cash", debit="100.00"), make_line("revenue", credit="100.00")),
    )
    assert entry.total == money("100.00")


def test_unbalanced_entry_is_rejected():
    with pytest.raises(AccountingError, match="does not balance"):
        JournalEntry(
            id="e1",
            date=date(2026, 1, 1),
            lines=(make_line("cash", debit="100.00"), make_line("revenue", credit="99.00")),
        )


def test_zero_effect_entry_is_rejected():
    with pytest.raises(AccountingError, match="zero net effect"):
        JournalEntry(
            id="e1",
            date=date(2026, 1, 1),
            lines=(make_line("cash", debit="0.00"), make_line("revenue", credit="0.00")),
        )


def test_single_line_entry_is_rejected():
    with pytest.raises(AccountingError, match="at least two lines"):
        JournalEntry(id="e1", date=date(2026, 1, 1), lines=(make_line("cash", debit="100.00"),))


def test_line_cannot_have_both_debit_and_credit():
    with pytest.raises(AccountingError, match="both a debit and a credit"):
        make_line("cash", debit="100.00", credit="50.00")


def test_negative_amounts_rejected():
    with pytest.raises(AccountingError, match="non-negative"):
        make_line("cash", debit="-5.00")


def test_duplicate_account_id_rejected():
    chart = ChartOfAccounts()
    chart.add(Account(id="cash", name="Cash", type=AccountType.ASSET))
    with pytest.raises(AccountingError, match="Duplicate account id"):
        chart.add(Account(id="cash", name="Cash Again", type=AccountType.ASSET))


def test_unknown_parent_rejected():
    chart = ChartOfAccounts()
    with pytest.raises(AccountingError, match="unknown parent"):
        chart.add(Account(id="cash", name="Cash", type=AccountType.ASSET, parent_id="assets"))
