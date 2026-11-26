"""Straight-line depreciation schedules and disposal gain/loss.

Pure Decimal, no dependency on Saldima production code -- see
reference/schedules/README.md and docs/plan.md section 2.1. Phase 3 scope:
a scenario author describes a fixed-asset purchase declaratively (see
docs/scenario-authoring.md, the `fixed_asset_purchase` event type); this
module computes the depreciation schedule (and, for `fixed_asset_disposal`,
the gain/loss) that the reference model then translates into journal
entries (runner/scenario_runner.py).
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


def build_straight_line_schedule(
    cost: Decimal,
    salvage_value: Decimal,
    in_service_date: date,
    useful_life_months: int,
    precision: int = 2,
    method: str = "HALF_UP",
    through: date | None = None,
) -> list[tuple[date, Decimal]]:
    """Monthly straight-line depreciation from `in_service_date`'s month for
    `useful_life_months` months, each dated at month-end.

    Phase 3 scope: `in_service_date` must be the first day of its month --
    partial-month proration isn't implemented yet (see
    docs/accounting-policy.md). The depreciable base (`cost - salvage_value`)
    is split evenly across every month, with the rounding remainder absorbed
    into the last month -- the same convention
    reference/schedules/deferred_revenue.py uses.

    `through`, if given, truncates the schedule to the last full month on or
    before that date (used when a `fixed_asset_disposal` event ends the
    asset's useful life early -- see docs/accounting-policy.md). It must not
    fall before the first depreciation month.
    """
    if in_service_date.day != 1:
        raise AccountingError(
            f"fixed_asset_purchase in_service_date {in_service_date} must be the first day of its month"
        )
    if useful_life_months < 1:
        raise AccountingError(f"useful_life_months must be at least 1 (got {useful_life_months})")
    if salvage_value > cost:
        raise AccountingError(f"salvage_value ({salvage_value}) cannot exceed cost ({cost})")

    depreciable_base = cost - salvage_value
    full_month_ends: list[date] = []
    for i in range(useful_life_months):
        month_start = _add_months(in_service_date, i)
        full_month_ends.append(_month_end(month_start.year, month_start.month))

    month_ends = full_month_ends
    if through is not None:
        month_ends = [month_end for month_end in full_month_ends if month_end <= through]
        if not month_ends:
            raise AccountingError(
                f"disposal date {through} is before the first depreciation month {full_month_ends[0]}"
            )

    n_full = len(full_month_ends)
    per_month = round_currency(depreciable_base / n_full, precision, method)

    if len(month_ends) == n_full:
        # The full schedule: the last month absorbs the rounding remainder.
        schedule = [(month_end, per_month) for month_end in month_ends[:-1]]
        allocated = per_month * (n_full - 1)
        schedule.append((month_ends[-1], depreciable_base - allocated))
        return schedule

    # Truncated by an early disposal: every remaining month still uses the
    # even per-month amount (the remainder only ever applies to the asset's
    # final scheduled month, which a disposal by definition never reaches).
    return [(month_end, per_month) for month_end in month_ends]


def disposal_gain_loss(cost: Decimal, accumulated_depreciation: Decimal, proceeds: Decimal) -> Decimal:
    """Gain (positive) or loss (negative) on disposing of a fixed asset.

    `book_value = cost - accumulated_depreciation`; `gain_loss = proceeds -
    book_value`. Positive means a gain (credit a gain account), negative
    means a loss (debit a loss account) -- see
    runner/scenario_runner.py's `_translate_fixed_asset_disposal`.
    """
    book_value = cost - accumulated_depreciation
    return proceeds - book_value
