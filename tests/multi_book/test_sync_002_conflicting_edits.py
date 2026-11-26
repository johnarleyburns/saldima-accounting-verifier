"""SYNC-002: conflicting edits to the same transaction on two branches,
merged with the conflict preserved, never silently resolved (docs/plan.md
section 14 and section 19; release-gate rule 7 -- docs/release-gates.md).

A transaction was originally miscategorized. Two devices, both offline,
independently "correct" it in different ways: device A recategorizes it
to the right expense account at the same amount; device B instead fixes
what it thinks was an amount typo, keeping the original (wrong) account.
Neither device has seen the other's edit. Merging two different edits of
the same original entry must not silently pick a winner or drop either
proposed correction -- it must flag the conflict and leave the original,
unedited entry in place pending human resolution.
"""

from datetime import date

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
    chart.add(Account(id="misc_expense", name="Miscellaneous Expense", type=AccountType.EXPENSE))
    chart.add(Account(id="supplies_expense", name="Supplies Expense", type=AccountType.EXPENSE))
    return chart


def test_merging_two_different_edits_of_the_same_entry_is_a_preserved_conflict():
    chart = _build_chart()
    original = JournalEntry(
        id="txn-1",
        date=date(2026, 1, 10),
        lines=(make_line("misc_expense", debit="500.00"), make_line("cash", credit="500.00")),
        memo="office supplies",
    )
    base_entries = [
        JournalEntry(
            id="base-1",
            date=date(2026, 1, 1),
            lines=(make_line("cash", debit="10000.00"), make_line("equity", credit="10000.00")),
        ),
        original,
    ]

    # Device A: recategorizes to the correct expense account, same amount.
    edit_a = JournalEntry(
        id="txn-1",
        date=date(2026, 1, 10),
        lines=(make_line("supplies_expense", debit="500.00"), make_line("cash", credit="500.00")),
        memo="office supplies (recategorized)",
    )
    # Device B: independently "fixes" what it thought was an amount typo,
    # keeping the original (wrong) account.
    edit_b = JournalEntry(
        id="txn-1",
        date=date(2026, 1, 10),
        lines=(make_line("misc_expense", debit="550.00"), make_line("cash", credit="550.00")),
        memo="office supplies (amount corrected)",
    )

    branch_a = BranchState(edits={"txn-1": edit_a})
    branch_b = BranchState(edits={"txn-1": edit_b})

    result = merge_branches(base_entries, branch_a, branch_b)

    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert conflict.original_entry_id == "txn-1"
    assert conflict.branch_a_edit == edit_a
    assert conflict.branch_b_edit == edit_b

    # The original entry survives, untouched -- neither proposed
    # correction was silently applied or discarded.
    assert original in result.merged_entries
    assert edit_a not in result.merged_entries
    assert edit_b not in result.merged_entries

    # Nothing about the merge corrupts the ledger: it still balances even
    # with the conflict left unresolved.
    merged_ledger = Ledger(chart=chart)
    for entry in result.merged_entries:
        merged_ledger.post(entry)
    tb = generate_trial_balance(merged_ledger, chart, date(2026, 12, 31), "sync-002", "2026")
    tb.assert_balanced()  # must not raise
