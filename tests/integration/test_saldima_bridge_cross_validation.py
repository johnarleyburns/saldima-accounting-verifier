"""Cross-engine validation against the real Saldima engine, via
adapters/saldima's bridge to packages/gnucash in the sibling `saldima`
repository. Skipped entirely unless SALDIMA_REPO_PATH points at a real
checkout -- this repo's own CI never has that sibling repo available --
see docs/accounting-policy.md's "Saldima bridge" section.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from adapters.saldima import bridge as saldima_bridge
from adapters.saldima.adapter import SaldimaAdapter
from reference.accounting import balance_sheet, income_statement
from runner import compare
from runner import period as period_mod
from runner.reference_runner import apply_closing_entries
from runner.scenario_runner import load_scenario

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

pytestmark = pytest.mark.skipif(
    not saldima_bridge.is_available(),
    reason=(
        "SALDIMA_REPO_PATH not set to a real saldima checkout (or pnpm not on PATH) -- "
        "see docs/accounting-policy.md's 'Saldima bridge' section"
    ),
)

# (scenario file, a period ending at a point with zero unclosed current_period_earnings
#  -- for the trial-balance/balance-sheet checks --, a period that doesn't span a closing
#  date -- for the income-statement check, which has no "exclude closing" concept on the
#  Saldima side; see docs/accounting-policy.md)
SCENARIOS = [
    (
        REPO_ROOT / "scenarios" / "foundational" / "core-002-basic-service-business.yaml",
        "2026",
        "2026-06",
    ),
    (
        REPO_ROOT
        / "scenarios"
        / "fixed-assets"
        / "fa-001-straight-line-equipment-depreciation.yaml",
        "2030-12",
        "2028-06",
    ),
]


@pytest.mark.parametrize(
    "scenario_path,balance_period,income_period",
    SCENARIOS,
    ids=lambda p: p.stem if isinstance(p, Path) else p,
)
def test_trial_balance_matches_the_real_saldima_engine(
    scenario_path: Path, balance_period: str, income_period: str
) -> None:
    repo_path = saldima_bridge.saldima_repo_path()
    assert repo_path is not None

    loaded = load_scenario(scenario_path)
    adapter = SaldimaAdapter(repo_path)
    try:
        book_id = adapter.create_book(loaded.raw)
        actual = adapter.get_trial_balance(book_id, balance_period)

        reviewed_path = (
            REPO_ROOT / "expected" / "reviewed" / loaded.id / balance_period / "trial_balance.json"
        )
        expected = json.loads(reviewed_path.read_text())

        result = compare.compare_statement(expected, actual)
        assert result["status"] == "PASS", json.dumps(result, indent=2)
    finally:
        adapter.close()


@pytest.mark.parametrize(
    "scenario_path,balance_period,income_period",
    SCENARIOS,
    ids=lambda p: p.stem if isinstance(p, Path) else p,
)
def test_balance_sheet_and_income_statement_aggregates_match_the_real_saldima_engine(
    scenario_path: Path, balance_period: str, income_period: str
) -> None:
    repo_path = saldima_bridge.saldima_repo_path()
    assert repo_path is not None

    # Our own, independently-computed aggregates -- a fresh load, entirely
    # separate from the (also fresh) ledger the adapter builds below.
    loaded = load_scenario(scenario_path)
    apply_closing_entries(loaded)
    as_of = period_mod.parse_period(balance_period)[1]
    fiscal_year_start = period_mod.fiscal_year_start(as_of)
    our_balance_sheet = balance_sheet.generate(
        loaded.ledger, loaded.chart, as_of, fiscal_year_start, loaded.id, balance_period
    )

    income_start, income_end = period_mod.parse_period(income_period)
    our_income_statement = income_statement.generate(
        loaded.ledger, loaded.chart, income_start, income_end, loaded.id, income_period
    )

    adapter = SaldimaAdapter(repo_path)
    try:
        book_id = adapter.create_book(loaded.raw)

        saldima_balance_sheet = adapter.get_financial_statements(book_id, balance_period)[
            "balance_sheet"
        ]["lines"]
        saldima_income_statement = adapter.get_financial_statements(book_id, income_period)[
            "income_statement"
        ]["lines"]

        assert (
            Decimal(saldima_balance_sheet["total_assets"]["ending_balance"])
            == our_balance_sheet.total_assets
        )
        assert (
            Decimal(saldima_balance_sheet["total_liabilities"]["ending_balance"])
            == our_balance_sheet.total_liabilities
        )
        assert (
            Decimal(saldima_balance_sheet["total_equity"]["ending_balance"])
            == our_balance_sheet.total_equity
        )

        assert (
            Decimal(saldima_income_statement["total_revenue"]["ending_balance"])
            == our_income_statement.total_revenue
        )
        assert (
            Decimal(saldima_income_statement["total_expenses"]["ending_balance"])
            == our_income_statement.total_expenses
        )
        assert (
            Decimal(saldima_income_statement["net_income"]["ending_balance"])
            == our_income_statement.net_income
        )
    finally:
        adapter.close()
