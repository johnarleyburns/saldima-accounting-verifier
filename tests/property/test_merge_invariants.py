"""Hypothesis-generalized coverage of reference/sync/merge.py's semantics
(docs/reference-model.md's "merge.py models an edit as a replacement"
section). tests/unit/test_merge.py hand-picks specific ids and amounts;
here the *counts* of base/branch entries, and the specific amounts in a
conflicting edit, are randomly generated.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from reference.accounting.journal import JournalEntry, make_line
from reference.sync.merge import BranchState, merge_branches


def _entry(entry_id: str, amount: str = "100.00") -> JournalEntry:
    return JournalEntry(
        id=entry_id,
        date=date(2026, 1, 1),
        lines=(make_line("cash", debit=amount), make_line("revenue", credit=amount)),
    )


@given(
    base_count=st.integers(min_value=0, max_value=10),
    new_a_count=st.integers(min_value=0, max_value=10),
    new_b_count=st.integers(min_value=0, max_value=10),
)
@settings(max_examples=100, deadline=None)
def test_independent_new_entries_never_conflict_at_any_size(
    base_count: int, new_a_count: int, new_b_count: int
) -> None:
    base_entries = [_entry(f"base-{i}") for i in range(base_count)]
    branch_a = BranchState(new_entries=tuple(_entry(f"a-{i}") for i in range(new_a_count)))
    branch_b = BranchState(new_entries=tuple(_entry(f"b-{i}") for i in range(new_b_count)))

    result = merge_branches(base_entries, branch_a, branch_b)

    assert result.conflicts == []
    assert len(result.merged_entries) == base_count + new_a_count + new_b_count
    assert {entry.id for entry in result.merged_entries} == (
        {e.id for e in base_entries}
        | {e.id for e in branch_a.new_entries}
        | {e.id for e in branch_b.new_entries}
    )


@given(
    amount_a=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("100000.00"), places=2),
    amount_b=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("100000.00"), places=2),
)
@settings(max_examples=100, deadline=None)
def test_different_edits_on_both_branches_always_conflict_and_preserve_the_original(
    amount_a: Decimal, amount_b: Decimal
) -> None:
    if amount_a == amount_b:
        return  # not the case under test -- an identical edit on both branches is not a conflict.

    original = _entry("e1", amount="1.00")
    edit_a = _entry("e1", amount=str(amount_a))
    edit_b = _entry("e1", amount=str(amount_b))
    branch_a = BranchState(edits={"e1": edit_a})
    branch_b = BranchState(edits={"e1": edit_b})

    result = merge_branches([original], branch_a, branch_b)

    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert conflict.original_entry_id == "e1"
    assert conflict.branch_a_edit == edit_a
    assert conflict.branch_b_edit == edit_b
    assert result.merged_entries == [original]
