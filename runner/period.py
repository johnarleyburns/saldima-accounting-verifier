"""Reporting-period parsing.

Supported period strings: "YYYY-MM" (calendar month), "YYYY-QN" (calendar
quarter), "YYYY" or "YYYY-FY" (full fiscal year). This Phase 1 implementation
assumes the fiscal year equals the calendar year (fiscal_year_end "12-31");
non-calendar fiscal years are deferred (see docs/plan.md section 8).
"""

from __future__ import annotations

import calendar
import re
from datetime import date

_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")
_QUARTER_RE = re.compile(r"^(\d{4})-Q([1-4])$")
_YEAR_RE = re.compile(r"^(\d{4})(?:-FY)?$")


def parse_period(period: str) -> tuple[date, date]:
    """Return (start, end) dates for a period string, inclusive on both ends."""
    if match := _MONTH_RE.match(period):
        year, month = int(match.group(1)), int(match.group(2))
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)
    if match := _QUARTER_RE.match(period):
        year, quarter = int(match.group(1)), int(match.group(2))
        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 2
        last_day = calendar.monthrange(year, end_month)[1]
        return date(year, start_month, 1), date(year, end_month, last_day)
    if match := _YEAR_RE.match(period):
        year = int(match.group(1))
        return date(year, 1, 1), date(year, 12, 31)
    raise ValueError(f"Unrecognized period format: {period!r}")


def fiscal_year_start(as_of: date) -> date:
    return date(as_of.year, 1, 1)
