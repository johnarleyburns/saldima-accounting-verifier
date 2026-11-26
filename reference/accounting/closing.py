"""Period-end closing entries: zero revenue/expense accounts into retained
earnings, or (Phase 5) allocate them across multiple partner capital
accounts by ratio.

See docs/plan.md section 7.1 ("account closure") and section 8 (closing
entries must not change historical transaction amounts -- this module only
ever appends a new, balanced JournalEntry; it never edits existing entries).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from reference.accounting.journal import (
    AccountingError,
    AccountType,
    ChartOfAccounts,
    JournalEntry,
    make_line,
)
from reference.accounting.ledger import Ledger
from reference.accounting.rounding import ZERO, round_currency

ONE = Decimal("1.00")


def _closing_targets(
    chart: ChartOfAccounts,
    retained_earnings_account_id: str | None,
    partner_allocations: dict[str, Decimal] | None,
) -> dict[str, Decimal]:
    if (retained_earnings_account_id is None) == (partner_allocations is None):
        raise AccountingError(
            "close_period: pass exactly one of retained_earnings_account_id or partner_allocations"
        )
    if retained_earnings_account_id is not None:
        if retained_earnings_account_id not in chart:
            raise AccountingError(f"Unknown retained earnings account: {retained_earnings_account_id!r}")
        return {retained_earnings_account_id: ONE}

    assert partner_allocations is not None  # narrowed by the check above
    total_ratio = sum(partner_allocations.values(), ZERO)
    if total_ratio != ONE:
        raise AccountingError(f"partner_allocations ratios must sum to 1.00 (got {total_ratio})")
    for account_id in partner_allocations:
        if account_id not in chart:
            raise AccountingError(f"Unknown partner capital account: {account_id!r}")
    return partner_allocations


def close_period(
    ledger: Ledger,
    chart: ChartOfAccounts,
    period_start: date,
    period_end: date,
    retained_earnings_account_id: str | None,
    entry_id: str,
    *,
    partner_allocations: dict[str, Decimal] | None = None,
) -> JournalEntry | None:
    """Close net revenue/expense activity for [period_start, period_end] into
    retained earnings (pass `retained_earnings_account_id`) or allocate it
    across multiple partner capital accounts by ratio (pass
    `partner_allocations`, a `{account_id: ratio}` mapping whose ratios sum
    to exactly 1.00) -- exactly one of the two must be given.

    Each target gets `round_currency(net_to_retained_earnings * ratio)`
    except the *last* target in `partner_allocations`'s iteration order,
    which gets the exact remainder -- the same remainder-to-last convention
    every reference/schedules/* module already uses. For a single target
    (the `retained_earnings_account_id` case, or a one-entry
    `partner_allocations`) that target always *is* "the last one," so it
    gets the full, unrounded amount -- this is exactly today's single-
    account behavior, not a new rounding step.

    Returns the posted closing entry, or None if the period had zero net
    activity (closing entries, like all journal entries, must have nonzero
    net effect).
    """
    targets = _closing_targets(chart, retained_earnings_account_id, partner_allocations)

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

    target_ids = list(targets.keys())
    allocated_so_far = ZERO
    for i, account_id in enumerate(target_ids):
        if i == len(target_ids) - 1:
            amount = net_to_retained_earnings - allocated_so_far
        else:
            amount = round_currency(net_to_retained_earnings * targets[account_id])
            allocated_so_far += amount

        if amount > ZERO:
            lines.append(make_line(account_id, credit=str(amount)))
        elif amount < ZERO:
            lines.append(make_line(account_id, debit=str(-amount)))

    entry = JournalEntry(
        id=entry_id,
        date=period_end,
        lines=tuple(lines),
        memo=f"Closing entry for {period_start}..{period_end}",
        is_closing=True,
    )
    ledger.post(entry)
    return entry
