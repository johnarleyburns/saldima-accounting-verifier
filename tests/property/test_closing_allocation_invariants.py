"""Hypothesis-generalized coverage of closing.py's partner_allocations
remainder-to-last convention (see docs/reference-model.md's Phase 5
section): for *any* number of partner capital accounts and *any* ratio
split, the amount actually allocated across them must sum to exactly the
period's net income/loss, with zero rounding drift.

`PART-001`'s reviewed fixture hand-verifies one specific 50/50 split.
This proves the underlying convention for arbitrary partner counts and
ratios, not just that one case.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from reference.accounting import closing
from reference.accounting.journal import (
    Account,
    AccountType,
    ChartOfAccounts,
    JournalEntry,
    make_line,
)
from reference.accounting.ledger import Ledger
from reference.accounting.rounding import ZERO

PERIOD_START = date(2026, 1, 1)
PERIOD_END = date(2026, 12, 31)


@st.composite
def partner_ratios(
    draw: st.DrawFn, min_partners: int = 2, max_partners: int = 6
) -> dict[str, Decimal]:
    """n partner ratios, as exact two-decimal-place Decimals, that always
    sum to exactly Decimal("1.00") by construction: draw n-1 distinct
    integer cut points in [1, 99], and turn the consecutive differences
    (which always sum to 100) into ratios diff/100.
    """
    n = draw(st.integers(min_value=min_partners, max_value=max_partners))
    cuts = sorted(
        draw(
            st.lists(
                st.integers(min_value=1, max_value=99), min_size=n - 1, max_size=n - 1, unique=True
            )
        )
    )
    boundaries = [0, *cuts, 100]
    diffs = [boundaries[i + 1] - boundaries[i] for i in range(n)]
    return {f"partner_{i}": Decimal(diff) / Decimal(100) for i, diff in enumerate(diffs)}


@given(
    ratios=partner_ratios(),
    net_income=st.decimals(
        min_value=Decimal("-100000.00"), max_value=Decimal("100000.00"), places=2
    ).filter(lambda d: d != 0),
)
@settings(max_examples=100, deadline=None)
def test_partner_allocation_sums_exactly_regardless_of_ratio_or_partner_count(
    ratios: dict[str, Decimal], net_income: Decimal
) -> None:
    chart = ChartOfAccounts()
    chart.add(Account(id="cash", name="Cash", type=AccountType.ASSET))
    chart.add(Account(id="revenue", name="Revenue", type=AccountType.REVENUE))
    chart.add(Account(id="expense", name="Expense", type=AccountType.EXPENSE))
    for partner_id in ratios:
        chart.add(Account(id=partner_id, name=partner_id, type=AccountType.EQUITY))

    ledger = Ledger(chart=chart)
    if net_income > ZERO:
        ledger.post(
            JournalEntry(
                id="e1",
                date=PERIOD_START,
                lines=(
                    make_line("cash", debit=str(net_income)),
                    make_line("revenue", credit=str(net_income)),
                ),
            )
        )
    else:
        loss = -net_income
        ledger.post(
            JournalEntry(
                id="e1",
                date=PERIOD_START,
                lines=(make_line("expense", debit=str(loss)), make_line("cash", credit=str(loss))),
            )
        )

    entry = closing.close_period(
        ledger, chart, PERIOD_START, PERIOD_END, None, "closing-1", partner_allocations=ratios
    )
    assert entry is not None

    total_credited = sum((line.credit for line in entry.lines if line.account_id in ratios), ZERO)
    total_debited = sum((line.debit for line in entry.lines if line.account_id in ratios), ZERO)
    assert (total_credited - total_debited) == net_income
