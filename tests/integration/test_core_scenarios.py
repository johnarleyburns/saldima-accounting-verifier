"""End-to-end: load a scenario, run the reference model, compare every
requested period's statements against the approved expected/reviewed/
fixtures (never expected/generated/ -- see docs/release-gates.md)."""

import json
from pathlib import Path

import pytest

from runner import compare, reference_runner
from runner.scenario_runner import load_scenario

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCENARIOS = [
    REPO_ROOT / "scenarios" / "foundational" / "core-001-opening-balances.yaml",
    REPO_ROOT / "scenarios" / "foundational" / "core-002-basic-service-business.yaml",
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
