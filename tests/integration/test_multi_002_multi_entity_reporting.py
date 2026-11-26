"""MULTI-002: multi-entity reporting (docs/plan.md section 19). Each
entity's own standalone correctness is already proven by tests/
integration/test_core_scenarios.py (multi-002-parent and
multi-002-subsidiary are in that module's parametrized scenario list).
This test covers the consolidated statements across five annual cycles
with two independent elimination pairs working together (financing-side
intercompany loan, operating-side intercompany management fee),
compared against expected/reviewed/multi-002-multi-entity-reporting/
via the same runner/compare.py every other integration test uses.
"""

import json
from decimal import Decimal
from pathlib import Path

from runner import compare, consolidation_runner

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GROUP_ID = "multi-002-multi-entity-reporting"


def test_consolidated_statements_match_reviewed_fixtures():
    actual_reports = consolidation_runner.run(GROUP_ID)

    reviewed_dir = REPO_ROOT / "expected" / "reviewed" / GROUP_ID
    assert reviewed_dir.exists(), f"No reviewed fixtures for {GROUP_ID!r}"

    failures = []
    for period, statement_dicts in actual_reports.items():
        period_dir = reviewed_dir / period
        assert period_dir.exists(), f"No reviewed fixtures for {GROUP_ID!r} period {period!r}"
        for statement_type, actual in statement_dicts.items():
            fixture_path = period_dir / f"{statement_type}.json"
            assert fixture_path.exists(), f"Missing reviewed fixture: {fixture_path}"
            expected = json.loads(fixture_path.read_text())
            result = compare.compare_statement(expected, actual)
            if result["status"] == "FAIL":
                failures.append(result)

    assert not failures, json.dumps(failures, indent=2)


def test_retained_earnings_grows_monotonically_across_all_five_years():
    """A regression-shaped sanity check independent of the fixture
    comparison above: five consecutive annual closings should never
    make consolidated retained earnings go backwards, since every
    year's net income here is positive."""
    actual_reports = consolidation_runner.run(GROUP_ID)
    values = [
        Decimal(
            actual_reports[period]["balance_sheet"]["lines"]["retained_earnings"]["ending_balance"]
        )
        for period in ("2026", "2027", "2028", "2029", "2030")
    ]
    assert values == sorted(values)
    assert len(set(values)) == len(values)


def test_consolidated_statements_have_no_intercompany_accounts_in_any_year():
    actual_reports = consolidation_runner.run(GROUP_ID)
    eliminated_ids = {
        "investment_in_subsidiary",
        "common_stock",
        "intercompany_receivable",
        "intercompany_payable",
        "intercompany_interest_income",
        "intercompany_interest_expense",
        "intercompany_management_fee_revenue",
        "intercompany_management_fee_expense",
    }
    for statement_dicts in actual_reports.values():
        for statement in statement_dicts.values():
            assert eliminated_ids.isdisjoint(statement["lines"])
