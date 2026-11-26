"""Accounts-payable / accrued-liability open-item tracking and aging.

Pure Decimal, no dependency on Saldima production code -- see
reference/schedules/README.md and docs/plan.md section 2.1. Vendor-side
mirror of reference/schedules/receivables.py: independent of any ledger,
built directly from bill/payment records so it can corroborate a ledger's
payable or accrued-liability balance.

Used for real by tests/integration/test_core_scenarios.py's ACCR-001
cross-check: it independently tracks the monthly payroll/utilities accrual
and the following month's payment as open bills, and the test asserts its
outstanding balance matches the ledger's `accrued_payroll_payable`/
`accrued_utilities_payable` account balances at every reported period. See
docs/accounting-policy.md for why accrued liabilities are treated as a form
of payable here.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from reference.accounting.rounding import ZERO


@dataclass(frozen=True)
class Bill:
    id: str
    vendor: str
    bill_date: date
    amount: Decimal


@dataclass(frozen=True)
class Payment:
    id: str
    bill_id: str
    payment_date: date
    amount: Decimal


def outstanding_balance(bills: list[Bill], payments: list[Payment], as_of: date) -> Decimal:
    """Total unpaid bill balance as of `as_of` (bills/payments dated on or before it)."""
    billed = sum((bill.amount for bill in bills if bill.bill_date <= as_of), ZERO)
    paid = sum((p.amount for p in payments if p.payment_date <= as_of), ZERO)
    return billed - paid


def open_balance_by_bill(bills: list[Bill], payments: list[Payment], as_of: date) -> dict[str, Decimal]:
    """Per-bill unpaid balance as of `as_of`, excluding fully-paid bills."""
    balances: dict[str, Decimal] = {}
    for bill in bills:
        if bill.bill_date > as_of:
            continue
        paid = sum(
            (p.amount for p in payments if p.bill_id == bill.id and p.payment_date <= as_of),
            ZERO,
        )
        remaining = bill.amount - paid
        if remaining != ZERO:
            balances[bill.id] = remaining
    return balances


def aging_schedule(
    bills: list[Bill],
    payments: list[Payment],
    as_of: date,
    buckets: tuple[int, ...] = (30, 60, 90),
) -> list[dict[str, object]]:
    """Open bills as of `as_of`, bucketed by days outstanding.

    Returns items shaped for schemas/schedule.schema.json's `items` array:
    `{bill_id, vendor, amount, days_outstanding, bucket}`. `bucket` is
    "current" at or under `buckets[0]` days, "<lo>-<hi>" for each further
    boundary, and "<last>+" beyond the final boundary.
    """
    open_balances = open_balance_by_bill(bills, payments, as_of)
    by_id = {bill.id: bill for bill in bills}
    items: list[dict[str, object]] = []
    for bill_id, amount in open_balances.items():
        bill = by_id[bill_id]
        days_outstanding = (as_of - bill.bill_date).days
        items.append(
            {
                "bill_id": bill_id,
                "vendor": bill.vendor,
                "amount": f"{amount:.2f}",
                "days_outstanding": days_outstanding,
                "bucket": _bucket(days_outstanding, buckets),
            }
        )
    return items


def _bucket(days_outstanding: int, buckets: tuple[int, ...]) -> str:
    if days_outstanding <= buckets[0]:
        return "current"
    for lo, hi in itertools.pairwise(buckets):
        if days_outstanding <= hi:
            return f"{lo}-{hi}"
    return f"{buckets[-1]}+"
