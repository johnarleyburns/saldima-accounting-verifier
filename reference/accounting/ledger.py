"""A posted, append-only ledger over a chart of accounts.

Implements core invariants from docs/plan.md section 13:
  1. Every posted journal entry balances (enforced by JournalEntry itself).
  9. Every split references a valid account.
  12. Period closing does not change historical transaction amounts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from reference.accounting.journal import (
    DEBIT_NORMAL,
    Account,
    AccountingError,
    AccountType,
    ChartOfAccounts,
    JournalEntry,
)
from reference.accounting.rounding import ZERO


@dataclass
class Ledger:
    chart: ChartOfAccounts
    entries: list[JournalEntry] = field(default_factory=list)
    closed_through: date | None = None
    _entry_ids: set[str] = field(default_factory=set, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Mirrors whatever `entries` the Ledger was constructed with (empty
        # in every real caller today, which only ever populates it via
        # `post()`) -- see the duplicate-id check below.
        self._entry_ids = {entry.id for entry in self.entries}

    def post(self, entry: JournalEntry) -> None:
        # A set lookup here, not a linear scan over `self.entries`, is what
        # keeps posting `n` entries O(n) overall instead of O(n^2) -- see
        # docs/plan.md section 15 / docs/reference-model.md's performance
        # section, which is what surfaced this (scripts/
        # run_performance_benchmark.py at 100,000+ transactions never
        # finished before this fix).
        if entry.id in self._entry_ids:
            raise AccountingError(f"Duplicate journal entry id: {entry.id!r}")
        for line in entry.lines:
            if line.account_id not in self.chart:
                raise AccountingError(
                    f"Journal entry {entry.id!r} references unknown account "
                    f"{line.account_id!r}"
                )
        if self.closed_through is not None and entry.date <= self.closed_through:
            raise AccountingError(
                f"Journal entry {entry.id!r} dated {entry.date} is posted into a "
                f"closed period (closed through {self.closed_through})"
            )
        self.entries.append(entry)
        self._entry_ids.add(entry.id)

    def close_period(self, through: date) -> None:
        """Lock all periods up to and including `through` against new postings.

        This models invariant 12 (closing does not retroactively change
        historical transaction amounts) by only ever narrowing what can be
        posted — it never rewrites `self.entries`.
        """
        if self.closed_through is not None and through < self.closed_through:
            raise AccountingError("Cannot move closed_through backwards")
        self.closed_through = through

    def entries_through(self, as_of: date) -> list[JournalEntry]:
        return [e for e in self.entries if e.date <= as_of]

    def entries_between(self, start: date, end: date) -> list[JournalEntry]:
        return [e for e in self.entries if start <= e.date <= end]

    def signed_balance(self, account: Account, debit_total: Decimal, credit_total: Decimal) -> Decimal:
        """Normal-balance-signed ending balance: positive means a normal balance."""
        if account.type in DEBIT_NORMAL:
            return debit_total - credit_total
        return credit_total - debit_total

    def balances_as_of(self, as_of: date, exclude_closing: bool = False) -> dict[str, dict[str, Decimal]]:
        """Per-account debit/credit totals and signed ending balance, inception-to-date.

        `exclude_closing=True` computes balances as if closing entries had
        never been posted. Used by cash_flow.py, which must stay blind to
        closing entries (a bookkeeping reclassification with zero cash
        impact) so its net-income and adjustment figures are computed on
        the same, consistent basis -- see docs/reference-model.md.
        """
        totals: dict[str, dict[str, Decimal]] = {
            account_id: {"debit": ZERO, "credit": ZERO} for account_id in self.chart.accounts
        }
        for entry in self.entries_through(as_of):
            if exclude_closing and entry.is_closing:
                continue
            for line in entry.lines:
                totals[line.account_id]["debit"] += line.debit
                totals[line.account_id]["credit"] += line.credit
        result: dict[str, dict[str, Decimal]] = {}
        for account_id, account in self.chart.accounts.items():
            debit_total = totals[account_id]["debit"]
            credit_total = totals[account_id]["credit"]
            result[account_id] = {
                "debit": debit_total,
                "credit": credit_total,
                "ending_balance": self.signed_balance(account, debit_total, credit_total),
            }
        return result

    def period_activity(self, start: date, end: date) -> dict[str, dict[str, Decimal]]:
        """Per-account debit/credit totals for business activity dated within [start, end].

        Excludes closing entries (see JournalEntry.is_closing) -- this is a
        report of what happened in the business during the period, not a
        dump of every posted line.
        """
        totals: dict[str, dict[str, Decimal]] = {
            account_id: {"debit": ZERO, "credit": ZERO} for account_id in self.chart.accounts
        }
        for entry in self.entries_between(start, end):
            if entry.is_closing:
                continue
            for line in entry.lines:
                totals[line.account_id]["debit"] += line.debit
                totals[line.account_id]["credit"] += line.credit
        return totals

    def last_closing_date_through(self, as_of: date) -> date | None:
        closing_dates = [e.date for e in self.entries_through(as_of) if e.is_closing]
        return max(closing_dates) if closing_dates else None

    def accounts_of_type(self, *types: AccountType) -> list[Account]:
        return [a for a in self.chart.accounts.values() if a.type in types]
