"""Accounts-receivable open-item tracking and aging.

Pure Decimal, no dependency on Saldima production code -- see
reference/schedules/README.md and docs/plan.md section 2.1. This schedule
is deliberately independent of any ledger: it is built directly from
invoice/payment records so it can corroborate (not merely restate) a
ledger's accounts-receivable balance -- the same role
reference/schedules/payables.py plays for accrued liabilities in
tests/integration/test_core_scenarios.py's ACCR-001 cross-check.

No Phase 2 gold-standard scenario exercises a trade receivable yet (none of
ACCR-001/002 or REV-001/002 involve invoice-now-collect-later credit sales
-- see docs/accounting-policy.md for why that gap is left open rather than
forced into an unrelated scenario). This module is unit-tested directly
(tests/unit/test_receivables.py) pending that scenario.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from reference.accounting.rounding import ZERO


@dataclass(frozen=True)
class Invoice:
    id: str
    customer: str
    invoice_date: date
    amount: Decimal


@dataclass(frozen=True)
class Payment:
    id: str
    invoice_id: str
    payment_date: date
    amount: Decimal


def outstanding_balance(invoices: list[Invoice], payments: list[Payment], as_of: date) -> Decimal:
    """Total unpaid invoice balance as of `as_of` (invoices/payments dated on or before it)."""
    invoiced = sum((inv.amount for inv in invoices if inv.invoice_date <= as_of), ZERO)
    paid = sum((p.amount for p in payments if p.payment_date <= as_of), ZERO)
    return invoiced - paid


def open_balance_by_invoice(
    invoices: list[Invoice], payments: list[Payment], as_of: date
) -> dict[str, Decimal]:
    """Per-invoice unpaid balance as of `as_of`, excluding fully-paid invoices."""
    balances: dict[str, Decimal] = {}
    for invoice in invoices:
        if invoice.invoice_date > as_of:
            continue
        paid = sum(
            (p.amount for p in payments if p.invoice_id == invoice.id and p.payment_date <= as_of),
            ZERO,
        )
        remaining = invoice.amount - paid
        if remaining != ZERO:
            balances[invoice.id] = remaining
    return balances


def aging_schedule(
    invoices: list[Invoice],
    payments: list[Payment],
    as_of: date,
    buckets: tuple[int, ...] = (30, 60, 90),
) -> list[dict[str, object]]:
    """Open invoices as of `as_of`, bucketed by days outstanding.

    Returns items shaped for schemas/schedule.schema.json's `items` array:
    `{invoice_id, customer, amount, days_outstanding, bucket}`. `bucket` is
    "current" at or under `buckets[0]` days, "<lo>-<hi>" for each further
    boundary, and "<last>+" beyond the final boundary.
    """
    open_balances = open_balance_by_invoice(invoices, payments, as_of)
    by_id = {invoice.id: invoice for invoice in invoices}
    items: list[dict[str, object]] = []
    for invoice_id, amount in open_balances.items():
        invoice = by_id[invoice_id]
        days_outstanding = (as_of - invoice.invoice_date).days
        items.append(
            {
                "invoice_id": invoice_id,
                "customer": invoice.customer,
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
