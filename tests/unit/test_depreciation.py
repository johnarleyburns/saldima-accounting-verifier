from datetime import date
from decimal import Decimal

import pytest

from reference.accounting.journal import AccountingError
from reference.schedules import depreciation


def test_straight_line_schedule_splits_evenly_with_no_remainder():
    schedule = depreciation.build_straight_line_schedule(
        Decimal("60000.00"), Decimal("0.00"), date(2026, 1, 1), 60
    )
    assert len(schedule) == 60
    assert all(amount == Decimal("1000.00") for _, amount in schedule)
    assert sum((amount for _, amount in schedule), Decimal("0.00")) == Decimal("60000.00")
    assert schedule[0][0] == date(2026, 1, 31)
    assert schedule[-1][0] == date(2030, 12, 31)


def test_straight_line_schedule_respects_salvage_value():
    schedule = depreciation.build_straight_line_schedule(
        Decimal("10000.00"), Decimal("1000.00"), date(2026, 1, 1), 9
    )
    # Depreciable base is 9000.00, not 10000.00.
    assert sum((amount for _, amount in schedule), Decimal("0.00")) == Decimal("9000.00")
    assert schedule[0][1] == Decimal("1000.00")


def test_straight_line_schedule_absorbs_rounding_remainder_into_last_month():
    schedule = depreciation.build_straight_line_schedule(
        Decimal("1000.00"), Decimal("0.00"), date(2026, 1, 1), 3
    )
    amounts = [amount for _, amount in schedule]
    assert amounts[:-1] == [Decimal("333.33"), Decimal("333.33")]
    assert amounts[-1] == Decimal("333.34")


def test_schedule_truncated_by_disposal_before_the_final_month():
    full = depreciation.build_straight_line_schedule(
        Decimal("24000.00"), Decimal("0.00"), date(2026, 1, 1), 24
    )
    truncated = depreciation.build_straight_line_schedule(
        Decimal("24000.00"), Decimal("0.00"), date(2026, 1, 1), 24, through=date(2026, 12, 31)
    )
    assert len(truncated) == 12
    assert truncated == full[:12]
    # Truncation never hits the remainder month, so every truncated amount
    # is the plain even per-month figure.
    assert all(amount == Decimal("1000.00") for _, amount in truncated)


def test_disposal_on_the_in_service_month_keeps_one_period():
    schedule = depreciation.build_straight_line_schedule(
        Decimal("1200.00"), Decimal("0.00"), date(2026, 1, 1), 12, through=date(2026, 1, 31)
    )
    assert schedule == [(date(2026, 1, 31), Decimal("100.00"))]


def test_disposal_before_the_first_depreciation_month_is_rejected():
    with pytest.raises(AccountingError, match="before the first depreciation month"):
        depreciation.build_straight_line_schedule(
            Decimal("1200.00"), Decimal("0.00"), date(2026, 2, 1), 12, through=date(2026, 1, 15)
        )


def test_in_service_date_must_be_first_day_of_month():
    with pytest.raises(AccountingError, match="first day of its month"):
        depreciation.build_straight_line_schedule(Decimal("1200.00"), Decimal("0.00"), date(2026, 1, 5), 12)


def test_salvage_value_cannot_exceed_cost():
    with pytest.raises(AccountingError, match="cannot exceed cost"):
        depreciation.build_straight_line_schedule(Decimal("100.00"), Decimal("200.00"), date(2026, 1, 1), 12)


def test_disposal_gain_when_proceeds_exceed_book_value():
    # cost 60000, accumulated depreciation 30000 -> book value 30000.
    gain_loss = depreciation.disposal_gain_loss(Decimal("60000.00"), Decimal("30000.00"), Decimal("35000.00"))
    assert gain_loss == Decimal("5000.00")


def test_disposal_loss_when_proceeds_are_below_book_value():
    # cost 24000, accumulated depreciation 12000 -> book value 12000.
    gain_loss = depreciation.disposal_gain_loss(Decimal("24000.00"), Decimal("12000.00"), Decimal("8000.00"))
    assert gain_loss == Decimal("-4000.00")


def test_disposal_at_exactly_book_value_is_neither_gain_nor_loss():
    gain_loss = depreciation.disposal_gain_loss(Decimal("24000.00"), Decimal("12000.00"), Decimal("12000.00"))
    assert gain_loss == Decimal("0.00")
