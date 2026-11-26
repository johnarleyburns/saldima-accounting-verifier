"""MACRS tax depreciation (5-year property, half-year convention, 200% declining
balance switching to straight-line).

Pure Decimal, no dependency on Saldima production code -- see
docs/plan.md section 2.1. Percentages are the published IRS Publication 946
(Table A-1) rates for 5-year property under the half-year convention:
20.00%, 32.00%, 19.20%, 11.52%, 11.52%, 5.76% across six tax years (the
half-year convention treats the asset as placed in service mid-year,
which is why a 5-year asset spans six tax years of depreciation).

Phase 3 scope (see docs/accounting-policy.md): this module validates the
MACRS schedule *computation* against hand-verified numbers. It does not
post journal entries or model the book-vs-tax deferred-tax difference that
a real set of financial statements would require -- that's out of scope
for "fixed assets and inventory" and is deferred to a future tax-accounting
phase. FA-003 uses this module directly (via a dedicated test), not through
`runner/scenario_runner.py`.
"""

from __future__ import annotations

from decimal import Decimal

from reference.accounting.journal import AccountingError
from reference.accounting.rounding import round_currency

# IRS Publication 946, Table A-1: 5-year property, half-year convention.
FIVE_YEAR_HALF_YEAR_CONVENTION: tuple[Decimal, ...] = (
    Decimal("0.2000"),
    Decimal("0.3200"),
    Decimal("0.1920"),
    Decimal("0.1152"),
    Decimal("0.1152"),
    Decimal("0.0576"),
)


def five_year_schedule(cost: Decimal, precision: int = 2, method: str = "HALF_UP") -> list[Decimal]:
    """MACRS depreciation per tax year for 5-year property, half-year convention.

    MACRS ignores salvage value (depreciates the full `cost`) and does not
    use calendar dates -- each entry is one tax year's depreciation amount,
    in order. The published percentages sum to exactly 100.00%, so the six
    amounts sum to exactly `cost` after rounding only if `cost` itself
    rounds evenly; this function does not adjust for rounding drift, since
    the IRS percentages (not a reference-model-computed total) are the
    authority here -- compare against `sum(five_year_schedule(cost))` in
    tests, not assume it equals `cost` to the penny for arbitrary input.
    """
    if cost <= Decimal(0):
        raise AccountingError(f"MACRS cost must be positive (got {cost})")
    return [round_currency(cost * rate, precision, method) for rate in FIVE_YEAR_HALF_YEAR_CONVENTION]
