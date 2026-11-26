"""Chart of accounts, journal entries, and double-entry balance enforcement.

This module is the independent reference implementation of core double-entry
bookkeeping described in docs/plan.md section 7.1. It deliberately does not
import, call, or depend on any Saldima production code — see docs/plan.md
section 2.1 ("the production accounting engine must never be the authority
for its own correctness").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum

from reference.accounting.rounding import ZERO, money


class AccountType(str, Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


class CashFlowCategory(str, Enum):
    """Which section of the statement of cash flows an account's balance
    changes belong in (reference/accounting/cash_flow.py). Defaults to
    OPERATING, which is the only category Phase 1/2 ever needed -- see
    docs/reference-model.md's "Phase 3 adds investing/financing
    classification" section for why Phase 3 (fixed assets) is the first
    phase to need the other two.
    """

    OPERATING = "operating"
    INVESTING = "investing"
    FINANCING = "financing"


# Normal balance side for each account type: debit-normal types increase with
# debits, credit-normal types increase with credits.
DEBIT_NORMAL = {AccountType.ASSET, AccountType.EXPENSE}
CREDIT_NORMAL = {AccountType.LIABILITY, AccountType.EQUITY, AccountType.REVENUE}

FLOW_TYPES = {AccountType.REVENUE, AccountType.EXPENSE}
BALANCE_TYPES = {AccountType.ASSET, AccountType.LIABILITY, AccountType.EQUITY}


class AccountingError(ValueError):
    """Raised when a scenario or engine output violates a core accounting rule."""


@dataclass(frozen=True)
class Account:
    id: str
    name: str
    type: AccountType
    parent_id: str | None = None
    cash_flow_category: CashFlowCategory = CashFlowCategory.OPERATING

    def is_debit_normal(self) -> bool:
        return self.type in DEBIT_NORMAL


@dataclass(frozen=True)
class JournalLine:
    account_id: str
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    description: str = ""

    def __post_init__(self) -> None:
        if self.debit < 0 or self.credit < 0:
            raise AccountingError(f"Journal line amounts must be non-negative: {self}")
        if self.debit > 0 and self.credit > 0:
            raise AccountingError(
                f"Journal line for account {self.account_id!r} has both a debit and a "
                "credit; a line must be one-sided."
            )


@dataclass(frozen=True)
class JournalEntry:
    id: str
    date: date
    lines: tuple[JournalLine, ...]
    memo: str = ""
    source_event_id: str | None = None
    is_closing: bool = False
    """True for period-end closing entries (see reference/accounting/closing.py).

    Closing entries are a bookkeeping mechanism, not business activity: a
    report of *period* revenue/expense activity (income_statement.py, and
    balance_sheet.py's unclosed-earnings calculation) must exclude them, or
    a report whose window ends exactly on a closing date would see revenue
    and expense zeroed out by the very entry that closed them. See
    Ledger.period_activity and docs/reference-model.md.
    """

    def __post_init__(self) -> None:
        if len(self.lines) < 2:
            raise AccountingError(
                f"Journal entry {self.id!r} must have at least two lines (got {len(self.lines)})"
            )
        total_debit = sum((line.debit for line in self.lines), ZERO)
        total_credit = sum((line.credit for line in self.lines), ZERO)
        if total_debit != total_credit:
            raise AccountingError(
                f"Journal entry {self.id!r} does not balance: "
                f"debits={total_debit} credits={total_credit}"
            )
        if total_debit == ZERO:
            raise AccountingError(f"Journal entry {self.id!r} has zero net effect")

    @property
    def total(self) -> Decimal:
        return sum((line.debit for line in self.lines), ZERO)


def make_line(account_id: str, debit: str = "0.00", credit: str = "0.00", description: str = "") -> JournalLine:
    return JournalLine(account_id=account_id, debit=money(debit), credit=money(credit), description=description)


@dataclass
class ChartOfAccounts:
    accounts: dict[str, Account] = field(default_factory=dict)

    def add(self, account: Account) -> None:
        if account.id in self.accounts:
            raise AccountingError(f"Duplicate account id: {account.id!r}")
        if account.parent_id is not None and account.parent_id not in self.accounts:
            raise AccountingError(
                f"Account {account.id!r} references unknown parent {account.parent_id!r}"
            )
        self.accounts[account.id] = account

    def get(self, account_id: str) -> Account:
        try:
            return self.accounts[account_id]
        except KeyError:
            raise AccountingError(f"Unknown account id: {account_id!r}") from None

    def __contains__(self, account_id: str) -> bool:
        return account_id in self.accounts
