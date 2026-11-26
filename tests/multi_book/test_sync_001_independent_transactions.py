"""SYNC-001: concurrent independent transactions on two branches, merged
with no conflicts (docs/plan.md section 14 and section 19).

Two devices go offline from a common base book and each independently
record one new, unrelated transaction. Merging must reconcile cleanly:
no conflicts, and the merged ledger's trial balance must equal what you'd
get by posting every entry (base + both branches') to a single ledger
directly -- an independent cross-check that the merge didn't lose or
duplicate anything.
"""

from datetime import date
from decimal import Decimal

from reference.accounting.journal import (
    Account,
    AccountType,
    ChartOfAccounts,
    JournalEntry,
    make_line,
)
from reference.accounting.ledger import Ledger
from reference.accounting.trial_balance import generate as generate_trial_balance
from reference.sync.merge import BranchState, merge_branches


def _build_chart() -> ChartOfAccounts:
    chart = ChartOfAccounts()
    chart.add(Account(id="cash", name="Cash", type=AccountType.ASSET))
    chart.add(Account(id="equity", name="Equity", type=AccountType.EQUITY))
    chart.add(Account(id="revenue", name="Revenue", type=AccountType.REVENUE))
    chart.add(Account(id="expense", name="Expense", type=AccountType.EXPENSE))
    return chart


def _ledger_from_entries(chart: ChartOfAccounts, entries: list[JournalEntry]) -> Ledger:
    ledger = Ledger(chart=chart)
    for entry in entries:
        ledger.post(entry)
    return ledger


def test_merging_two_branches_with_independent_transactions_has_no_conflicts():
    chart = _build_chart()
    base_entries = [
        JournalEntry(
            id="base-1",
            date=date(2026, 1, 1),
            lines=(make_line("cash", debit="10000.00"), make_line("equity", credit="10000.00")),
        )
    ]

    # Device A (offline): records a $500.00 sale nobody else has seen yet.
    branch_a = BranchState(
        new_entries=(
            JournalEntry(
                id="device-a-1",
                date=date(2026, 1, 5),
                lines=(make_line("cash", debit="500.00"), make_line("revenue", credit="500.00")),
            ),
        )
    )
    # Device B (offline, never saw device A's sale): records an unrelated
    # $200.00 expense payment.
    branch_b = BranchState(
        new_entries=(
            JournalEntry(
                id="device-b-1",
                date=date(2026, 1, 6),
                lines=(make_line("expense", debit="200.00"), make_line("cash", credit="200.00")),
            ),
        )
    )

    result = merge_branches(base_entries, branch_a, branch_b)
    assert result.conflicts == []
    assert {entry.id for entry in result.merged_entries} == {"base-1", "device-a-1", "device-b-1"}

    merged_ledger = _ledger_from_entries(chart, result.merged_entries)
    merged_tb = generate_trial_balance(merged_ledger, chart, date(2026, 12, 31), "sync-001", "2026")
    merged_tb.assert_balanced()  # must not raise

    # Independent cross-check: a ledger built by posting every entry
    # directly (base + both branches', in a different order) must produce
    # the identical trial balance -- proving the merge reconciled exactly,
    # not just "a" balanced result.
    direct_entries = base_entries + list(branch_b.new_entries) + list(branch_a.new_entries)
    direct_ledger = _ledger_from_entries(_build_chart(), direct_entries)
    direct_tb = generate_trial_balance(direct_ledger, chart, date(2026, 12, 31), "sync-001", "2026")

    assert merged_tb.lines == direct_tb.lines
    assert merged_ledger.balances_as_of(date(2026, 12, 31))["cash"]["ending_balance"] == Decimal("10300.00")
