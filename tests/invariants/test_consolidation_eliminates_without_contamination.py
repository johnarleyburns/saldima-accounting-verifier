"""Consolidation-specific invariants (release-gate rules 6/7, docs/plan.md
section 20 / docs/release-gates.md): no multi-book operation creates
cross-book contamination, and no reconciliation operation silently
discards valid data. See reference/accounting/consolidation.py and
docs/reference-model.md's "double-entry invariants, numbered" section
for the general numbered invariants this complements.
"""

from datetime import date
from decimal import Decimal

import pytest

from reference.accounting import consolidation
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


def _entity_with_unique_account(unique_account_id: str, amount: str) -> consolidation.Entity:
    chart = ChartOfAccounts()
    chart.add(Account(id="cash", name="Cash", type=AccountType.ASSET))
    chart.add(Account(id=unique_account_id, name=unique_account_id, type=AccountType.EQUITY))
    ledger = Ledger(chart=chart)
    ledger.post(
        JournalEntry(
            id="e1",
            date=AS_OF,
            lines=(make_line("cash", debit=amount), make_line(unique_account_id, credit=amount)),
        )
    )
    return chart, ledger


def test_an_account_unique_to_one_entity_never_leaks_into_another_entitys_figures():
    """A balance-sheet line that exists on only one entity's chart must
    appear in the consolidated statement at exactly that entity's amount
    -- not doubled, not zeroed, not attributed to the wrong entity."""
    entity_a = _entity_with_unique_account("entity_a_only_equity", "100.00")
    entity_b = _entity_with_unique_account("entity_b_only_equity", "250.00")

    bs = consolidation.consolidated_balance_sheet([entity_a, entity_b], [], AS_OF, "test", "2026")

    assert bs.equity["entity_a_only_equity"] == Decimal("100.00")
    assert bs.equity["entity_b_only_equity"] == Decimal("250.00")
    bs.assert_balances()


def _entity_with_asset(account_id: str, amount: str) -> consolidation.Entity:
    chart = ChartOfAccounts()
    chart.add(Account(id="cash", name="Cash", type=AccountType.ASSET))
    chart.add(Account(id=account_id, name=account_id, type=AccountType.ASSET))
    ledger = Ledger(chart=chart)
    ledger.post(
        JournalEntry(
            id="e1",
            date=AS_OF,
            lines=(make_line(account_id, debit=amount), make_line("cash", credit=amount)),
        )
    )
    return chart, ledger


def _entity_with_liability(account_id: str, amount: str) -> consolidation.Entity:
    chart = ChartOfAccounts()
    chart.add(Account(id="cash", name="Cash", type=AccountType.ASSET))
    chart.add(Account(id=account_id, name=account_id, type=AccountType.LIABILITY))
    ledger = Ledger(chart=chart)
    ledger.post(
        JournalEntry(
            id="e1",
            date=AS_OF,
            lines=(make_line("cash", debit=amount), make_line(account_id, credit=amount)),
        )
    )
    return chart, ledger


def test_an_unreconciled_intercompany_balance_is_never_silently_dropped():
    """If two entities' supposedly-matching intercompany accounts don't
    actually net to zero, consolidation must raise -- not silently
    report a consolidated statement that happens to still balance by
    coincidentally dropping the discrepancy."""
    entity_a = _entity_with_asset("intercompany_receivable", "500.00")
    entity_b = _entity_with_liability("intercompany_payable", "499.99")

    with pytest.raises(AccountingError, match="does not net to zero"):
        consolidation.consolidated_trial_balance(
            [entity_a, entity_b],
            [consolidation.EliminationPair("intercompany_receivable", "intercompany_payable")],
            AS_OF,
            "test",
            "2026",
        )
