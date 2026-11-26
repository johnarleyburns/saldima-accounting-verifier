from decimal import Decimal

import pytest

from reference.accounting.journal import AccountingError
from reference.tax import partnership_basis


def test_basis_combines_contribution_liability_share_and_income():
    basis = partnership_basis.outside_basis(
        contribution=Decimal("30000.00"),
        share_of_liabilities=Decimal("30000.00"),
        cumulative_allocated_income=Decimal("12000.00"),
        cumulative_allocated_losses=Decimal("0.00"),
        distributions_received=Decimal("0.00"),
    )
    assert basis == Decimal("72000.00")


def test_losses_and_distributions_reduce_basis():
    basis = partnership_basis.outside_basis(
        contribution=Decimal("30000.00"),
        share_of_liabilities=Decimal("30000.00"),
        cumulative_allocated_income=Decimal("12000.00"),
        cumulative_allocated_losses=Decimal("5000.00"),
        distributions_received=Decimal("5000.00"),
    )
    assert basis == Decimal("62000.00")


def test_a_declining_liability_reduces_basis_over_time():
    # Same facts except the partner's share of the (now partly repaid)
    # liability has fallen from 30000.00 to 20000.00.
    basis = partnership_basis.outside_basis(
        contribution=Decimal("30000.00"),
        share_of_liabilities=Decimal("20000.00"),
        cumulative_allocated_income=Decimal("12000.00"),
        cumulative_allocated_losses=Decimal("0.00"),
        distributions_received=Decimal("0.00"),
    )
    assert basis == Decimal("62000.00")


def test_negative_basis_is_rejected():
    with pytest.raises(AccountingError, match="cannot be negative"):
        partnership_basis.outside_basis(
            contribution=Decimal("1000.00"),
            share_of_liabilities=Decimal("0.00"),
            cumulative_allocated_income=Decimal("0.00"),
            cumulative_allocated_losses=Decimal("5000.00"),
            distributions_received=Decimal("0.00"),
        )
