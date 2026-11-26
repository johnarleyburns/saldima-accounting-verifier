from decimal import Decimal

import pytest

from reference.accounting.journal import AccountingError
from reference.schedules.inventory import Lot, consume_fifo


def test_consume_from_a_single_lot():
    lots = [Lot(quantity=Decimal(100), unit_cost=Decimal("10.00"))]
    cogs, remaining = consume_fifo(lots, Decimal(40))
    assert cogs == Decimal("400.00")
    assert remaining == [Lot(quantity=Decimal(60), unit_cost=Decimal("10.00"))]


def test_consume_exactly_empties_a_lot():
    lots = [Lot(quantity=Decimal(100), unit_cost=Decimal("10.00"))]
    cogs, remaining = consume_fifo(lots, Decimal(100))
    assert cogs == Decimal("1000.00")
    assert remaining == []


def test_consume_spans_multiple_lots_oldest_first():
    lots = [
        Lot(quantity=Decimal(100), unit_cost=Decimal("10.00")),
        Lot(quantity=Decimal(100), unit_cost=Decimal("12.00")),
    ]
    cogs, remaining = consume_fifo(lots, Decimal(150))
    # 100 units @ 10.00 + 50 units @ 12.00 = 1000.00 + 600.00 = 1600.00.
    assert cogs == Decimal("1600.00")
    assert remaining == [Lot(quantity=Decimal(50), unit_cost=Decimal("12.00"))]


def test_consume_leaves_later_lots_untouched_when_earlier_lots_suffice():
    lots = [
        Lot(quantity=Decimal(100), unit_cost=Decimal("10.00")),
        Lot(quantity=Decimal(100), unit_cost=Decimal("12.00")),
    ]
    cogs, remaining = consume_fifo(lots, Decimal(40))
    assert cogs == Decimal("400.00")
    assert remaining == [
        Lot(quantity=Decimal(60), unit_cost=Decimal("10.00")),
        Lot(quantity=Decimal(100), unit_cost=Decimal("12.00")),
    ]


def test_selling_more_than_on_hand_is_rejected():
    lots = [Lot(quantity=Decimal(100), unit_cost=Decimal("10.00"))]
    with pytest.raises(AccountingError, match="only 100.00 units on hand"):
        consume_fifo(lots, Decimal(150))


def test_consume_with_no_lots_and_zero_quantity_is_a_no_op():
    cogs, remaining = consume_fifo([], Decimal(0))
    assert cogs == Decimal("0.00")
    assert remaining == []
