"""End-to-end: load a scenario, run the reference model, compare every
requested period's statements against the approved expected/reviewed/
fixtures (never expected/generated/ -- see docs/release-gates.md)."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from reference.schedules import payables
from runner import compare, reference_runner
from runner import period as period_mod
from runner.scenario_runner import load_scenario

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCENARIOS = [
    REPO_ROOT / "scenarios" / "foundational" / "core-001-opening-balances.yaml",
    REPO_ROOT / "scenarios" / "foundational" / "core-002-basic-service-business.yaml",
    REPO_ROOT / "scenarios" / "accruals" / "accr-001-accrued-payroll-and-utilities.yaml",
    REPO_ROOT / "scenarios" / "accruals" / "accr-002-prepaid-insurance-and-rent.yaml",
    REPO_ROOT / "scenarios" / "revenue-recognition" / "rev-001-advance-service-contract.yaml",
    REPO_ROOT / "scenarios" / "revenue-recognition" / "rev-002-multiple-performance-obligations.yaml",
    REPO_ROOT / "scenarios" / "fixed-assets" / "fa-001-straight-line-equipment-depreciation.yaml",
    REPO_ROOT / "scenarios" / "fixed-assets" / "fa-002-asset-disposal.yaml",
    REPO_ROOT / "scenarios" / "fixed-assets" / "fa-003-tax-vs-book-depreciation.yaml",
    REPO_ROOT / "scenarios" / "inventory" / "inv-001-fifo-retail.yaml",
    REPO_ROOT / "scenarios" / "inventory" / "inv-002-inventory-write-down.yaml",
]


@pytest.mark.parametrize("scenario_path", SCENARIOS, ids=lambda p: p.stem)
def test_scenario_matches_reviewed_fixtures(scenario_path: Path):
    loaded = load_scenario(scenario_path)
    actual_reports = reference_runner.run(loaded)

    reviewed_dir = REPO_ROOT / "expected" / "reviewed" / loaded.id
    assert reviewed_dir.exists(), f"No reviewed fixtures for {loaded.id!r}"

    failures = []
    for period, statement_dicts in actual_reports.items():
        period_dir = reviewed_dir / period
        assert period_dir.exists(), f"No reviewed fixtures for {loaded.id!r} period {period!r}"
        for statement_type, actual in statement_dicts.items():
            fixture_path = period_dir / f"{statement_type}.json"
            assert fixture_path.exists(), f"Missing reviewed fixture: {fixture_path}"
            expected = json.loads(fixture_path.read_text())
            result = compare.compare_statement(expected, actual)
            if result["status"] == "FAIL":
                failures.append(result)

    assert not failures, json.dumps(failures, indent=2)


def test_core_002_covers_monthly_midyear_and_annual_periods():
    loaded = load_scenario(
        REPO_ROOT / "scenarios" / "foundational" / "core-002-basic-service-business.yaml"
    )
    assert set(loaded.report_periods) == {"2026-01", "2026-06", "2026-12", "2026"}


def test_accr_001_covers_monthly_midyear_and_annual_periods():
    loaded = load_scenario(
        REPO_ROOT / "scenarios" / "accruals" / "accr-001-accrued-payroll-and-utilities.yaml"
    )
    assert set(loaded.report_periods) == {"2026-01", "2026-06", "2026-12", "2026"}


def test_accr_002_covers_both_fiscal_years():
    loaded = load_scenario(
        REPO_ROOT / "scenarios" / "accruals" / "accr-002-prepaid-insurance-and-rent.yaml"
    )
    assert set(loaded.report_periods) == {
        "2026-01",
        "2026-12",
        "2027-01",
        "2027-12",
        "2026",
        "2027",
    }


def test_rev_001_covers_monthly_midyear_and_annual_periods():
    loaded = load_scenario(
        REPO_ROOT / "scenarios" / "revenue-recognition" / "rev-001-advance-service-contract.yaml"
    )
    assert set(loaded.report_periods) == {"2026-01", "2026-06", "2026-12", "2026"}


def test_rev_002_covers_both_fiscal_years():
    loaded = load_scenario(
        REPO_ROOT
        / "scenarios"
        / "revenue-recognition"
        / "rev-002-multiple-performance-obligations.yaml"
    )
    assert set(loaded.report_periods) == {
        "2026-01",
        "2026-12",
        "2027-01",
        "2027-12",
        "2026",
        "2027",
    }


def test_fa_001_covers_five_fiscal_years():
    loaded = load_scenario(
        REPO_ROOT / "scenarios" / "fixed-assets" / "fa-001-straight-line-equipment-depreciation.yaml"
    )
    assert set(loaded.report_periods) == {
        "2026-01",
        "2026-12",
        "2028-06",
        "2030-01",
        "2030-12",
        "2026",
        "2028",
        "2030",
    }


def test_fa_002_covers_both_disposal_months_and_surrounding_years():
    loaded = load_scenario(REPO_ROOT / "scenarios" / "fixed-assets" / "fa-002-asset-disposal.yaml")
    assert set(loaded.report_periods) == {
        "2026-12",
        "2027-12",
        "2028-06",
        "2028-12",
        "2030-12",
        "2026",
        "2027",
        "2028",
        "2030",
    }


def test_inv_001_covers_both_sale_months_and_fiscal_years():
    loaded = load_scenario(REPO_ROOT / "scenarios" / "inventory" / "inv-001-fifo-retail.yaml")
    assert set(loaded.report_periods) == {
        "2026-01",
        "2026-06",
        "2026-12",
        "2027-06",
        "2027-12",
        "2026",
        "2027",
    }


def test_inv_002_covers_both_sale_months_and_fiscal_years():
    loaded = load_scenario(REPO_ROOT / "scenarios" / "inventory" / "inv-002-inventory-write-down.yaml")
    assert set(loaded.report_periods) == {
        "2026-01",
        "2026-06",
        "2026-12",
        "2027-06",
        "2027-12",
        "2026",
        "2027",
    }


def test_inv_001_fifo_cogs_corroborates_the_ledger_independently():
    """reference/schedules/inventory.py's consume_fifo, applied to INV-001's own
    purchase/sale quantities independently of the ledger, must agree with the
    cost_of_goods_sold entries the reference model actually posted -- the same
    "independent schedule corroborates the ledger" pattern as the ACCR-001
    payables cross-check above."""
    from reference.schedules import inventory as inventory_mod

    loaded = load_scenario(REPO_ROOT / "scenarios" / "inventory" / "inv-001-fifo-retail.yaml")

    lots = [
        inventory_mod.Lot(quantity=Decimal(100), unit_cost=Decimal("10.00")),
        inventory_mod.Lot(quantity=Decimal(100), unit_cost=Decimal("12.00")),
    ]
    cogs_1, lots = inventory_mod.consume_fifo(lots, Decimal(150))
    assert cogs_1 == Decimal("1600.00")

    lots.append(inventory_mod.Lot(quantity=Decimal(100), unit_cost=Decimal("15.00")))
    cogs_2, lots = inventory_mod.consume_fifo(lots, Decimal(100))
    assert cogs_2 == Decimal("1350.00")

    balances = loaded.ledger.balances_as_of(date(2027, 12, 31))
    ledger_cogs_total = balances["cost_of_goods_sold"]["ending_balance"]
    assert cogs_1 + cogs_2 == ledger_cogs_total


def test_accr_001_payables_schedule_corroborates_accrued_liability_balances():
    """reference/schedules/payables.py, built independently from the scenario's own
    accrual/payment event dates (not from the ledger), must agree with the ledger's
    accrued_payroll_payable + accrued_utilities_payable balance at every reported
    period -- the "independent schedule corroborates the ledger" pattern described
    in docs/accounting-policy.md."""
    loaded = load_scenario(
        REPO_ROOT / "scenarios" / "accruals" / "accr-001-accrued-payroll-and-utilities.yaml"
    )

    bills: list[payables.Bill] = []
    payments: list[payables.Payment] = []
    for month in range(1, 13):
        accrual_date = period_mod.parse_period(f"2026-{month:02d}")[1]
        bills.append(
            payables.Bill(
                id=f"payroll-{month}", vendor="payroll", bill_date=accrual_date, amount=Decimal("1200.00")
            )
        )
        bills.append(
            payables.Bill(
                id=f"utilities-{month}", vendor="utilities", bill_date=accrual_date, amount=Decimal("150.00")
            )
        )
        if month < 12:
            payment_date = date(2026, month + 1, 1)
            payments.append(
                payables.Payment(
                    id=f"pay-payroll-{month}",
                    bill_id=f"payroll-{month}",
                    payment_date=payment_date,
                    amount=Decimal("1200.00"),
                )
            )
            payments.append(
                payables.Payment(
                    id=f"pay-utilities-{month}",
                    bill_id=f"utilities-{month}",
                    payment_date=payment_date,
                    amount=Decimal("150.00"),
                )
            )

    for period in loaded.report_periods:
        _, period_end = period_mod.parse_period(period)
        schedule_outstanding = payables.outstanding_balance(bills, payments, period_end)

        balances = loaded.ledger.balances_as_of(period_end)
        ledger_outstanding = (
            balances["accrued_payroll_payable"]["ending_balance"]
            + balances["accrued_utilities_payable"]["ending_balance"]
        )
        assert schedule_outstanding == ledger_outstanding, (
            f"payables schedule ({schedule_outstanding}) disagrees with the ledger's "
            f"accrued-liability balance ({ledger_outstanding}) as of {period_end}"
        )
