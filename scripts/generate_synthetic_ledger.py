"""Deterministic synthetic ledger generator for scale/performance testing
(docs/plan.md section 15 and section 18's Phase 7). Not a gold-standard
scenario -- there is no hand-verified expected output for a randomly
generated ledger, and none is claimed. Used by
scripts/run_performance_benchmark.py and tests/performance/
test_performance_smoke.py.

Entries are spread across a fixed 50-year span so a large-enough ledger
also exercises "extended multi-year simulations" (docs/plan.md section
18) without inventing a new named scenario for it.

Usage: python scripts/generate_synthetic_ledger.py 10000
"""

from __future__ import annotations

import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from reference.accounting import closing
from reference.accounting.journal import (
    Account,
    AccountType,
    CashFlowCategory,
    ChartOfAccounts,
    JournalEntry,
    make_line,
)
from reference.accounting.ledger import Ledger

START_DATE = date(1980, 1, 1)
SPAN_YEARS = 50
SPAN_DAYS = SPAN_YEARS * 365
CASH_ACCOUNT_ID = "cash"
RETAINED_EARNINGS_ACCOUNT_ID = "retained_earnings"


def build_chart() -> ChartOfAccounts:
    """A fixed twelve-account chart spanning every AccountType and every
    CashFlowCategory, so a large synthetic ledger also exercises the
    investing/financing classification Phase 3/4 added to cash_flow.py.
    """
    chart = ChartOfAccounts()
    chart.add(Account(id=CASH_ACCOUNT_ID, name="Cash", type=AccountType.ASSET))
    chart.add(Account(id="ar", name="Accounts Receivable", type=AccountType.ASSET))
    chart.add(Account(id="inventory", name="Inventory", type=AccountType.ASSET))
    chart.add(
        Account(
            id="fixed_assets",
            name="Fixed Assets",
            type=AccountType.ASSET,
            cash_flow_category=CashFlowCategory.INVESTING,
        )
    )
    chart.add(Account(id="ap", name="Accounts Payable", type=AccountType.LIABILITY))
    chart.add(
        Account(
            id="loan_payable",
            name="Loan Payable",
            type=AccountType.LIABILITY,
            cash_flow_category=CashFlowCategory.FINANCING,
        )
    )
    chart.add(Account(id="equity", name="Owner's Equity", type=AccountType.EQUITY))
    chart.add(Account(id="retained_earnings", name="Retained Earnings", type=AccountType.EQUITY))
    chart.add(Account(id="revenue", name="Revenue", type=AccountType.REVENUE))
    chart.add(Account(id="cogs", name="Cost of Goods Sold", type=AccountType.EXPENSE))
    chart.add(Account(id="operating_expense", name="Operating Expense", type=AccountType.EXPENSE))
    chart.add(Account(id="interest_expense", name="Interest Expense", type=AccountType.EXPENSE))
    return chart


def build_synthetic_ledger(num_transactions: int, seed: int = 0) -> tuple[ChartOfAccounts, Ledger]:
    """A fully posted ledger of `num_transactions` balanced two-line
    entries, deterministic for a given (num_transactions, seed) pair --
    same account population and amounts every time, per docs/plan.md
    section 2.3.

    Entries are packed `ceil(num_transactions / SPAN_DAYS)` per day (one
    per day when there are fewer transactions than SPAN_DAYS) so the date
    sequence is always non-decreasing in posting order -- the last-posted
    entry is always the chronologically last one, however many
    transactions are requested. Every full calendar year before the
    final (necessarily partial) year is then closed into
    RETAINED_EARNINGS_ACCOUNT_ID via reference/accounting/closing.py, the
    same way every real scenario's runner/reference_runner.py does --
    without this, a multi-year ledger's balance sheet would fail the
    accounting equation, since balance_sheet.py only ever recognizes the
    *current* fiscal year's unclosed revenue/expense activity as equity
    (see docs/reference-model.md).
    """
    chart = build_chart()
    account_ids = list(chart.accounts.keys())
    ledger = Ledger(chart=chart)
    rng = random.Random(seed)

    entries_per_day = max(1, -(-num_transactions // SPAN_DAYS))  # ceil division
    for i in range(num_transactions):
        debit_account, credit_account = rng.sample(account_ids, 2)
        cents = rng.randint(1, 500_000)
        amount = Decimal(cents) / Decimal(100)
        day_index = min(i // entries_per_day, SPAN_DAYS - 1)
        entry_date = START_DATE + timedelta(days=day_index)
        ledger.post(
            JournalEntry(
                id=f"synthetic-{i}",
                date=entry_date,
                lines=(
                    make_line(debit_account, debit=str(amount)),
                    make_line(credit_account, credit=str(amount)),
                ),
            )
        )

    if ledger.entries:
        final_year = ledger.entries[-1].date.year
        for year in range(START_DATE.year, final_year):
            closing.close_period(
                ledger,
                chart,
                period_start=date(year, 1, 1),
                period_end=date(year, 12, 31),
                retained_earnings_account_id=RETAINED_EARNINGS_ACCOUNT_ID,
                entry_id=f"synthetic-closing-{year}",
            )

    return chart, ledger


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    built_chart, built_ledger = build_synthetic_ledger(n)
    print(
        f"Built a synthetic ledger with {len(built_ledger.entries)} entries across {len(built_chart.accounts)} accounts"
    )
    print(f"Spanning {built_ledger.entries[0].date} .. {max(e.date for e in built_ledger.entries)}")
