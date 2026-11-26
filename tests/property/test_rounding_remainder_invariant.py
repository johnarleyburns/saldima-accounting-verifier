"""Hypothesis-generalized coverage of the shared "rounding remainder goes
to the last period/target" convention documented in
docs/reference-model.md, across all four modules that use it. Each
existing unit test (test_deferred_revenue.py, test_depreciation.py,
test_debt.py, test_liabilities.py) hand-picks one uneven-split example.
Here the total/period-count/ratios are randomly generated, proving the
per-period or per-target amounts always sum to *exactly* the input total
with zero drift, not just for those hand-picked cases.
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from reference.schedules import debt, deferred_revenue, depreciation
from reference.tax import liabilities


def _nth_month_end(start: date, months_ahead: int) -> date:
    """The last day of the month `months_ahead` months after `start`'s
    month (0 = start's own month) -- the same arithmetic
    reference/schedules/{debt,depreciation}.py use internally to walk
    from a first-of-month start date.
    """
    total_months = (start.month - 1) + months_ahead
    year = start.year + total_months // 12
    month = total_months % 12 + 1
    return date(year, month, calendar.monthrange(year, month)[1])


@given(
    total=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1000000.00"), places=2),
    n_months=st.integers(min_value=1, max_value=360),
)
@settings(max_examples=100, deadline=None)
def test_deferred_revenue_schedule_sums_exactly_to_total(total: Decimal, n_months: int) -> None:
    start = date(2026, 1, 1)
    end = _nth_month_end(start, n_months - 1)
    schedule = deferred_revenue.build_straight_line_schedule(total, start, end)
    assert len(schedule) == n_months
    assert sum((amount for _, amount in schedule), Decimal("0.00")) == total


@given(
    cost=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1000000.00"), places=2),
    salvage_fraction=st.decimals(min_value=Decimal("0.00"), max_value=Decimal("0.90"), places=2),
    useful_life_months=st.integers(min_value=1, max_value=360),
)
@settings(max_examples=100, deadline=None)
def test_depreciation_schedule_sums_exactly_to_the_depreciable_base(
    cost: Decimal, salvage_fraction: Decimal, useful_life_months: int
) -> None:
    salvage_value = (cost * salvage_fraction).quantize(Decimal("0.01"))
    schedule = depreciation.build_straight_line_schedule(
        cost, salvage_value, date(2026, 1, 1), useful_life_months
    )
    assert len(schedule) == useful_life_months
    assert sum((amount for _, amount in schedule), Decimal("0.00")) == cost - salvage_value


@given(
    principal=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10000000.00"), places=2),
    annual_interest_rate=st.decimals(
        min_value=Decimal("0.00"), max_value=Decimal("0.30"), places=4
    ),
    term_months=st.integers(min_value=1, max_value=360),
)
@settings(max_examples=100, deadline=None)
def test_amortization_schedule_principal_payments_sum_exactly_to_the_principal(
    principal: Decimal, annual_interest_rate: Decimal, term_months: int
) -> None:
    schedule = debt.build_amortization_schedule(
        principal, annual_interest_rate, term_months, date(2026, 1, 1)
    )
    assert len(schedule) == term_months
    total_principal_paid = sum(
        (principal_payment for _, _, principal_payment, _ in schedule), Decimal("0.00")
    )
    assert total_principal_paid == principal


@st.composite
def sharing_ratios(
    draw: st.DrawFn, min_partners: int = 2, max_partners: int = 6
) -> dict[str, Decimal]:
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
    total_liability=st.decimals(
        min_value=Decimal("0.01"), max_value=Decimal("10000000.00"), places=2
    ),
    ratios=sharing_ratios(),
)
@settings(max_examples=100, deadline=None)
def test_partner_liability_shares_sum_exactly_to_the_total(
    total_liability: Decimal, ratios: dict[str, Decimal]
) -> None:
    shares = liabilities.partner_share_of_liability(total_liability, ratios)
    assert sum(shares.values(), Decimal("0.00")) == total_liability
