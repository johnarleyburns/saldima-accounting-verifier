from datetime import date

import pytest

from reference.accounting.journal import AccountingError, JournalEntry, make_line
from reference.sync.merge import BranchState, merge_branches


def _entry(entry_id: str, debit_account: str = "cash", credit_account: str = "revenue", amount: str = "100.00") -> JournalEntry:
    return JournalEntry(
        id=entry_id,
        date=date(2026, 1, 1),
        lines=(make_line(debit_account, debit=amount), make_line(credit_account, credit=amount)),
    )


def test_no_edits_or_new_entries_returns_the_base_unchanged():
    base = [_entry("e1"), _entry("e2")]
    result = merge_branches(base, BranchState(), BranchState())
    assert result.conflicts == []
    assert result.merged_entries == base


def test_independent_new_entries_from_both_branches_merge_cleanly():
    base = [_entry("e1")]
    branch_a = BranchState(new_entries=(_entry("e2"),))
    branch_b = BranchState(new_entries=(_entry("e3"),))
    result = merge_branches(base, branch_a, branch_b)
    assert result.conflicts == []
    assert {entry.id for entry in result.merged_entries} == {"e1", "e2", "e3"}


def test_edit_on_only_one_branch_is_applied_with_no_conflict():
    base = [_entry("e1", amount="100.00")]
    corrected = _entry("e1", amount="150.00")
    branch_a = BranchState(edits={"e1": corrected})
    branch_b = BranchState()
    result = merge_branches(base, branch_a, branch_b)
    assert result.conflicts == []
    assert result.merged_entries == [corrected]


def test_identical_edit_on_both_branches_is_not_a_conflict():
    base = [_entry("e1", amount="100.00")]
    corrected = _entry("e1", amount="150.00")
    branch_a = BranchState(edits={"e1": corrected})
    branch_b = BranchState(edits={"e1": corrected})
    result = merge_branches(base, branch_a, branch_b)
    assert result.conflicts == []
    assert result.merged_entries == [corrected]


def test_different_edits_on_both_branches_is_a_conflict_and_keeps_the_original():
    original = _entry("e1", amount="100.00")
    base = [original]
    edit_a = _entry("e1", amount="150.00")
    edit_b = _entry("e1", amount="200.00")
    branch_a = BranchState(edits={"e1": edit_a})
    branch_b = BranchState(edits={"e1": edit_b})

    result = merge_branches(base, branch_a, branch_b)

    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert conflict.original_entry_id == "e1"
    assert conflict.branch_a_edit == edit_a
    assert conflict.branch_b_edit == edit_b
    # The original entry is preserved, untouched, pending resolution --
    # neither edit silently wins.
    assert result.merged_entries == [original]


def test_edit_referencing_an_unknown_base_entry_is_rejected():
    base = [_entry("e1")]
    branch_a = BranchState(edits={"nonexistent": _entry("nonexistent", amount="1.00")})
    with pytest.raises(AccountingError, match="unknown base entry id"):
        merge_branches(base, branch_a, BranchState())


def test_both_branches_creating_a_new_entry_with_the_same_id_is_rejected():
    base = [_entry("e1")]
    branch_a = BranchState(new_entries=(_entry("e2", amount="1.00"),))
    branch_b = BranchState(new_entries=(_entry("e2", amount="2.00"),))
    with pytest.raises(AccountingError, match="same id"):
        merge_branches(base, branch_a, branch_b)


def test_a_new_entry_colliding_with_a_base_entry_id_is_rejected():
    base = [_entry("e1")]
    branch_a = BranchState(new_entries=(_entry("e1", amount="1.00"),))
    with pytest.raises(AccountingError, match="collides with a base entry id"):
        merge_branches(base, branch_a, BranchState())
