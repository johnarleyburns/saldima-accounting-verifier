"""Multi-year carry-forward tests (docs/plan.md section 8, docs/test-categories.md).

ACCR-002 is the first Phase 2 scenario to span two fiscal years with two
separate year-end closings (2026-12-31 and 2027-12-31), making it the right
fixture to prove: retained earnings accumulates correctly across both
closings, and posting 2027's activity/closing never changes 2026's already-
reported figures (release-gate rule 5: "no historical reporting period
changes unexpectedly" -- docs/release-gates.md).
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

from reference.accounting import balance_sheet, closing, income_statement, trial_balance
from reference.accounting.ledger import Ledger
from reference.reporting import statements as statements_mod
from runner import period as period_mod
from runner import reference_runner
from runner.scenario_runner import load_scenario

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ACCR_002 = REPO_ROOT / "scenarios" / "accruals" / "accr-002-prepaid-insurance-and-rent.yaml"
FIRST_CLOSING_DATE = date(2026, 12, 31)


def test_retained_earnings_accumulates_across_both_fiscal_year_closings():
    loaded = load_scenario(ACCR_002)
    reports = reference_runner.run(loaded)

    def net_income(period: str) -> Decimal:
        return Decimal(reports[period]["income_statement"]["lines"]["net_income"]["ending_balance"])

    def retained_earnings(period: str) -> Decimal:
        return Decimal(reports[period]["balance_sheet"]["lines"]["retained_earnings"]["ending_balance"])

    assert retained_earnings("2026-12") == net_income("2026")
    assert retained_earnings("2027-12") == net_income("2026") + net_income("2027")


def test_2026_reviewed_figures_are_unaffected_by_2027s_later_activity_and_closing():
    """2026's statements, computed from a ledger that only ever saw 2026's own
    activity, must match 2026's statements computed from the full two-year
    ledger (which also contains all of 2027's events and its own closing
    entry) -- i.e. nothing that happens after a historical period is allowed
    to change it."""
    full_loaded = load_scenario(ACCR_002)
    full_reports = reference_runner.run(full_loaded)

    # A fresh ledger containing only the entries dated on or before the first
    # fiscal year's closing date, as if the scenario had ended after 2026 --
    # `load_scenario` posts every event regardless of date, and closing
    # entries aren't applied until `reference_runner.run`, so this is just
    # 2026's business activity.
    year_1_loaded = load_scenario(ACCR_002)
    chart = year_1_loaded.chart
    truncated_ledger = Ledger(chart=chart)
    for entry in year_1_loaded.ledger.entries:
        if entry.date <= FIRST_CLOSING_DATE:
            truncated_ledger.post(entry)
    closing.close_period(
        truncated_ledger, chart, date(2026, 1, 1), FIRST_CLOSING_DATE, "retained_earnings", "closing-2026-12-31"
    )

    for period in ("2026-01", "2026"):
        start, end = period_mod.parse_period(period)
        tb = trial_balance.generate(truncated_ledger, chart, end, "accr-002", period)
        income = income_statement.generate(truncated_ledger, chart, start, end, "accr-002", period)
        bs = balance_sheet.generate(truncated_ledger, chart, end, date(2026, 1, 1), "accr-002", period)

        assert statements_mod.trial_balance_to_dict(tb)["lines"] == full_reports[period]["trial_balance"]["lines"]
        assert (
            statements_mod.income_statement_to_dict(income)["lines"]
            == full_reports[period]["income_statement"]["lines"]
        )
        assert statements_mod.balance_sheet_to_dict(bs)["lines"] == full_reports[period]["balance_sheet"]["lines"]
