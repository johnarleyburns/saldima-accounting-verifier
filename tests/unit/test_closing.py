from datetime import date
from decimal import Decimal

import pytest

from reference.accounting.closing import close_period
from reference.accounting.journal import (
    Account,
    AccountingError,
    AccountType,
    ChartOfAccounts,
    JournalEntry,
    make_line,
)
from reference.accounting.ledger import Ledger


def _build_chart(*equity_ids: str) -> ChartOfAccounts:
    chart = ChartOfAccounts()
    chart.add(Account(id="cash", name="Cash", type=AccountType.ASSET))
    chart.add(Account(id="revenue", name="Revenue", type=AccountType.REVENUE))
    chart.add(Account(id="expense", name="Expense", type=AccountType.EXPENSE))
    for equity_id in equity_ids:
        chart.add(Account(id=equity_id, name=equity_id, type=AccountType.EQUITY))
    return chart


def test_single_target_matches_todays_behavior_exactly():
    chart = _build_chart("retained_earnings")
    ledger = Ledger(chart=chart)
    ledger.post(
        JournalEntry(id="e1", date=date(2026, 1, 1), lines=(make_line("cash", debit="1000.00"), make_line("revenue", credit="1000.00")))
    )
    ledger.post(
        JournalEntry(id="e2", date=date(2026, 1, 2), lines=(make_line("expense", debit="700.00"), make_line("cash", credit="700.00")))
    )

    entry = close_period(
        ledger, chart, date(2026, 1, 1), date(2026, 12, 31), "retained_earnings", "closing-1"
    )
    assert entry is not None
    retained_earnings_line = next(line for line in entry.lines if line.account_id == "retained_earnings")
    assert retained_earnings_line.credit == Decimal("300.00")
    assert retained_earnings_line.debit == Decimal("0.00")


def test_two_way_allocation_splits_net_income_by_ratio():
    chart = _build_chart("partner_a", "partner_b")
    ledger = Ledger(chart=chart)
    ledger.post(
        JournalEntry(id="e1", date=date(2026, 1, 1), lines=(make_line("cash", debit="1000.00"), make_line("revenue", credit="1000.00")))
    )

    entry = close_period(
        ledger,
        chart,
        date(2026, 1, 1),
        date(2026, 12, 31),
        None,
        "closing-1",
        partner_allocations={"partner_a": Decimal("0.60"), "partner_b": Decimal("0.40")},
    )
    assert entry is not None
    by_account = {line.account_id: line for line in entry.lines}
    assert by_account["partner_a"].credit == Decimal("600.00")
    assert by_account["partner_b"].credit == Decimal("400.00")


def test_allocation_remainder_lands_on_the_last_listed_partner():
    chart = _build_chart("partner_a", "partner_b", "partner_c")
    ledger = Ledger(chart=chart)
    # 1000.00 split 1/3 each: 333.33 + 333.33 + 333.34 (remainder on the last).
    ledger.post(
        JournalEntry(id="e1", date=date(2026, 1, 1), lines=(make_line("cash", debit="1000.00"), make_line("revenue", credit="1000.00")))
    )

    entry = close_period(
        ledger,
        chart,
        date(2026, 1, 1),
        date(2026, 12, 31),
        None,
        "closing-1",
        partner_allocations={
            "partner_a": Decimal("0.3333333333"),
            "partner_b": Decimal("0.3333333333"),
            "partner_c": Decimal("0.3333333334"),
        },
    )
    assert entry is not None
    by_account = {line.account_id: line for line in entry.lines}
    assert by_account["partner_a"].credit == Decimal("333.33")
    assert by_account["partner_b"].credit == Decimal("333.33")
    assert by_account["partner_c"].credit == Decimal("333.34")
    total = sum((line.credit for line in entry.lines if line.account_id.startswith("partner_")), Decimal("0.00"))
    assert total == Decimal("1000.00")


def test_allocation_splits_a_net_loss_too():
    chart = _build_chart("partner_a", "partner_b")
    ledger = Ledger(chart=chart)
    ledger.post(
        JournalEntry(id="e1", date=date(2026, 1, 1), lines=(make_line("expense", debit="1000.00"), make_line("cash", credit="1000.00")))
    )

    entry = close_period(
        ledger,
        chart,
        date(2026, 1, 1),
        date(2026, 12, 31),
        None,
        "closing-1",
        partner_allocations={"partner_a": Decimal("0.50"), "partner_b": Decimal("0.50")},
    )
    assert entry is not None
    by_account = {line.account_id: line for line in entry.lines}
    assert by_account["partner_a"].debit == Decimal("500.00")
    assert by_account["partner_b"].debit == Decimal("500.00")


def test_passing_both_targets_is_rejected():
    chart = _build_chart("retained_earnings", "partner_a")
    ledger = Ledger(chart=chart)
    with pytest.raises(AccountingError, match="exactly one of"):
        close_period(
            ledger,
            chart,
            date(2026, 1, 1),
            date(2026, 12, 31),
            "retained_earnings",
            "closing-1",
            partner_allocations={"partner_a": Decimal("1.00")},
        )


def test_passing_neither_target_is_rejected():
    chart = _build_chart("retained_earnings")
    ledger = Ledger(chart=chart)
    with pytest.raises(AccountingError, match="exactly one of"):
        close_period(ledger, chart, date(2026, 1, 1), date(2026, 12, 31), None, "closing-1")


def test_allocation_ratios_must_sum_to_one():
    chart = _build_chart("partner_a", "partner_b")
    ledger = Ledger(chart=chart)
    ledger.post(
        JournalEntry(id="e1", date=date(2026, 1, 1), lines=(make_line("cash", debit="1000.00"), make_line("revenue", credit="1000.00")))
    )
    with pytest.raises(AccountingError, match="must sum to 1.00"):
        close_period(
            ledger,
            chart,
            date(2026, 1, 1),
            date(2026, 12, 31),
            None,
            "closing-1",
            partner_allocations={"partner_a": Decimal("0.50"), "partner_b": Decimal("0.40")},
        )


def test_unknown_partner_account_is_rejected():
    chart = _build_chart("partner_a")
    ledger = Ledger(chart=chart)
    ledger.post(
        JournalEntry(id="e1", date=date(2026, 1, 1), lines=(make_line("cash", debit="1000.00"), make_line("revenue", credit="1000.00")))
    )
    with pytest.raises(AccountingError, match="Unknown partner capital account"):
        close_period(
            ledger,
            chart,
            date(2026, 1, 1),
            date(2026, 12, 31),
            None,
            "closing-1",
            partner_allocations={"partner_a": Decimal("0.50"), "nonexistent": Decimal("0.50")},
        )
