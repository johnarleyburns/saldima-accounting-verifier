"""PART-003: section 704(c) built-in gain allocation -- traditional method.

Per docs/accounting-policy.md's Phase 5 scope boundary, this scenario's
ledger only ever posts the *book* depreciation (at the contributed
equipment's fair market value, split 50/50 for GAAP purposes -- compared
against its own expected/reviewed/ fixtures by
tests/integration/test_core_scenarios.py, like every other scenario).
This is the dedicated comparison against the *tax* side: the traditional-
method section 704(c) allocation, computed independently by
reference/tax/section_704c.py from the scenario's own book/tax basis
facts, and never posted to any ledger -- mirroring
test_fa_003_tax_vs_book_depreciation.py's shape.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

from reference.tax import section_704c
from runner import reference_runner
from runner.scenario_runner import load_scenario

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PART_003 = REPO_ROOT / "scenarios" / "partnerships" / "part-003-property-contribution-704c.yaml"

FMV = Decimal("60000.00")
TAX_BASIS = Decimal("30000.00")
USEFUL_LIFE_MONTHS = 60


def _book_depreciation_per_month() -> Decimal:
    return FMV / USEFUL_LIFE_MONTHS  # 1000.00/month, matching FA-001's identical cost/life


def _tax_depreciation_per_month() -> Decimal:
    return TAX_BASIS / USEFUL_LIFE_MONTHS  # 500.00/month


def test_book_depreciation_matches_the_reviewed_ledger():
    loaded = load_scenario(PART_003)
    reference_runner.run(loaded)
    balances = loaded.ledger.balances_as_of(date(2030, 12, 31))
    total_book_depreciation = -balances["accumulated_depreciation_equipment"]["ending_balance"]
    assert total_book_depreciation == FMV  # fully depreciated over the 60-month life


def test_ceiling_rule_leaves_the_contributing_partner_with_zero_tax_depreciation():
    """Partner C's (non-contributing) book share of depreciation is
    500.00/month (half of the 1000.00/month book depreciation); total tax
    depreciation available is also exactly 500.00/month (30000.00 tax basis
    / 60 months) -- the ceiling rule binds exactly, leaving Partner D (the
    contributing partner) with 0.00/month tax depreciation for the asset's
    entire life. See reference/tax/section_704c.py and this scenario's
    approval.json for the full hand computation."""
    book_depreciation_per_month = _book_depreciation_per_month()
    tax_depreciation_per_month = _tax_depreciation_per_month()
    non_contributing_partner_book_share = book_depreciation_per_month / 2  # 50/50 book split

    non_contributing_tax, contributing_tax = section_704c.traditional_method_allocation(
        tax_depreciation_per_month, non_contributing_partner_book_share
    )

    assert non_contributing_tax == Decimal("500.00")
    assert contributing_tax == Decimal("0.00")
    # Every month of the asset's 60-month life hits the same ceiling, since
    # both book and tax depreciation are flat throughout.
    for _ in range(USEFUL_LIFE_MONTHS):
        monthly_non_contributing, monthly_contributing = section_704c.traditional_method_allocation(
            tax_depreciation_per_month, non_contributing_partner_book_share
        )
        assert monthly_non_contributing == Decimal("500.00")
        assert monthly_contributing == Decimal("0.00")


def test_total_tax_depreciation_over_the_assets_life_equals_tax_basis():
    tax_depreciation_per_month = _tax_depreciation_per_month()
    total_tax_depreciation = tax_depreciation_per_month * USEFUL_LIFE_MONTHS
    assert total_tax_depreciation == TAX_BASIS

    # Partner D (the contributing partner) never recovers any of that
    # 30000.00 of tax depreciation through this asset's life -- the built-in
    # gain (FMV - tax basis = 30000.00) is preserved for recognition on an
    # eventual sale instead, the well-known "ceiling rule problem."
    built_in_gain = FMV - TAX_BASIS
    assert built_in_gain == Decimal("30000.00")
