"""FIFO inventory costing.

Pure Decimal, no dependency on Saldima production code -- see
reference/schedules/README.md and docs/plan.md section 2.1. Phase 3 scope:
a scenario author describes `inventory_purchase`/`inventory_sale` events
declaratively (see docs/scenario-authoring.md); the reference model
maintains a running list of open FIFO lots per inventory account
(runner/scenario_runner.py, since this is the one Phase 3 event type whose
translation needs state carried across events, not just the event's own
fields) and calls `consume_fifo` here to derive each sale's cost of goods
sold -- the actual engine-under-test behavior being validated, since the
sale/purchase dollar totals themselves are plain multiplication.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from reference.accounting.journal import AccountingError
from reference.accounting.rounding import ZERO


@dataclass(frozen=True)
class Lot:
    quantity: Decimal
    unit_cost: Decimal


def consume_fifo(lots: list[Lot], quantity: Decimal) -> tuple[Decimal, list[Lot]]:
    """Consume `quantity` units from `lots` oldest-first (FIFO).

    Returns `(cost_of_goods_sold, remaining_lots)`. `lots` must already be
    in purchase order (oldest first); it is not mutated. Raises
    `AccountingError` if `quantity` exceeds the total quantity on hand --
    selling inventory that was never purchased is a scenario-authoring bug,
    not a valid business event.
    """
    available = sum((lot.quantity for lot in lots), ZERO)
    if quantity > available:
        raise AccountingError(
            f"Cannot sell {quantity} units: only {available} units on hand across {len(lots)} lot(s)"
        )

    remaining_to_consume = quantity
    cost_of_goods_sold = ZERO
    remaining_lots: list[Lot] = []
    for lot in lots:
        if remaining_to_consume <= ZERO:
            remaining_lots.append(lot)
            continue
        consumed_from_lot = min(lot.quantity, remaining_to_consume)
        cost_of_goods_sold += consumed_from_lot * lot.unit_cost
        remaining_to_consume -= consumed_from_lot
        leftover_quantity = lot.quantity - consumed_from_lot
        if leftover_quantity > ZERO:
            remaining_lots.append(Lot(quantity=leftover_quantity, unit_cost=lot.unit_cost))

    return cost_of_goods_sold, remaining_lots
