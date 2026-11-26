from datetime import date
from decimal import Decimal

import pytest

from reference.accounting.journal import AccountingError
from reference.schedules import deferred_revenue


def test_straight_line_schedule_splits_evenly_with_no_remainder():
    schedule = deferred_revenue.build_straight_line_schedule(
        Decimal("12000.00"), date(2026, 1, 1), date(2026, 12, 31)
    )
    assert len(schedule) == 12
    assert all(amount == Decimal("1000.00") for _, amount in schedule)
    assert sum((amount for _, amount in schedule), Decimal("0.00")) == Decimal("12000.00")
    assert schedule[0][0] == date(2026, 1, 31)
    assert schedule[-1][0] == date(2026, 12, 31)


def test_straight_line_schedule_absorbs_rounding_remainder_into_last_month():
    # 1000.00 / 3 = 333.333... -> 333.33/333.33/333.34, summing to 1000.00 exactly.
    schedule = deferred_revenue.build_straight_line_schedule(
        Decimal("1000.00"), date(2026, 1, 1), date(2026, 3, 31)
    )
    amounts = [amount for _, amount in schedule]
    assert amounts[:-1] == [Decimal("333.33"), Decimal("333.33")]
    assert amounts[-1] == Decimal("333.34")
    assert sum(amounts, Decimal("0.00")) == Decimal("1000.00")


def test_straight_line_schedule_spans_a_year_boundary():
    schedule = deferred_revenue.build_straight_line_schedule(
        Decimal("18000.00"), date(2026, 1, 1), date(2027, 12, 31)
    )
    assert len(schedule) == 24
    assert all(amount == Decimal("750.00") for _, amount in schedule)
    assert schedule[0][0] == date(2026, 1, 31)
    assert schedule[-1][0] == date(2027, 12, 31)


def test_single_month_schedule():
    schedule = deferred_revenue.build_straight_line_schedule(
        Decimal("500.00"), date(2026, 3, 1), date(2026, 3, 31)
    )
    assert schedule == [(date(2026, 3, 31), Decimal("500.00"))]


def test_start_must_be_first_day_of_month():
    with pytest.raises(AccountingError, match="first day of its month"):
        deferred_revenue.build_straight_line_schedule(
            Decimal("100.00"), date(2026, 1, 5), date(2026, 1, 31)
        )


def test_end_must_be_last_day_of_month():
    with pytest.raises(AccountingError, match="last day of its month"):
        deferred_revenue.build_straight_line_schedule(
            Decimal("100.00"), date(2026, 1, 1), date(2026, 1, 15)
        )


def test_end_before_start_is_rejected():
    with pytest.raises(AccountingError, match="is before start"):
        deferred_revenue.build_straight_line_schedule(
            Decimal("100.00"), date(2026, 3, 1), date(2026, 1, 31)
        )
