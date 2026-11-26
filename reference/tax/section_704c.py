"""Section 704(c) built-in gain allocation -- traditional method only.

Pure Decimal, no dependency on Saldima production code -- see
docs/plan.md section 2.1; authority is IRS Publication 541 and Treasury
Regulation 1.704-3(b) (the traditional method).

Phase 5 scope (see docs/accounting-policy.md): when a partner contributes
property whose fair market value (the GAAP book basis) exceeds its tax
basis, section 704(c) requires the resulting "built-in gain" to be
allocated back to the contributing partner as the property depreciates
or is sold, instead of being shared under the partnership's ordinary
profit ratio. This module implements **only the traditional method**
(Treasury Reg. 1.704-3(b)) for the two-partner, one-contributed-asset
case `PART-003` needs -- not the curative or remedial methods, which
Treasury Reg. 1.704-3(c)/(d) separately allow and which this reference
model does not implement. This is a documented scope boundary, the same
honesty `reference/tax/macrs.py` applies to MACRS vs. book depreciation.

Like every other tax-basis module in this phase, this computes an
allocation for comparison in a dedicated test
(tests/integration/test_part_003_section_704c.py); nothing here is ever
posted as a journal entry -- the GAAP books depreciate the contributed
asset at its book value (fair market value) and split that depreciation
under the partnership's ordinary profit ratio, same as any other asset.
"""

from __future__ import annotations

from decimal import Decimal

ZERO = Decimal("0.00")


def traditional_method_allocation(
    tax_depreciation_per_period: Decimal,
    non_contributing_partners_book_share: Decimal,
) -> tuple[Decimal, Decimal]:
    """One period's traditional-method tax depreciation split between the
    non-contributing partner(s) and the contributing partner, for a single
    contributed asset.

    Returns `(non_contributing_tax_depreciation, contributing_tax_depreciation)`.

    The non-contributing partners receive tax depreciation equal to their
    *book* depreciation share, capped by the "ceiling rule": traditional-
    method tax depreciation allocated to non-contributing partners can
    never exceed the partnership's total tax depreciation for the period,
    even when book depreciation (on the higher, stepped-up book basis) is
    larger than tax depreciation (on the lower, carried-over tax basis).
    The contributing partner receives whatever tax depreciation remains,
    which can be zero. When the built-in gain is large enough that it
    always is zero for the asset's whole life, the contributing partner's
    tax depreciation deductions are permanently reduced -- this is the
    well-known "ceiling rule problem," an acknowledged limitation of the
    traditional method (not a bug in this calculation).
    """
    non_contributing_tax_depreciation = min(non_contributing_partners_book_share, tax_depreciation_per_period)
    contributing_tax_depreciation = tax_depreciation_per_period - non_contributing_tax_depreciation
    return non_contributing_tax_depreciation, contributing_tax_depreciation
