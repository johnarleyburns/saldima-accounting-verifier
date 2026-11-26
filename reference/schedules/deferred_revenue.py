"""Deferred-revenue recognition schedules (straight-line / point-in-time).

Pure Decimal, no dependency on Saldima production code -- see
reference/schedules/README.md and docs/plan.md section 2.1. Phase 2 scope:
a scenario author describes a customer contract's performance obligations
declaratively (see docs/scenario-authoring.md, the `customer_contract_payment`
event type); this module computes the revenue-recognition schedule that the
reference model then translates into journal entries
(runner/scenario_runner.py). See docs/accounting-policy.md for why this is
the one event type Phase 2 elevates above `manual_journal_entry`.
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from reference.accounting.journal import AccountingError
from reference.accounting.rounding import round_currency


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _month_ends_between(start: date, end: date) -> list[date]:
    """Month-end dates for every calendar month from `start`'s month through `end`'s month.

    Phase 2 scope: `start` must be the first day of its month and `end` must
    be the last day of its month -- partial-month proration is not
    implemented yet (see docs/accounting-policy.md).
    """
    if start.day != 1:
        raise AccountingError(
            f"Straight-line recognition start {start} must be the first day of its month"
        )
    if end != _month_end(end.year, end.month):
        raise AccountingError(
            f"Straight-line recognition end {end} must be the last day of its month"
        )
    if end < start:
        raise AccountingError(f"Straight-line recognition end {end} is before start {start}")

    month_ends = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        month_ends.append(_month_end(year, month))
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return month_ends


def build_straight_line_schedule(
    total: Decimal,
    start: date,
    end: date,
    precision: int = 2,
    method: str = "HALF_UP",
) -> list[tuple[date, Decimal]]:
    """Split `total` evenly across every calendar month in [start, end].

    Returns (month_end_date, amount) pairs, one per month, in chronological
    order. The rounding remainder left over from dividing `total` evenly is
    absorbed into the last month, so the amounts always sum to exactly
    `total` -- the same convention reference/accounting/closing.py already
    uses for its own computed totals.
    """
    month_ends = _month_ends_between(start, end)
    n = len(month_ends)
    per_month = round_currency(total / n, precision, method)
    schedule = [(month_end, per_month) for month_end in month_ends[:-1]]
    allocated = per_month * (n - 1)
    schedule.append((month_ends[-1], total - allocated))
    return schedule
