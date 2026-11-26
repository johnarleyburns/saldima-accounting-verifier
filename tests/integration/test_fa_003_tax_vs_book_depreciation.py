"""FA-003: tax (MACRS) versus book (straight-line) depreciation.

Per docs/accounting-policy.md's Phase 3 scope boundary, this scenario's
ledger only ever posts the *book* schedule (see
scenarios/fixed-assets/fa-003-tax-vs-book-depreciation.yaml, compared
against its own expected/reviewed/ fixtures by
tests/integration/test_core_scenarios.py like every other scenario). This
test is the dedicated comparison against the *tax* (MACRS) schedule for
the same asset, computed independently by reference/tax/macrs.py and never
posted to any ledger.
"""

import json
from decimal import Decimal
from pathlib import Path

from reference.tax import macrs
from runner import reference_runner
from runner.scenario_runner import load_scenario

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FA_003 = REPO_ROOT / "scenarios" / "fixed-assets" / "fa-003-tax-vs-book-depreciation.yaml"
BOOK_YEARS = ["2026", "2027", "2028", "2029", "2030"]


def _book_annual_depreciation() -> list[Decimal]:
    loaded = load_scenario(FA_003)
    reports = reference_runner.run(loaded)
    return [
        Decimal(reports[year]["income_statement"]["lines"]["depreciation_expense"]["ending_balance"])
        for year in BOOK_YEARS
    ]


def test_book_depreciation_is_flat_across_exactly_five_years():
    book = _book_annual_depreciation()
    assert book == [Decimal("12000.00")] * 5
    assert sum(book, Decimal("0.00")) == Decimal("60000.00")


def test_macrs_depreciation_is_accelerated_across_six_tax_years():
    tax = macrs.five_year_schedule(Decimal("60000.00"))
    assert tax == [
        Decimal("12000.00"),
        Decimal("19200.00"),
        Decimal("11520.00"),
        Decimal("6912.00"),
        Decimal("6912.00"),
        Decimal("3456.00"),
    ]
    assert len(tax) == 6
    assert sum(tax, Decimal("0.00")) == Decimal("60000.00")


def test_tax_and_book_schedules_diverge_after_year_one():
    """Year one happens to coincide for this specific $60,000 cost (book
    12000.00 == MACRS's 20.00% first-year rate), but the schedules diverge
    from year two onward and span a different number of years entirely --
    the actual "tax versus book" difference this scenario validates."""
    book = _book_annual_depreciation()
    tax = macrs.five_year_schedule(Decimal("60000.00"))

    assert book[0] == tax[0] == Decimal("12000.00")
    assert book[1] != tax[1]
    assert len(book) != len(tax)

    # Total lifetime depreciation is identical either way -- only the
    # timing (and the number of years it's spread across) differs.
    assert sum(book, Decimal("0.00")) == sum(tax, Decimal("0.00")) == Decimal("60000.00")


def test_fa_003_reviewed_fixtures_cover_every_book_year():
    reviewed_dir = REPO_ROOT / "expected" / "reviewed" / "fa-003-tax-vs-book-depreciation"
    for year in BOOK_YEARS:
        fixture = reviewed_dir / year / "income_statement.json"
        assert fixture.exists(), f"Missing reviewed fixture: {fixture}"
        data = json.loads(fixture.read_text())
        assert data["lines"]["depreciation_expense"]["ending_balance"] == "12000.00"
