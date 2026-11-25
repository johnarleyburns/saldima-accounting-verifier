"""Period-end closing entries: zero revenue/expense accounts into retained earnings.

See docs/plan.md section 7.1 ("account closure") and section 8 (closing
entries must not change historical transaction amounts -- this module only
ever appends a new, balanced JournalEntry; it never edits existing entries).
"""

from __future__ import annotations

from datetime import date

from reference.accounting.journal import (
    AccountingError,
    AccountType,
    ChartOfAccounts,
    JournalEntry,
    make_line,
)
from reference.accounting.ledger import Ledger
from reference.accounting.rounding import ZERO, round_currency


def close_period(
    ledger: Ledger,
    chart: ChartOfAccounts,
    period_start: date,
    period_end: date,
    retained_earnings_account_id: str,
    entry_id: str,
) -> JournalEntry | None:
    """Close net revenue/expense activity for [period_start, period_end] into retained earnings.

    Returns the posted closing entry, or None if the period had zero net
    activity (closing entries, like all journal entries, must have nonzero
    net effect).
    """
    if retained_earnings_account_id not in chart:
        raise AccountingError(f"Unknown retained earnings account: {retained_earnings_account_id!r}")

    activity = ledger.period_activity(period_start, period_end)
    lines = []
    net_to_retained_earnings = ZERO

    for account in chart.accounts.values():
        if account.type not in (AccountType.REVENUE, AccountType.EXPENSE):
            continue
        debit_total = activity[account.id]["debit"]
        credit_total = activity[account.id]["credit"]
        if debit_total == ZERO and credit_total == ZERO:
            continue
        if account.type == AccountType.REVENUE:
            # Revenue is credit-normal; zero it by debiting its credit balance.
            net = round_currency(credit_total - debit_total)
            if net > ZERO:
                lines.append(make_line(account.id, debit=str(net)))
                net_to_retained_earnings += net
            elif net < ZERO:
                lines.append(make_line(account.id, credit=str(-net)))
                net_to_retained_earnings += net
        else:
            # Expense is debit-normal; zero it by crediting its debit balance.
            net = round_currency(debit_total - credit_total)
            if net > ZERO:
                lines.append(make_line(account.id, credit=str(net)))
                net_to_retained_earnings -= net
            elif net < ZERO:
                lines.append(make_line(account.id, debit=str(-net)))
                net_to_retained_earnings -= net

    if not lines:
        return None

    if net_to_retained_earnings > ZERO:
        lines.append(make_line(retained_earnings_account_id, credit=str(net_to_retained_earnings)))
    elif net_to_retained_earnings < ZERO:
        lines.append(make_line(retained_earnings_account_id, debit=str(-net_to_retained_earnings)))

    entry = JournalEntry(
        id=entry_id,
        date=period_end,
        lines=tuple(lines),
        memo=f"Closing entry for {period_start}..{period_end}",
        is_closing=True,
    )
    ledger.post(entry)
    return entry
