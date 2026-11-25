"""Core double-entry invariants from docs/plan.md section 13, items 1-3, 6-7.

These exercise the invariants directly on hand-built ledgers. Hypothesis-
based randomized coverage of the same invariants across generated books is
planned for tests/property (Phase 7) — see docs/test-categories.md.
"""

from datetime import date
from decimal import Decimal

import pytest

from reference.accounting import trial_balance
from reference.accounting.journal import (
    Account,
    AccountingError,
    AccountType,
    ChartOfAccounts,
    JournalEntry,
    make_line,
)
from reference.accounting.ledger import Ledger


def _build_ledger() -> tuple[ChartOfAccounts, Ledger]:
    chart = ChartOfAccounts()
    chart.add(Account(id="cash", name="Cash", type=AccountType.ASSET))
    chart.add(Account(id="ar", name="Accounts Receivable", type=AccountType.ASSET))
    chart.add(Account(id="ap", name="Accounts Payable", type=AccountType.LIABILITY))
    chart.add(Account(id="equity", name="Equity", type=AccountType.EQUITY))
    chart.add(Account(id="revenue", name="Revenue", type=AccountType.REVENUE))
    chart.add(Account(id="expense", name="Expense", type=AccountType.EXPENSE))
    ledger = Ledger(chart=chart)
    return chart, ledger


def test_invariant_1_every_posted_entry_balances():
    # Enforced at construction time -- JournalEntry.__post_init__ raises
    # before an unbalanced entry can even be built, let alone posted.
    with pytest.raises(AccountingError):
        JournalEntry(
            id="bad", date=date(2026, 1, 1), lines=(make_line("cash", debit="10.00"), make_line("equity", credit="9.00"))
        )


def test_invariant_2_trial_balance_always_balances_for_arbitrary_balanced_postings():
    chart, ledger = _build_ledger()
    postings = [
        (make_line("cash", debit="1000.00"), make_line("equity", credit="1000.00")),
        (make_line("ar", debit="250.00"), make_line("revenue", credit="250.00")),
        (make_line("cash", debit="250.00"), make_line("ar", credit="250.00")),
        (make_line("expense", debit="75.00"), make_line("ap", credit="75.00")),
        (make_line("ap", debit="75.00"), make_line("cash", credit="75.00")),
    ]
    for i, lines in enumerate(postings):
        ledger.post(JournalEntry(id=f"e{i}", date=date(2026, 1, i + 1), lines=lines))

    tb = trial_balance.generate(ledger, chart, date(2026, 1, 31), "inv-test", "2026-01")
    tb.assert_balanced()  # must not raise
    assert tb.total_debit == tb.total_credit


def test_invariant_3_accounting_equation_detects_a_broken_ledger():
    """If a ledger somehow ends up unbalanced, balance_sheet must say so, not
    silently report an incorrect balance sheet."""
    from reference.accounting import balance_sheet

    chart, ledger = _build_ledger()
    ledger.post(
        JournalEntry(
            id="e1", date=date(2026, 1, 1), lines=(make_line("cash", debit="100.00"), make_line("equity", credit="100.00"))
        )
    )
    bs = balance_sheet.generate(ledger, chart, date(2026, 1, 31), date(2026, 1, 1), "inv-test", "2026-01")
    bs.assert_balances()  # must not raise for a genuinely balanced ledger

    # Now simulate a broken balance sheet object directly (we cannot produce
    # an unbalanced one through the ledger, since every entry is enforced
    # balanced at construction -- this checks the detector itself fires).
    broken = balance_sheet.BalanceSheet(
        scenario_id="inv-test",
        period="2026-01",
        as_of=date(2026, 1, 31),
        assets={"cash": Decimal("100.00")},
        liabilities={},
        equity={"equity": Decimal("50.00")},
    )
    with pytest.raises(AccountingError, match="accounting equation"):
        broken.assert_balances()


def test_invariant_6_posted_transactions_are_immutable():
    """JournalEntry and JournalLine are frozen dataclasses; there is no
    in-place mutation API on Ledger other than post() (append-only)."""
    _, ledger = _build_ledger()
    entry = JournalEntry(
        id="e1", date=date(2026, 1, 1), lines=(make_line("cash", debit="100.00"), make_line("equity", credit="100.00"))
    )
    ledger.post(entry)
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        entry.date = date(2026, 2, 1)  # type: ignore[misc]


def test_invariant_7_reversal_restores_original_balances():
    _, ledger = _build_ledger()
    original = JournalEntry(
        id="e1", date=date(2026, 1, 1), lines=(make_line("cash", debit="500.00"), make_line("revenue", credit="500.00"))
    )
    ledger.post(original)
    reversal = JournalEntry(
        id="e1-rev", date=date(2026, 1, 2), lines=(make_line("cash", credit="500.00"), make_line("revenue", debit="500.00"))
    )
    ledger.post(reversal)

    balances = ledger.balances_as_of(date(2026, 1, 2))
    assert balances["cash"]["ending_balance"].is_zero()
    assert balances["revenue"]["ending_balance"].is_zero()


def test_invariant_8_every_split_references_a_valid_account():
    _, ledger = _build_ledger()
    entry = JournalEntry(
        id="e1", date=date(2026, 1, 1), lines=(make_line("cash", debit="1.00"), make_line("nonexistent", credit="1.00"))
    )
    with pytest.raises(AccountingError, match="unknown account"):
        ledger.post(entry)


def test_invariant_12_closing_does_not_change_historical_entries():
    from reference.accounting import closing

    chart, ledger = _build_ledger()
    ledger.post(
        JournalEntry(
            id="e1", date=date(2026, 1, 1), lines=(make_line("cash", debit="1000.00"), make_line("revenue", credit="1000.00"))
        )
    )
    before = ledger.balances_as_of(date(2026, 1, 1))["revenue"]["ending_balance"]
    closing.close_period(ledger, chart, date(2026, 1, 1), date(2026, 12, 31), "equity", "closing-1")
    # The original entry's own recorded amounts never change -- only a new
    # entry is appended.
    original_entry = next(e for e in ledger.entries if e.id == "e1")
    assert original_entry.lines[0].debit == Decimal("1000.00")
    assert before == Decimal("1000.00")
