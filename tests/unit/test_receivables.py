from datetime import date
from decimal import Decimal

from reference.schedules import receivables


def _invoices() -> list[receivables.Invoice]:
    return [
        receivables.Invoice(id="inv-1", customer="acme", invoice_date=date(2026, 1, 1), amount=Decimal("500.00")),
        receivables.Invoice(id="inv-2", customer="acme", invoice_date=date(2026, 2, 1), amount=Decimal("300.00")),
        receivables.Invoice(id="inv-3", customer="globex", invoice_date=date(2026, 2, 15), amount=Decimal("100.00")),
    ]


def test_outstanding_balance_before_any_payments():
    invoices = _invoices()
    assert receivables.outstanding_balance(invoices, [], date(2026, 3, 1)) == Decimal("900.00")


def test_outstanding_balance_ignores_invoices_not_yet_issued():
    invoices = _invoices()
    assert receivables.outstanding_balance(invoices, [], date(2026, 1, 15)) == Decimal("500.00")


def test_outstanding_balance_after_a_partial_payment():
    invoices = _invoices()
    payments = [
        receivables.Payment(id="p1", invoice_id="inv-1", payment_date=date(2026, 1, 20), amount=Decimal("200.00"))
    ]
    assert receivables.outstanding_balance(invoices, payments, date(2026, 3, 1)) == Decimal("700.00")


def test_open_balance_by_invoice_excludes_fully_paid_invoices():
    invoices = _invoices()
    payments = [
        receivables.Payment(id="p1", invoice_id="inv-1", payment_date=date(2026, 1, 20), amount=Decimal("500.00"))
    ]
    open_balances = receivables.open_balance_by_invoice(invoices, payments, date(2026, 3, 1))
    assert "inv-1" not in open_balances
    assert open_balances["inv-2"] == Decimal("300.00")
    assert open_balances["inv-3"] == Decimal("100.00")


def test_aging_schedule_buckets_by_days_outstanding():
    invoices = [
        receivables.Invoice(id="current", customer="acme", invoice_date=date(2026, 1, 20), amount=Decimal("10.00")),
        receivables.Invoice(id="31-60", customer="acme", invoice_date=date(2025, 12, 15), amount=Decimal("20.00")),
        receivables.Invoice(id="91+", customer="acme", invoice_date=date(2025, 10, 1), amount=Decimal("30.00")),
    ]
    items = receivables.aging_schedule(invoices, [], date(2026, 1, 31))
    by_id = {item["invoice_id"]: item for item in items}
    assert by_id["current"]["bucket"] == "current"
    assert by_id["31-60"]["bucket"] == "30-60"
    assert by_id["91+"]["bucket"] == "90+"


def test_aging_schedule_excludes_paid_invoices():
    invoices = _invoices()
    payments = [
        receivables.Payment(id="p1", invoice_id="inv-1", payment_date=date(2026, 1, 20), amount=Decimal("500.00"))
    ]
    items = receivables.aging_schedule(invoices, payments, date(2026, 3, 1))
    assert "inv-1" not in {item["invoice_id"] for item in items}
