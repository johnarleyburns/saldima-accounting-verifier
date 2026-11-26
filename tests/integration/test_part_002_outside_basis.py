"""PART-002: partner outside tax basis (IRC sections 705(a)/752).

Per docs/accounting-policy.md's Phase 5 scope boundary, this scenario's
ledger only ever posts the *book* capital accounts (compared against its
own expected/reviewed/ fixtures by tests/integration/test_core_scenarios.py,
like every other scenario). This is the dedicated comparison against each
partner's *outside basis*, computed independently by
reference/tax/{liabilities,partnership_basis}.py from the scenario's own
contribution/liability/income facts, and never posted to any ledger --
mirroring test_fa_003_tax_vs_book_depreciation.py's shape.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

from reference.schedules import debt as debt_mod
from reference.tax import liabilities, partnership_basis
from runner import reference_runner
from runner.scenario_runner import load_scenario

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PART_002 = REPO_ROOT / "scenarios" / "partnerships" / "part-002-partnership-debt-and-outside-basis.yaml"

CONTRIBUTION = Decimal("10000.00")
SHARING_RATIOS = {"partner_a": Decimal("0.50"), "partner_b": Decimal("0.50")}


def test_outside_basis_at_the_end_of_each_year_matches_book_capital_plus_liability_share():
    """Outside basis = contribution + share of the (declining) partnership
    liability + cumulative allocated income - distributions. With zero
    distributions in this scenario, outside basis must always equal book
    capital (from the reviewed ledger) plus the partner's current share of
    the remaining loan balance -- an independent identity, not something
    either module assumes about the other."""
    loaded = load_scenario(PART_002)
    reference_runner.run(loaded)  # applies the closing entries that set book capital

    schedule = debt_mod.build_amortization_schedule(Decimal("60000.00"), Decimal("0.06"), 60, date(2026, 1, 1))
    remaining_balance_by_month_end = {period_end: balance for period_end, _, _, balance in schedule}

    for year_end, cumulative_income_per_partner in [
        (date(2026, 12, 31), Decimal("10365.00")),
        (date(2028, 12, 31), Decimal("32175.00")),
        (date(2030, 12, 31), Decimal("55425.00")),
    ]:
        remaining_liability = remaining_balance_by_month_end[year_end]
        share = liabilities.partner_share_of_liability(remaining_liability, SHARING_RATIOS)["partner_a"]

        outside_basis = partnership_basis.outside_basis(
            contribution=CONTRIBUTION,
            share_of_liabilities=share,
            cumulative_allocated_income=cumulative_income_per_partner,
            cumulative_allocated_losses=Decimal("0.00"),
            distributions_received=Decimal("0.00"),
        )

        book_capital = loaded.ledger.balances_as_of(year_end)["partner_a_capital"]["ending_balance"]
        assert outside_basis == book_capital + share, (
            f"at {year_end}: outside basis {outside_basis} != book capital {book_capital} "
            f"+ liability share {share}"
        )


def test_outside_basis_hand_computed_values():
    schedule = debt_mod.build_amortization_schedule(Decimal("60000.00"), Decimal("0.06"), 60, date(2026, 1, 1))
    remaining_balance_by_month_end = {period_end: balance for period_end, _, _, balance in schedule}

    # End of 2026: remaining liability 48000.00, A's share 24000.00; cumulative
    # allocated income 10365.00 (half of 20730.00, matching DEBT-001/PART-002's
    # year-1 net income).
    share_2026 = liabilities.partner_share_of_liability(
        remaining_balance_by_month_end[date(2026, 12, 31)], SHARING_RATIOS
    )["partner_a"]
    assert share_2026 == Decimal("24000.00")
    basis_2026 = partnership_basis.outside_basis(
        CONTRIBUTION, share_2026, Decimal("10365.00"), Decimal("0.00"), Decimal("0.00")
    )
    assert basis_2026 == Decimal("44365.00")

    # End of 2030: loan fully repaid (remaining liability 0.00), cumulative
    # allocated income 55425.00 (half of 110850.00, the five-year total).
    share_2030 = liabilities.partner_share_of_liability(
        remaining_balance_by_month_end[date(2030, 12, 31)], SHARING_RATIOS
    )["partner_a"]
    assert share_2030 == Decimal("0.00")
    basis_2030 = partnership_basis.outside_basis(
        CONTRIBUTION, share_2030, Decimal("55425.00"), Decimal("0.00"), Decimal("0.00")
    )
    assert basis_2030 == Decimal("65425.00")
