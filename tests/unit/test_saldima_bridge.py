from decimal import Decimal

import pytest

from adapters.saldima.bridge import from_wire_money, to_wire_money


@pytest.mark.parametrize(
    "value",
    [
        Decimal("0.00"),
        Decimal("1234.56"),
        Decimal("-500.25"),
        Decimal("1000000.00"),
        Decimal("0.01"),
        Decimal("-0.01"),
    ],
)
def test_to_wire_money_round_trips_through_from_wire_money(value: Decimal) -> None:
    assert from_wire_money(to_wire_money(value)) == value


def test_to_wire_money_uses_a_fixed_denominator_of_100() -> None:
    assert to_wire_money(Decimal("12.34")) == {"num": "1234", "denom": "100"}


def test_from_wire_money_handles_a_reduced_fraction() -> None:
    # packages/gnucash's own arithmetic reduces fractions to lowest terms
    # (confirmed by hand-testing the real bridge: "1300/1", not "130000/100").
    assert from_wire_money({"num": "13", "denom": "1"}) == Decimal("13.00")
    assert from_wire_money({"num": "-500", "denom": "4"}) == Decimal("-125.00")
