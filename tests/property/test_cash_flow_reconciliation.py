"""Hypothesis-generalized coverage of the cash-flow reconciliation identity
(docs/reference-model.md's proof sketch: `operating_cash_flow ==
ending_cash - beginning_cash` for any consistent choice of deltas).

The six existing scenarios that exercise `cash_flow.generate` each hand-
verify one specific set of numbers. This proves the identity holds for
arbitrary randomly generated activity over a fixed chart, not just those
six.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from reference.accounting import cash_flow
from reference.accounting.journal import (
    Account,
    AccountType,
    ChartOfAccounts,
    JournalEntry,
    make_line,
)
from reference.accounting.ledger import Ledger

ACCOUNT_IDS = ("cash", "ar", "ap", "equity", "revenue", "expense")
PERIOD_START = date(2026, 1, 1)
PERIOD_END = date(2026, 12, 31)


def _build_chart() -> ChartOfAccounts:
    chart = ChartOfAccounts()
    chart.add(Account(id="cash", name="Cash", type=AccountType.ASSET))
    chart.add(Account(id="ar", name="Accounts Receivable", type=AccountType.ASSET))
    chart.add(Account(id="ap", name="Accounts Payable", type=AccountType.LIABILITY))
    chart.add(Account(id="equity", name="Equity", type=AccountType.EQUITY))
    chart.add(Account(id="revenue", name="Revenue", type=AccountType.REVENUE))
    chart.add(Account(id="expense", name="Expense", type=AccountType.EXPENSE))
    return chart


@st.composite
def entry_lists(draw: st.DrawFn, min_size: int = 1, max_size: int = 30) -> list[JournalEntry]:
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    entries = []
    for i in range(n):
        debit_account, credit_account = draw(
            st.tuples(st.sampled_from(ACCOUNT_IDS), st.sampled_from(ACCOUNT_IDS)).filter(
                lambda pair: pair[0] != pair[1]
            )
        )
        amount = draw(
            st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10000.00"), places=2)
        )
        offset_days = draw(st.integers(min_value=0, max_value=363))
        entries.append(
            JournalEntry(
                id=f"e{i}",
                date=PERIOD_START + timedelta(days=offset_days),
                lines=(
                    make_line(debit_account, debit=str(amount)),
                    make_line(credit_account, credit=str(amount)),
                ),
            )
        )
    return entries


@given(entries=entry_lists())
@settings(max_examples=100, deadline=None)
def test_cash_flow_reconciles_for_arbitrary_valid_ledgers(entries: list[JournalEntry]) -> None:
    chart = _build_chart()
    ledger = Ledger(chart=chart)
    for entry in entries:
        ledger.post(entry)

    statement = cash_flow.generate(
        ledger, chart, PERIOD_START, PERIOD_END, {"cash"}, "prop-test", "2026"
    )
    statement.assert_reconciles()  # must not raise
