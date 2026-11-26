from decimal import Decimal

import pytest

from reference.accounting.journal import AccountingError
from reference.tax import liabilities


def test_even_two_way_split():
    shares = liabilities.partner_share_of_liability(
        Decimal("60000.00"), {"partner_a": Decimal("0.50"), "partner_b": Decimal("0.50")}
    )
    assert shares == {"partner_a": Decimal("30000.00"), "partner_b": Decimal("30000.00")}


def test_uneven_split_with_remainder_on_the_last_partner():
    shares = liabilities.partner_share_of_liability(
        Decimal("1000.00"),
        {
            "partner_a": Decimal("0.3333333333"),
            "partner_b": Decimal("0.3333333333"),
            "partner_c": Decimal("0.3333333334"),
        },
    )
    assert shares["partner_a"] == Decimal("333.33")
    assert shares["partner_b"] == Decimal("333.33")
    assert shares["partner_c"] == Decimal("333.34")
    assert sum(shares.values(), Decimal("0.00")) == Decimal("1000.00")


def test_ratios_must_sum_to_one():
    with pytest.raises(AccountingError, match="must sum to 1.00"):
        liabilities.partner_share_of_liability(
            Decimal("1000.00"), {"partner_a": Decimal("0.50"), "partner_b": Decimal("0.40")}
        )


def test_zero_liability_splits_to_zero():
    shares = liabilities.partner_share_of_liability(
        Decimal("0.00"), {"partner_a": Decimal("0.50"), "partner_b": Decimal("0.50")}
    )
    assert shares == {"partner_a": Decimal("0.00"), "partner_b": Decimal("0.00")}
