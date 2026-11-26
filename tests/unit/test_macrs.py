from decimal import Decimal

import pytest

from reference.accounting.journal import AccountingError
from reference.tax import macrs


def test_rates_sum_to_exactly_one_hundred_percent():
    assert sum(macrs.FIVE_YEAR_HALF_YEAR_CONVENTION, Decimal(0)) == Decimal("1.0000")


def test_five_year_schedule_for_sixty_thousand_dollar_asset():
    # Hand computation (IRS Pub. 946 Table A-1, 5-year property, half-year
    # convention): 60000 * [20.00%, 32.00%, 19.20%, 11.52%, 11.52%, 5.76%]
    # = [12000.00, 19200.00, 11520.00, 6912.00, 6912.00, 3456.00], which
    # sums to exactly 60000.00 since every rate times 60000 lands on a
    # whole cent with no rounding.
    schedule = macrs.five_year_schedule(Decimal("60000.00"))
    assert schedule == [
        Decimal("12000.00"),
        Decimal("19200.00"),
        Decimal("11520.00"),
        Decimal("6912.00"),
        Decimal("6912.00"),
        Decimal("3456.00"),
    ]
    assert sum(schedule, Decimal("0.00")) == Decimal("60000.00")


def test_schedule_length_is_six_tax_years():
    assert len(macrs.five_year_schedule(Decimal("1000.00"))) == 6


def test_cost_must_be_positive():
    with pytest.raises(AccountingError, match="must be positive"):
        macrs.five_year_schedule(Decimal("0.00"))
