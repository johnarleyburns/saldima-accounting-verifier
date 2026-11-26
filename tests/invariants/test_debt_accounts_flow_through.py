"""Confirms (not just assumes) that a liability tagged `cash_flow_category:
financing` flows correctly through cash_flow.py, independent of any one
scenario's bookkeeping choices.

`FA-001`/`FA-002` (Phase 3) already proved `cash_flow_category` tagging
works on the *asset* side (the equipment purchase, tagged `investing`).
This is the first dedicated proof it also works on the *liability* side,
for both directions: a liability increase (loan proceeds) and a liability
decrease (a principal repayment) -- see docs/accounting-policy.md.
"""

from datetime import date
from decimal import Decimal

from reference.accounting import cash_flow
from reference.accounting.journal import (
    Account,
    AccountType,
    CashFlowCategory,
    ChartOfAccounts,
    JournalEntry,
    make_line,
)
from reference.accounting.ledger import Ledger


def _build_chart() -> ChartOfAccounts:
    chart = ChartOfAccounts()
    chart.add(Account(id="cash", name="Cash", type=AccountType.ASSET))
    chart.add(
        Account(
            id="loan_payable",
            name="Loan Payable",
            type=AccountType.LIABILITY,
            cash_flow_category=CashFlowCategory.FINANCING,
        )
    )
    chart.add(Account(id="equity", name="Equity", type=AccountType.EQUITY))
    chart.add(Account(id="interest_expense", name="Interest Expense", type=AccountType.EXPENSE))
    return chart


def test_loan_proceeds_are_a_financing_source_of_cash():
    chart = _build_chart()
    ledger = Ledger(chart=chart)
    ledger.post(
        JournalEntry(
            id="e1",
            date=date(2026, 1, 1),
            lines=(make_line("cash", debit="1000.00"), make_line("equity", credit="1000.00")),
        )
    )
    ledger.post(
        JournalEntry(
            id="e2",
            date=date(2026, 1, 1),
            lines=(make_line("cash", debit="10000.00"), make_line("loan_payable", credit="10000.00")),
        )
    )

    statement = cash_flow.generate(
        ledger, chart, date(2026, 1, 1), date(2026, 1, 31), {"cash"}, "inv-test", "2026-01"
    )
    statement.assert_reconciles()  # must not raise

    assert statement.financing_activities == {"loan_payable": Decimal("10000.00")}
    assert "loan_payable" not in statement.operating_adjustments


def test_principal_repayment_is_a_financing_use_of_cash():
    chart = _build_chart()
    ledger = Ledger(chart=chart)
    ledger.post(
        JournalEntry(
            id="e1",
            date=date(2026, 1, 1),
            lines=(make_line("cash", debit="10000.00"), make_line("loan_payable", credit="10000.00")),
        )
    )
    ledger.post(
        JournalEntry(
            id="e2",
            date=date(2026, 2, 28),
            lines=(
                make_line("interest_expense", debit="50.00"),
                make_line("loan_payable", debit="900.00"),
                make_line("cash", credit="950.00"),
            ),
        )
    )

    statement = cash_flow.generate(
        ledger, chart, date(2026, 2, 1), date(2026, 2, 28), {"cash"}, "inv-test", "2026-02"
    )
    statement.assert_reconciles()  # must not raise

    # The principal repayment (a liability decrease) is a financing use of
    # cash; interest stays in net_income (via the expense) and never
    # appears as a separate adjustment line at all.
    assert statement.financing_activities == {"loan_payable": Decimal("-900.00")}
    assert "loan_payable" not in statement.operating_adjustments
    assert statement.net_income == Decimal("-50.00")
