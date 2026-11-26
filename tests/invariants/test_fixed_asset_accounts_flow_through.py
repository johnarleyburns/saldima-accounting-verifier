"""Confirms (not just assumes) that fixed-asset accounts flow correctly
through trial_balance.py, balance_sheet.py, and cash_flow.py, independent
of any one scenario's bookkeeping choices.

Two claims from docs/accounting-policy.md's Phase 3 section, proved
directly on a hand-built ledger:

1. A contra-asset account (accumulated depreciation) declared `type:
   asset` naturally goes negative (it only ever receives credits) and
   nets against the gross asset account in `total_assets` to produce net
   book value -- no change needed to balance_sheet.py/trial_balance.py,
   which are already generic over AccountType.
2. `cash_flow.py`'s new `cash_flow_category` classification correctly
   separates the equipment purchase (investing, a use of cash) from the
   depreciation add-back (operating, a source of cash) -- the classic
   indirect-method treatment, which falls out of the existing generic
   asset-delta logic for free once the account is tagged `investing`.
"""

from datetime import date
from decimal import Decimal

from reference.accounting import balance_sheet, cash_flow, trial_balance
from reference.accounting.journal import (
    Account,
    AccountType,
    CashFlowCategory,
    ChartOfAccounts,
    JournalEntry,
    make_line,
)
from reference.accounting.ledger import Ledger


def _build_chart() -> ChartOfAccounts:
    chart = ChartOfAccounts()
    chart.add(Account(id="cash", name="Cash", type=AccountType.ASSET))
    chart.add(
        Account(
            id="equipment",
            name="Equipment",
            type=AccountType.ASSET,
            cash_flow_category=CashFlowCategory.INVESTING,
        )
    )
    chart.add(Account(id="accumulated_depreciation", name="Accumulated Depreciation", type=AccountType.ASSET))
    chart.add(Account(id="equity", name="Equity", type=AccountType.EQUITY))
    chart.add(Account(id="depreciation_expense", name="Depreciation Expense", type=AccountType.EXPENSE))
    return chart


def _build_ledger(chart: ChartOfAccounts) -> Ledger:
    ledger = Ledger(chart=chart)
    ledger.post(
        JournalEntry(
            id="e1",
            date=date(2026, 1, 1),
            lines=(make_line("cash", debit="10000.00"), make_line("equity", credit="10000.00")),
        )
    )
    ledger.post(
        JournalEntry(
            id="e2",
            date=date(2026, 1, 1),
            lines=(make_line("equipment", debit="6000.00"), make_line("cash", credit="6000.00")),
        )
    )
    ledger.post(
        JournalEntry(
            id="e3",
            date=date(2026, 1, 31),
            lines=(
                make_line("depreciation_expense", debit="100.00"),
                make_line("accumulated_depreciation", credit="100.00"),
            ),
        )
    )
    return ledger


def test_contra_asset_nets_into_total_assets_as_net_book_value():
    chart = _build_chart()
    ledger = _build_ledger(chart)
    as_of = date(2026, 1, 31)

    tb = trial_balance.generate(ledger, chart, as_of, "inv-test", "2026-01")
    tb.assert_balanced()  # must not raise

    bs = balance_sheet.generate(ledger, chart, as_of, date(2026, 1, 1), "inv-test", "2026-01")
    bs.assert_balances()  # must not raise

    assert bs.assets["equipment"] == Decimal("6000.00")
    assert bs.assets["accumulated_depreciation"] == Decimal("-100.00")
    # Net book value of the equipment (gross cost + the contra-asset's
    # negative balance) falls out of a plain sum over asset accounts.
    net_book_value = bs.assets["equipment"] + bs.assets["accumulated_depreciation"]
    assert net_book_value == Decimal("5900.00")


def test_equipment_purchase_is_investing_and_depreciation_addback_is_operating():
    chart = _build_chart()
    ledger = _build_ledger(chart)

    statement = cash_flow.generate(
        ledger, chart, date(2026, 1, 1), date(2026, 1, 31), {"cash"}, "inv-test", "2026-01"
    )
    statement.assert_reconciles()  # must not raise

    # The equipment purchase (an asset increase) is a use of cash,
    # classified investing because the account is tagged that way.
    assert statement.investing_activities == {"equipment": Decimal("-6000.00")}
    assert "equipment" not in statement.operating_adjustments

    # The depreciation add-back (accumulated_depreciation's balance went
    # more negative, i.e. a negative delta) is a *source* of cash, and
    # stays in the default "operating" category.
    assert statement.operating_adjustments["accumulated_depreciation"] == Decimal("100.00")
    assert "accumulated_depreciation" not in statement.investing_activities
