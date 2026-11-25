"""Decimal rounding helpers for monetary calculations.

All monetary values in this reference model are `decimal.Decimal`, constructed
from strings (never from `float`). See docs/accounting-policy.md.
"""

from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

_METHODS = {
    "HALF_UP": ROUND_HALF_UP,
    "HALF_EVEN": ROUND_HALF_EVEN,
    "DOWN": ROUND_DOWN,
}

ZERO = Decimal("0.00")


def money(value: str | Decimal) -> Decimal:
    """Parse a monetary string into a Decimal. Rejects float input."""
    if isinstance(value, float):
        raise TypeError(
            f"Refusing to build Decimal from float {value!r}; pass a string instead "
            "(Decimal(1234.56) silently imports binary floating-point imprecision)."
        )
    return Decimal(value)


def round_currency(value: Decimal, precision: int = 2, method: str = "HALF_UP") -> Decimal:
    """Round `value` to `precision` decimal places using the named policy method."""
    if method not in _METHODS:
        raise ValueError(f"Unknown rounding method: {method!r}")
    quantum = Decimal(1).scaleb(-precision)
    return value.quantize(quantum, rounding=_METHODS[method])
