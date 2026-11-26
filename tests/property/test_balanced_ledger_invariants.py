"""Hypothesis-generalized coverage of invariants 2 and 3 (docs/plan.md
section 13; see docs/reference-model.md's "double-entry invariants,
numbered" section), plus a genuinely new property this phase adds:
posting order must not affect final balances (idempotent replay).

tests/invariants/test_double_entry_invariants.py proves these on a
handful of hand-picked postings. Here the postings themselves are
randomly generated over the same fixed six-account chart, so the
property holds over a much wider slice of the input space, not just the
examples someone thought to write down.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from reference.accounting import balance_sheet, trial_balance
from reference.accounting.journal import (
    Account,
    AccountType,
    ChartOfAccounts,
    JournalEntry,
    make_line,
)
from reference.accounting.ledger import Ledger

ACCOUNT_IDS = ("cash", "ar", "ap", "equity", "revenue", "expense")
FISCAL_YEAR_START = date(2026, 1, 1)
AS_OF = date(2026, 12, 31)


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
    """A list of balanced two-line entries over ACCOUNT_IDS, all dated
    within the single fiscal year [FISCAL_YEAR_START, AS_OF], with
    sequential ids so no draw can collide.
    """
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
                date=FISCAL_YEAR_START + timedelta(days=offset_days),
                lines=(
                    make_line(debit_account, debit=str(amount)),
                    make_line(credit_account, credit=str(amount)),
                ),
            )
        )
    return entries


@given(entries=entry_lists())
@settings(max_examples=100, deadline=None)
def test_trial_balance_always_balances_for_arbitrary_valid_postings(
    entries: list[JournalEntry],
) -> None:
    chart = _build_chart()
    ledger = Ledger(chart=chart)
    for entry in entries:
        ledger.post(entry)

    tb = trial_balance.generate(ledger, chart, AS_OF, "prop-test", "2026")
    tb.assert_balanced()  # must not raise
    assert tb.total_debit == tb.total_credit


@given(entries=entry_lists())
@settings(max_examples=100, deadline=None)
def test_accounting_equation_holds_for_arbitrary_valid_ledgers(entries: list[JournalEntry]) -> None:
    chart = _build_chart()
    ledger = Ledger(chart=chart)
    for entry in entries:
        ledger.post(entry)

    bs = balance_sheet.generate(ledger, chart, AS_OF, FISCAL_YEAR_START, "prop-test", "2026")
    bs.assert_balances()  # must not raise


@given(entries=entry_lists(), seed=st.integers(min_value=0, max_value=1_000_000))
@settings(max_examples=50, deadline=None)
def test_posting_order_does_not_affect_final_balances(
    entries: list[JournalEntry], seed: int
) -> None:
    ledger_in_original_order = Ledger(chart=_build_chart())
    for entry in entries:
        ledger_in_original_order.post(entry)

    shuffled = list(entries)
    random.Random(seed).shuffle(shuffled)
    ledger_in_shuffled_order = Ledger(chart=_build_chart())
    for entry in shuffled:
        ledger_in_shuffled_order.post(entry)

    balances_original = ledger_in_original_order.balances_as_of(AS_OF)
    balances_shuffled = ledger_in_shuffled_order.balances_as_of(AS_OF)
    for account_id in ACCOUNT_IDS:
        assert (
            balances_original[account_id]["ending_balance"]
            == balances_shuffled[account_id]["ending_balance"]
        )
