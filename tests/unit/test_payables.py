from datetime import date
from decimal import Decimal

from reference.schedules import payables


def _bills() -> list[payables.Bill]:
    return [
        payables.Bill(id="bill-1", vendor="acme-supplies", bill_date=date(2026, 1, 1), amount=Decimal("500.00")),
        payables.Bill(id="bill-2", vendor="acme-supplies", bill_date=date(2026, 2, 1), amount=Decimal("300.00")),
        payables.Bill(id="bill-3", vendor="globex-utilities", bill_date=date(2026, 2, 15), amount=Decimal("100.00")),
    ]


def test_outstanding_balance_before_any_payments():
    bills = _bills()
    assert payables.outstanding_balance(bills, [], date(2026, 3, 1)) == Decimal("900.00")


def test_outstanding_balance_ignores_bills_not_yet_issued():
    bills = _bills()
    assert payables.outstanding_balance(bills, [], date(2026, 1, 15)) == Decimal("500.00")


def test_outstanding_balance_after_a_partial_payment():
    bills = _bills()
    payments = [
        payables.Payment(id="p1", bill_id="bill-1", payment_date=date(2026, 1, 20), amount=Decimal("200.00"))
    ]
    assert payables.outstanding_balance(bills, payments, date(2026, 3, 1)) == Decimal("700.00")


def test_open_balance_by_bill_excludes_fully_paid_bills():
    bills = _bills()
    payments = [
        payables.Payment(id="p1", bill_id="bill-1", payment_date=date(2026, 1, 20), amount=Decimal("500.00"))
    ]
    open_balances = payables.open_balance_by_bill(bills, payments, date(2026, 3, 1))
    assert "bill-1" not in open_balances
    assert open_balances["bill-2"] == Decimal("300.00")
    assert open_balances["bill-3"] == Decimal("100.00")


def test_aging_schedule_buckets_by_days_outstanding():
    bills = [
        payables.Bill(id="current", vendor="acme", bill_date=date(2026, 1, 20), amount=Decimal("10.00")),
        payables.Bill(id="31-60", vendor="acme", bill_date=date(2025, 12, 15), amount=Decimal("20.00")),
        payables.Bill(id="91+", vendor="acme", bill_date=date(2025, 10, 1), amount=Decimal("30.00")),
    ]
    items = payables.aging_schedule(bills, [], date(2026, 1, 31))
    by_id = {item["bill_id"]: item for item in items}
    assert by_id["current"]["bucket"] == "current"
    assert by_id["31-60"]["bucket"] == "30-60"
    assert by_id["91+"]["bucket"] == "90+"


def test_aging_schedule_excludes_paid_bills():
    bills = _bills()
    payments = [
        payables.Payment(id="p1", bill_id="bill-1", payment_date=date(2026, 1, 20), amount=Decimal("500.00"))
    ]
    items = payables.aging_schedule(bills, payments, date(2026, 3, 1))
    assert "bill-1" not in {item["bill_id"] for item in items}
