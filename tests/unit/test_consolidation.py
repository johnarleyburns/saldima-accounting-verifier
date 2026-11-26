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
PERIOD_START = date(2026, 1, 1)


def _parent() -> consolidation.Entity:
    chart = ChartOfAccounts()
    chart.add(Account(id="cash", name="Cash", type=AccountType.ASSET))
    chart.add(
        Account(
            id="investment_in_subsidiary", name="Investment in Subsidiary", type=AccountType.ASSET
        )
    )
    chart.add(Account(id="paid_in_capital", name="Paid-in Capital", type=AccountType.EQUITY))
    ledger = Ledger(chart=chart)
    ledger.post(
        JournalEntry(
            id="opening",
            date=PERIOD_START,
            lines=(
                make_line("cash", debit="1000.00"),
                make_line("paid_in_capital", credit="1000.00"),
            ),
        )
    )
    ledger.post(
        JournalEntry(
            id="formation",
            date=PERIOD_START,
            lines=(
                make_line("investment_in_subsidiary", debit="600.00"),
                make_line("cash", credit="600.00"),
            ),
        )
    )
    return chart, ledger


def _subsidiary(contributed_capital: str = "600.00") -> consolidation.Entity:
    chart = ChartOfAccounts()
    chart.add(Account(id="cash", name="Cash", type=AccountType.ASSET))
    chart.add(Account(id="common_stock", name="Common Stock", type=AccountType.EQUITY))
    ledger = Ledger(chart=chart)
    ledger.post(
        JournalEntry(
            id="formation",
            date=PERIOD_START,
            lines=(
                make_line("cash", debit=contributed_capital),
                make_line("common_stock", credit=contributed_capital),
            ),
        )
    )
    return chart, ledger


INVESTMENT_ELIMINATION = consolidation.EliminationPair("investment_in_subsidiary", "common_stock")


def test_matching_elimination_pair_is_removed_from_the_consolidated_trial_balance():
    tb = consolidation.consolidated_trial_balance(
        [_parent(), _subsidiary()], [INVESTMENT_ELIMINATION], AS_OF, "test", "2026"
    )
    assert "investment_in_subsidiary" not in tb.lines
    assert "common_stock" not in tb.lines
    tb.assert_balanced()


def test_same_id_accounts_across_entities_are_summed():
    tb = consolidation.consolidated_trial_balance(
        [_parent(), _subsidiary()], [INVESTMENT_ELIMINATION], AS_OF, "test", "2026"
    )
    # Parent: cash 1000.00 - 600.00 = 400.00. Subsidiary: cash 600.00.
    assert tb.lines["cash"].debit == Decimal("1000.00")


def test_mismatched_elimination_pair_raises():
    mismatched_subsidiary = _subsidiary(contributed_capital="601.00")
    with pytest.raises(AccountingError, match="does not net to zero"):
        consolidation.consolidated_trial_balance(
            [_parent(), mismatched_subsidiary], [INVESTMENT_ELIMINATION], AS_OF, "test", "2026"
        )


def test_consolidated_balance_sheet_balances_after_elimination():
    bs = consolidation.consolidated_balance_sheet(
        [_parent(), _subsidiary()], [INVESTMENT_ELIMINATION], AS_OF, "test", "2026"
    )
    assert "investment_in_subsidiary" not in bs.assets
    assert "common_stock" not in bs.equity
    bs.assert_balances()
    assert bs.total_assets == Decimal("1000.00")


def test_consolidated_balance_sheet_rejects_unclosed_revenue_or_expense():
    chart, ledger = _parent()
    chart.add(Account(id="revenue", name="Revenue", type=AccountType.REVENUE))
    ledger.post(
        JournalEntry(
            id="unclosed-revenue",
            date=AS_OF,
            lines=(make_line("cash", debit="50.00"), make_line("revenue", credit="50.00")),
        )
    )
    with pytest.raises(AccountingError, match="unclosed revenue/expense activity"):
        consolidation.consolidated_balance_sheet(
            [(chart, ledger), _subsidiary()], [INVESTMENT_ELIMINATION], AS_OF, "test", "2026"
        )


def test_consolidated_income_statement_eliminates_intercompany_revenue_and_expense():
    parent_chart, parent_ledger = _parent()
    parent_chart.add(
        Account(
            id="intercompany_fee_revenue", name="Intercompany Fee Revenue", type=AccountType.REVENUE
        )
    )
    parent_ledger.post(
        JournalEntry(
            id="fee",
            date=AS_OF,
            lines=(
                make_line("cash", debit="200.00"),
                make_line("intercompany_fee_revenue", credit="200.00"),
            ),
        )
    )
    sub_chart, sub_ledger = _subsidiary()
    sub_chart.add(
        Account(
            id="intercompany_fee_expense", name="Intercompany Fee Expense", type=AccountType.EXPENSE
        )
    )
    sub_ledger.post(
        JournalEntry(
            id="fee",
            date=AS_OF,
            lines=(
                make_line("intercompany_fee_expense", debit="200.00"),
                make_line("cash", credit="200.00"),
            ),
        )
    )

    fee_elimination = consolidation.EliminationPair(
        "intercompany_fee_expense", "intercompany_fee_revenue"
    )
    income = consolidation.consolidated_income_statement(
        [(parent_chart, parent_ledger), (sub_chart, sub_ledger)],
        [INVESTMENT_ELIMINATION, fee_elimination],
        PERIOD_START,
        AS_OF,
        "test",
        "2026",
    )
    assert "intercompany_fee_revenue" not in income.revenue
    assert "intercompany_fee_expense" not in income.expenses
    assert income.net_income == Decimal("0.00")
