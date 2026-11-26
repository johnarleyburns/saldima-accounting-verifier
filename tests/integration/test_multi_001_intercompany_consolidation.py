"""MULTI-001: intercompany transactions and consolidation (docs/plan.md
section 19). Each entity's own standalone correctness is already proven
by tests/integration/test_core_scenarios.py (multi-001-parent and
multi-001-subsidiary are in that module's parametrized scenario list).
This test covers the genuinely new arithmetic: the *consolidated*
statements, compared against expected/reviewed/
multi-001-intercompany-transactions/ via the same runner/compare.py
every other integration test uses.
"""

import json
from pathlib import Path

from runner import compare, consolidation_runner

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GROUP_ID = "multi-001-intercompany-transactions"


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


def test_consolidated_balance_sheet_has_no_intercompany_accounts():
    actual_reports = consolidation_runner.run(GROUP_ID)
    for period, statement_dicts in actual_reports.items():
        lines = statement_dicts["balance_sheet"]["lines"]
        for eliminated_id in (
            "investment_in_subsidiary",
            "common_stock",
            "intercompany_receivable",
            "intercompany_payable",
        ):
            assert eliminated_id not in lines, (
                f"{eliminated_id!r} should be eliminated in period {period!r}"
            )


def test_consolidated_income_statement_has_no_intercompany_interest():
    actual_reports = consolidation_runner.run(GROUP_ID)
    for statement_dicts in actual_reports.values():
        lines = statement_dicts["income_statement"]["lines"]
        assert "intercompany_interest_income" not in lines
        assert "intercompany_interest_expense" not in lines
