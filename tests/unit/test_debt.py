from datetime import date
from decimal import Decimal

import pytest

from reference.accounting.journal import AccountingError
from reference.schedules import debt


def test_equal_principal_schedule_with_no_remainder():
    schedule = debt.build_amortization_schedule(
        Decimal("60000.00"), Decimal("0.06"), 60, date(2026, 1, 1)
    )
    assert len(schedule) == 60

    # Principal is always exactly 1000.00/month; interest declines by
    # exactly 5.00/month since the balance always drops by a round 1000.00
    # and the monthly rate is 0.5%.
    for i, (period_end, interest, principal_payment, remaining_balance) in enumerate(schedule):
        assert principal_payment == Decimal("1000.00")
        assert interest == Decimal("300.00") - Decimal("5.00") * i
        assert remaining_balance == Decimal("60000.00") - Decimal("1000.00") * (i + 1)

    assert schedule[0][0] == date(2026, 1, 31)
    assert schedule[-1][0] == date(2030, 12, 31)
    assert schedule[-1][3] == Decimal("0.00")

    total_principal = sum((p for _, _, p, _ in schedule), Decimal("0.00"))
    total_interest = sum((i for _, i, _, _ in schedule), Decimal("0.00"))
    assert total_principal == Decimal("60000.00")
    assert total_interest == Decimal("9150.00")  # sum_{m=1..60}(305 - 5m)


def test_schedule_absorbs_rounding_remainder_into_last_month():
    schedule = debt.build_amortization_schedule(
        Decimal("1000.00"), Decimal("0.12"), 3, date(2026, 1, 1)
    )
    principal_payments = [p for _, _, p, _ in schedule]
    assert principal_payments[:-1] == [Decimal("333.33"), Decimal("333.33")]
    assert principal_payments[-1] == Decimal("333.34")
    assert sum(principal_payments, Decimal("0.00")) == Decimal("1000.00")
    assert schedule[-1][3] == Decimal("0.00")


def test_first_month_interest_and_remaining_balance():
    schedule = debt.build_amortization_schedule(
        Decimal("1000.00"), Decimal("0.12"), 3, date(2026, 1, 1)
    )
    period_end, interest, principal_payment, remaining_balance = schedule[0]
    assert period_end == date(2026, 1, 31)
    assert interest == Decimal("10.00")  # 1000.00 * (0.12 / 12)
    assert principal_payment == Decimal("333.33")
    assert remaining_balance == Decimal("666.67")


def test_start_date_must_be_first_day_of_month():
    with pytest.raises(AccountingError, match="first day of its month"):
        debt.build_amortization_schedule(Decimal("1000.00"), Decimal("0.06"), 12, date(2026, 1, 5))


def test_term_months_must_be_positive():
    with pytest.raises(AccountingError, match="term_months must be at least 1"):
        debt.build_amortization_schedule(Decimal("1000.00"), Decimal("0.06"), 0, date(2026, 1, 1))


def test_principal_must_be_positive():
    with pytest.raises(AccountingError, match="principal must be positive"):
        debt.build_amortization_schedule(Decimal("0.00"), Decimal("0.06"), 12, date(2026, 1, 1))
