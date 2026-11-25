from decimal import Decimal

import pytest

from reference.accounting.rounding import money, round_currency


def test_money_parses_decimal_string():
    assert money("1234.56") == Decimal("1234.56")


def test_money_rejects_float():
    with pytest.raises(TypeError, match="Refusing to build Decimal from float"):
        money(1234.56)  # type: ignore[arg-type]


def test_round_currency_half_up():
    assert round_currency(Decimal("1.005"), precision=2, method="HALF_UP") == Decimal("1.01")
    assert round_currency(Decimal("1.004"), precision=2, method="HALF_UP") == Decimal("1.00")


def test_round_currency_unknown_method_rejected():
    with pytest.raises(ValueError, match="Unknown rounding method"):
        round_currency(Decimal("1.00"), method="NEAREST_DOLLAR")
