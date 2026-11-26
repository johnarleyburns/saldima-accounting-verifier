"""Confirms (not just assumes) that AR/AP/prepaid/deferred-revenue accounts flow
correctly through trial_balance.py, balance_sheet.py, and cash_flow.py without
any Phase 2 code changes to those modules.

trial_balance.py, income_statement.py, balance_sheet.py, and closing.py are
already fully generic over AccountType (see docs/reference-model.md), and
cash_flow.py already adjusts for the change in *every* non-cash asset/
liability/equity account -- an asset increase is a use of cash, a liability
increase is a source of cash. That is exactly the correct treatment for
accounts receivable, accounts payable, prepaid expenses, and deferred
revenue, not just a coincidence of Phase 1's scenarios. This test builds a
small hand-built ledger with those four account types and proves it,
independent of any one scenario's bookkeeping choices -- see
docs/accounting-policy.md.
"""

from datetime import date
from decimal import Decimal

from reference.accounting import balance_sheet, cash_flow, trial_balance
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
    chart.add(Account(id="accounts_receivable", name="Accounts Receivable", type=AccountType.ASSET))
    chart.add(Account(id="prepaid_expense", name="Prepaid Expense", type=AccountType.ASSET))
    chart.add(Account(id="accounts_payable", name="Accounts Payable", type=AccountType.LIABILITY))
    chart.add(Account(id="deferred_revenue", name="Deferred Revenue", type=AccountType.LIABILITY))
    chart.add(Account(id="equity", name="Equity", type=AccountType.EQUITY))
    chart.add(Account(id="revenue", name="Revenue", type=AccountType.REVENUE))
    chart.add(Account(id="expense", name="Expense", type=AccountType.EXPENSE))
    return chart


def test_ar_ap_prepaid_deferred_revenue_flow_through_trial_balance_and_balance_sheet():
    chart = _build_chart()
    ledger = Ledger(chart=chart)
    ledger.post(
        JournalEntry(
            id="e1",
            date=date(2026, 1, 1),
            lines=(make_line("cash", debit="10000.00"), make_line("equity", credit="10000.00")),
        )
    )
    # A credit sale: revenue earned now, cash collected later.
    ledger.post(
        JournalEntry(
            id="e2",
            date=date(2026, 1, 5),
            lines=(make_line("accounts_receivable", debit="500.00"), make_line("revenue", credit="500.00")),
        )
    )
    # A credit purchase: expense incurred now, cash paid later.
    ledger.post(
        JournalEntry(
            id="e3",
            date=date(2026, 1, 10),
            lines=(make_line("expense", debit="200.00"), make_line("accounts_payable", credit="200.00")),
        )
    )
    # Prepaying an expense: cash out now, asset consumed later.
    ledger.post(
        JournalEntry(
            id="e4",
            date=date(2026, 1, 15),
            lines=(make_line("prepaid_expense", debit="300.00"), make_line("cash", credit="300.00")),
        )
    )
    # Collecting cash in advance of earning it.
    ledger.post(
        JournalEntry(
            id="e5",
            date=date(2026, 1, 20),
            lines=(make_line("cash", debit="400.00"), make_line("deferred_revenue", credit="400.00")),
        )
    )

    as_of = date(2026, 1, 31)
    tb = trial_balance.generate(ledger, chart, as_of, "inv-test", "2026-01")
    tb.assert_balanced()  # must not raise

    bs = balance_sheet.generate(ledger, chart, as_of, date(2026, 1, 1), "inv-test", "2026-01")
    bs.assert_balances()  # must not raise
    assert bs.assets["accounts_receivable"] == Decimal("500.00")
    assert bs.assets["prepaid_expense"] == Decimal("300.00")
    assert bs.liabilities["accounts_payable"] == Decimal("200.00")
    assert bs.liabilities["deferred_revenue"] == Decimal("400.00")


def test_asset_increase_is_a_use_of_cash_and_liability_increase_is_a_source():
    chart = _build_chart()
    ledger = Ledger(chart=chart)
    ledger.post(
        JournalEntry(
            id="e1",
            date=date(2026, 1, 1),
            lines=(make_line("cash", debit="10000.00"), make_line("equity", credit="10000.00")),
        )
    )
    ledger.post(
        JournalEntry(
            id="e2",
            date=date(2026, 1, 5),
            lines=(make_line("accounts_receivable", debit="500.00"), make_line("revenue", credit="500.00")),
        )
    )
    ledger.post(
        JournalEntry(
            id="e3",
            date=date(2026, 1, 10),
            lines=(make_line("expense", debit="200.00"), make_line("accounts_payable", credit="200.00")),
        )
    )
    ledger.post(
        JournalEntry(
            id="e4",
            date=date(2026, 1, 15),
            lines=(make_line("prepaid_expense", debit="300.00"), make_line("cash", credit="300.00")),
        )
    )
    ledger.post(
        JournalEntry(
            id="e5",
            date=date(2026, 1, 20),
            lines=(make_line("cash", debit="400.00"), make_line("deferred_revenue", credit="400.00")),
        )
    )

    statement = cash_flow.generate(
        ledger, chart, date(2026, 1, 1), date(2026, 1, 31), {"cash"}, "inv-test", "2026-01"
    )
    statement.assert_reconciles()  # must not raise

    # Asset increases are a *use* of cash (negative adjustments)...
    assert statement.operating_adjustments["accounts_receivable"] == Decimal("-500.00")
    assert statement.operating_adjustments["prepaid_expense"] == Decimal("-300.00")
    # ...and liability increases are a *source* of cash (positive adjustments).
    assert statement.operating_adjustments["accounts_payable"] == Decimal("200.00")
    assert statement.operating_adjustments["deferred_revenue"] == Decimal("400.00")
