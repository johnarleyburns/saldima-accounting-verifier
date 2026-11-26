"""Equal-principal, declining-interest loan amortization schedules.

Pure Decimal, no dependency on Saldima production code -- see
reference/schedules/README.md and docs/plan.md section 2.1. Phase 4
scope: a scenario author describes a loan's principal/rate/term
declaratively (see docs/scenario-authoring.md, the `loan_origination`
event type); this module computes the period-by-period principal/
interest split that the reference model then translates into journal
entries (runner/scenario_runner.py).

This is deliberately an equal-principal loan (the monthly principal
payment is level; interest declines as the balance declines), not the
standard level-total-payment annuity (`payment = P*r / (1-(1+r)^-n)`).
Both are real business-loan structures, but the annuity formula's payment
amount essentially never lands on a clean cent for arbitrary rate/term
combinations, which would make a gold-standard scenario's hand-
verification arithmetic needlessly tedious. See docs/accounting-policy.md.
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from reference.accounting.journal import AccountingError
from reference.accounting.rounding import round_currency


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _add_months(start: date, months: int) -> date:
    total_months = (start.month - 1) + months
    year = start.year + total_months // 12
    month = total_months % 12 + 1
    return date(year, month, 1)


def build_amortization_schedule(
    principal: Decimal,
    annual_interest_rate: Decimal,
    term_months: int,
    start_date: date,
    precision: int = 2,
    method: str = "HALF_UP",
) -> list[tuple[date, Decimal, Decimal, Decimal]]:
    """Monthly (period_end, interest, principal_payment, remaining_balance)
    for an equal-principal loan, starting the month of `start_date`.

    `start_date` must be the first day of its month (same convention as
    reference/schedules/depreciation.py's `in_service_date`). The equal
    monthly principal payment is `principal / term_months`, with the
    rounding remainder absorbed into the last month -- the same
    convention used throughout reference/schedules/. Each month's
    interest is the *remaining* balance (before that month's principal
    payment) times the monthly rate (`annual_interest_rate / 12`),
    rounded.
    """
    if start_date.day != 1:
        raise AccountingError(f"loan_origination start date {start_date} must be the first day of its month")
    if term_months < 1:
        raise AccountingError(f"term_months must be at least 1 (got {term_months})")
    if principal <= Decimal(0):
        raise AccountingError(f"principal must be positive (got {principal})")

    monthly_rate = annual_interest_rate / Decimal(12)
    equal_principal_payment = round_currency(principal / term_months, precision, method)

    schedule: list[tuple[date, Decimal, Decimal, Decimal]] = []
    remaining_balance = principal
    for i in range(term_months):
        month_start = _add_months(start_date, i)
        period_end = _month_end(month_start.year, month_start.month)

        interest = round_currency(remaining_balance * monthly_rate, precision, method)
        if i == term_months - 1:
            # Last month absorbs the rounding remainder, like every other
            # equal-split schedule in this repo.
            principal_payment = remaining_balance
        else:
            principal_payment = equal_principal_payment

        remaining_balance -= principal_payment
        schedule.append((period_end, interest, principal_payment, remaining_balance))

    return schedule
