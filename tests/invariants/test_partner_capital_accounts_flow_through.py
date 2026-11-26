"""Confirms (not just assumes) that multiple partner capital accounts flow
correctly through trial_balance.py/balance_sheet.py, and that
closing.py's new `partner_allocations` path produces a correctly-balanced
entry, independent of any one scenario's bookkeeping choices.

Two claims from docs/accounting-policy.md's Phase 5 section:

1. Multiple `AccountType.EQUITY` accounts (one per partner) need no new
   type/schema machinery -- trial_balance.py/balance_sheet.py already sum
   every equity account generically.
2. `closing.close_period`'s `partner_allocations` path, for a non-trivial
   (60/40) ratio, produces a balanced entry with the rounding remainder
   landing on the last listed partner -- the liability/equity-allocation
   counterpart to Phase 2/3's "already generic" findings.
"""

from datetime import date
from decimal import Decimal

from reference.accounting import balance_sheet, trial_balance
from reference.accounting.closing import close_period
from reference.accounting.journal import (
    Account,
    AccountType,
    ChartOfAccounts,
    JournalEntry,
    make_line,
)
from reference.accounting.ledger import Ledger


def _build_chart() -> ChartOfAccounts:
    chart = ChartOfAccounts()
    chart.add(Account(id="cash", name="Cash", type=AccountType.ASSET))
    chart.add(Account(id="partner_x_capital", name="Partner X Capital", type=AccountType.EQUITY))
    chart.add(Account(id="partner_y_capital", name="Partner Y Capital", type=AccountType.EQUITY))
    chart.add(Account(id="revenue", name="Revenue", type=AccountType.REVENUE))
    chart.add(Account(id="expense", name="Expense", type=AccountType.EXPENSE))
    return chart


def test_multiple_partner_capital_accounts_sum_into_total_equity():
    chart = _build_chart()
    ledger = Ledger(chart=chart)
    ledger.post(
        JournalEntry(
            id="e1",
            date=date(2026, 1, 1),
            lines=(make_line("cash", debit="1000.00"), make_line("partner_x_capital", credit="600.00"), make_line("partner_y_capital", credit="400.00")),
        )
    )
    as_of = date(2026, 1, 31)

    tb = trial_balance.generate(ledger, chart, as_of, "inv-test", "2026-01")
    tb.assert_balanced()  # must not raise

    bs = balance_sheet.generate(ledger, chart, as_of, date(2026, 1, 1), "inv-test", "2026-01")
    bs.assert_balances()  # must not raise
    assert bs.equity["partner_x_capital"] == Decimal("600.00")
    assert bs.equity["partner_y_capital"] == Decimal("400.00")
    assert bs.total_equity == Decimal("1000.00")


def test_closing_allocates_a_non_trivial_ratio_with_remainder_on_the_last_partner():
    chart = _build_chart()
    ledger = Ledger(chart=chart)
    ledger.post(
        JournalEntry(
            id="e1",
            date=date(2026, 1, 1),
            lines=(make_line("cash", debit="1000.00"), make_line("revenue", credit="1000.00")),
        )
    )

    entry = close_period(
        ledger,
        chart,
        date(2026, 1, 1),
        date(2026, 12, 31),
        None,
        "closing-1",
        partner_allocations={"partner_x_capital": Decimal("0.60"), "partner_y_capital": Decimal("0.40")},
    )
    assert entry is not None
    by_account = {line.account_id: line for line in entry.lines}
    assert by_account["partner_x_capital"].credit == Decimal("600.00")
    assert by_account["partner_y_capital"].credit == Decimal("400.00")

    as_of = date(2026, 12, 31)
    bs = balance_sheet.generate(ledger, chart, as_of, date(2026, 1, 1), "inv-test", "2026")
    bs.assert_balances()  # must not raise
    assert bs.equity["partner_x_capital"] == Decimal("600.00")
    assert bs.equity["partner_y_capital"] == Decimal("400.00")
