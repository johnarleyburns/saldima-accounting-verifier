"""Multi-book branch merge and conflict detection (docs/plan.md section 14).

Pure Decimal/dataclass logic over `JournalEntry`/`ChartOfAccounts`
(reference/accounting/journal.py) -- no change to `Ledger` itself, and no
dependency on Saldima production code. This validates book isolation and
multi-device merge/reconciliation *semantics*, deliberately without
duplicating Saldima's production cryptographic/sync implementation (see
docs/plan.md section 14 and docs/accounting-policy.md).

A **book** is just a `(ChartOfAccounts, list[JournalEntry])` pair -- the
existing primitives. A **branch** is one device's local view of a book
that started from a common base: it may *edit* an existing base entry
(modeled as a locally-tracked replacement, since `JournalEntry` stays
immutable once posted -- invariant 6, docs/plan.md section 13) and/or add
brand-new entries that aren't corrections of anything.

`SYNC-001` ("concurrent independent transactions"): two branches each add
new entries only, with no overlap -- merging is a clean union, and
`merge_branches` reports zero conflicts.

`SYNC-002` ("conflicting transaction edits"): the same base entry gets a
*different* correcting replacement on each branch. The release gate
("no reconciliation operation silently discards valid accounting data" --
docs/release-gates.md) means neither replacement can simply win by
default: `merge_branches` records an `EditConflict` and keeps the
*original* entry, untouched, in the merged result, pending human
resolution -- it never silently picks one side or drops data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from reference.accounting.journal import AccountingError, JournalEntry


@dataclass(frozen=True)
class BranchState:
    """One branch's local changes relative to a common base.

    `edits`: `{original_entry_id: replacement_entry}` -- entries from the
    base that this branch has corrected locally. `new_entries`: entries
    this branch created that don't correct anything in the base.
    """

    edits: dict[str, JournalEntry] = field(default_factory=dict)
    new_entries: tuple[JournalEntry, ...] = ()


@dataclass(frozen=True)
class EditConflict:
    """Two branches independently edited the same base entry differently."""

    original_entry_id: str
    branch_a_edit: JournalEntry
    branch_b_edit: JournalEntry


@dataclass(frozen=True)
class MergeResult:
    merged_entries: list[JournalEntry]
    conflicts: list[EditConflict]


def merge_branches(base_entries: list[JournalEntry], branch_a: BranchState, branch_b: BranchState) -> MergeResult:
    """Merge two branches that diverged from the same `base_entries`.

    For each base entry: edited identically on both branches, or only on
    one -> apply that edit, no conflict. Edited differently on both ->
    record an `EditConflict` and keep the *original* entry unedited in the
    merged result (see module docstring). Then append every new entry
    from both branches. Raises `AccountingError` if a branch edits an
    entry id that isn't in `base_entries`, or if the two branches (or a
    branch and the base) independently used the same id for two different
    new entries -- a different, simpler kind of problem this reference
    model only needs to detect, not resolve.
    """
    base_ids = {entry.id for entry in base_entries}
    for edited_id in set(branch_a.edits) | set(branch_b.edits):
        if edited_id not in base_ids:
            raise AccountingError(f"branch edit references unknown base entry id: {edited_id!r}")

    new_ids_a = {entry.id for entry in branch_a.new_entries}
    new_ids_b = {entry.id for entry in branch_b.new_entries}
    colliding_new_ids = new_ids_a & new_ids_b
    if colliding_new_ids:
        raise AccountingError(
            f"both branches independently created new entries with the same id(s): {sorted(colliding_new_ids)}"
        )
    colliding_with_base = (new_ids_a | new_ids_b) & base_ids
    if colliding_with_base:
        raise AccountingError(
            f"a branch's new entry id collides with a base entry id: {sorted(colliding_with_base)}"
        )

    conflicts: list[EditConflict] = []
    merged_entries: list[JournalEntry] = []
    for entry in base_entries:
        edit_a = branch_a.edits.get(entry.id)
        edit_b = branch_b.edits.get(entry.id)
        if edit_a is not None and edit_b is not None:
            if edit_a == edit_b:
                merged_entries.append(edit_a)
            else:
                conflicts.append(EditConflict(entry.id, edit_a, edit_b))
                merged_entries.append(entry)
        elif edit_a is not None:
            merged_entries.append(edit_a)
        elif edit_b is not None:
            merged_entries.append(edit_b)
        else:
            merged_entries.append(entry)

    merged_entries.extend(branch_a.new_entries)
    merged_entries.extend(branch_b.new_entries)

    return MergeResult(merged_entries=merged_entries, conflicts=conflicts)
