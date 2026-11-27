"""`SaldimaAdapter` -- the first real `AccountingSystemAdapter`
implementation (`adapters/__init__.py`) driving an actual Saldima
engine, via `adapters/saldima/bridge.py`'s subprocess transport to
`pnpm accounting-bridge` in the sibling `saldima` repository.

Unavailable unless `bridge.is_available()` -- see
`docs/accounting-policy.md`'s "Saldima bridge" section for the
`SALDIMA_REPO_PATH` gating this repo's CI relies on.

Like `adapters/gnucash_xml/adapter.py`, `create_book` builds the full
ledger up front (via the unchanged `runner/scenario_runner.build_ledger`
and `runner/reference_runner.apply_closing_entries`) and replays every
resulting entry into the real engine -- `apply_event`/`run_adjustments`
are documented no-ops for the identical, honest reason: `packages/
gnucash`'s bridge has no concept of incrementally applying one business
event or of a closing entry, only of posted transactions. This isn't a
stand-in for Saldima deriving entries itself; it's testing whether the
*real engine's own ledger/reporting arithmetic* agrees with ours, given
the same postings.

Scope boundary (see docs/accounting-policy.md): the bridge's
`balanceSheet`/`incomeStatement` return aggregate totals only, not
per-account lines (`packages/gnucash`'s reporting is still minimal) --
`get_financial_statements` reflects that honestly (`total_assets` etc.,
not per-account), rather than forcing a shape the real engine doesn't
produce. `trial_balance` *is* per-account, and is translated back to
our account ids in full.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from adapters.gnucash_xml import xml_format
from adapters.saldima.bridge import SaldimaBridge, from_wire_money, to_wire_money
from reference.accounting.journal import Account, AccountType, ChartOfAccounts, JournalEntry
from reference.accounting.ledger import Ledger
from runner import period as period_mod
from runner import reference_runner
from runner.scenario_runner import LoadedScenario, build_ledger

_ACCOUNT_TYPE_TO_SALDIMA = {
    AccountType.ASSET: "ASSET",
    AccountType.LIABILITY: "LIABILITY",
    AccountType.EQUITY: "EQUITY",
    AccountType.REVENUE: "INCOME",
    AccountType.EXPENSE: "EXPENSE",
}
"""Deliberately coarse: doesn't distinguish Saldima's BANK/CASH/CREDIT/
RECEIVABLE/PAYABLE subtypes, since our own AccountType has no equivalent
granularity -- see docs/accounting-policy.md."""


def _account_to_wire(account: Account) -> dict[str, Any]:
    wire: dict[str, Any] = {
        "id": xml_format.account_guid(account.id),
        "name": account.name,
        "type": _ACCOUNT_TYPE_TO_SALDIMA[account.type],
    }
    if account.parent_id is not None:
        wire["parentId"] = xml_format.account_guid(account.parent_id)
    return wire


def _entry_to_wire(entry: JournalEntry) -> dict[str, Any]:
    return {
        "id": xml_format.entry_guid(entry.id),
        "date": entry.date.isoformat(),
        # Saldima requires a non-empty description; our memo is often "".
        "description": entry.memo or entry.id,
        "splits": [
            {
                "accountId": xml_format.account_guid(line.account_id),
                "value": to_wire_money(line.debit - line.credit),
            }
            for line in entry.lines
        ],
    }


@dataclass
class _Book:
    scenario_id: str
    chart: ChartOfAccounts
    ledger: Ledger
    bridge: SaldimaBridge
    guid_to_account_id: dict[str, str] = field(default_factory=dict)


class SaldimaAdapter:
    def __init__(self, repo_path: Path) -> None:
        self._repo_path = repo_path
        self._books: dict[str, _Book] = {}
        self._next_id = 0

    def create_book(self, scenario: dict[str, Any]) -> str:
        chart, ledger = build_ledger(scenario)
        loaded = LoadedScenario(raw=scenario, chart=chart, ledger=ledger)
        reference_runner.apply_closing_entries(loaded)

        bridge = SaldimaBridge(self._repo_path)
        guid_to_account_id = {xml_format.account_guid(aid): aid for aid in chart.accounts}
        bridge.reset([_account_to_wire(account) for account in chart.accounts.values()])
        for entry in ledger.entries:
            bridge.post(_entry_to_wire(entry))

        book_id = f"book-{self._next_id}"
        self._next_id += 1
        self._books[book_id] = _Book(
            scenario_id=loaded.id,
            chart=chart,
            ledger=ledger,
            bridge=bridge,
            guid_to_account_id=guid_to_account_id,
        )
        return book_id

    def apply_event(self, book_id: str, event: dict[str, Any]) -> None:
        pass

    def run_adjustments(self, book_id: str, period: str) -> None:
        pass

    def get_journal_entries(self, book_id: str, period: str) -> list[dict[str, Any]]:
        book = self._books[book_id]
        start, end = period_mod.parse_period(period)
        return [
            {
                "id": entry.id,
                "date": entry.date.isoformat(),
                "memo": entry.memo,
                "is_closing": entry.is_closing,
                "lines": [
                    {
                        "account_id": line.account_id,
                        "debit": str(line.debit),
                        "credit": str(line.credit),
                    }
                    for line in entry.lines
                ],
            }
            for entry in book.ledger.entries_between(start, end)
        ]

    def get_trial_balance(self, book_id: str, period: str) -> dict[str, Any]:
        return self.get_financial_statements(book_id, period)["trial_balance"]

    def get_financial_statements(self, book_id: str, period: str) -> dict[str, dict[str, Any]]:
        book = self._books[book_id]
        start, end = period_mod.parse_period(period)

        tb_result = book.bridge.trial_balance(end.isoformat())
        bs_result = book.bridge.balance_sheet(end.isoformat())
        is_result = book.bridge.income_statement(start.isoformat(), end.isoformat())

        # packages/gnucash's own trialBalance omits any account whose
        # balance is exactly zero (ledger.ts: `if (equalsMoney(balance,
        # ZERO)) continue`) -- a presentation convention, not a
        # discrepancy. Our own trial_balance.generate always includes
        # every chart account, so fill in the zero lines it left out to
        # match that convention honestly (the missing accounts really
        # are zero; Saldima just doesn't say so).
        trial_balance_lines = {
            account_id: {"debit": "0.00", "credit": "0.00"} for account_id in book.chart.accounts
        }
        for row in tb_result["rows"]:
            account_id = book.guid_to_account_id[row["accountId"]]
            trial_balance_lines[account_id] = {
                "debit": str(from_wire_money(row["debit"])),
                "credit": str(from_wire_money(row["credit"])),
            }

        return {
            "trial_balance": {
                "scenario_id": book.scenario_id,
                "period": period,
                "statement_type": "trial_balance",
                "lines": trial_balance_lines,
            },
            # Aggregate-only: packages/gnucash's balanceSheet/incomeStatement
            # don't return per-account lines yet -- see this module's docstring.
            "balance_sheet": {
                "scenario_id": book.scenario_id,
                "period": period,
                "statement_type": "balance_sheet",
                "lines": {
                    "total_assets": {"ending_balance": str(from_wire_money(bs_result["assets"]))},
                    "total_liabilities": {
                        "ending_balance": str(from_wire_money(bs_result["liabilities"]))
                    },
                    "total_equity": {"ending_balance": str(from_wire_money(bs_result["equity"]))},
                    "retained_earnings": {
                        "ending_balance": str(from_wire_money(bs_result["retainedEarnings"]))
                    },
                },
            },
            "income_statement": {
                "scenario_id": book.scenario_id,
                "period": period,
                "statement_type": "income_statement",
                "lines": {
                    "total_revenue": {"ending_balance": str(from_wire_money(is_result["revenue"]))},
                    "total_expenses": {
                        "ending_balance": str(from_wire_money(is_result["expenses"]))
                    },
                    "net_income": {"ending_balance": str(from_wire_money(is_result["netIncome"]))},
                },
            },
        }

    def get_schedules(self, book_id: str, period: str) -> dict[str, Any]:
        return {}

    def export_book(self, book_id: str) -> bytes:
        """Our own export of what we posted to Saldima -- reuses the
        already-tested `adapters/gnucash_xml` export, since the bridge
        itself has no export op yet. Not something Saldima produced.
        """
        book = self._books[book_id]
        return xml_format.export_book(book.chart, list(book.ledger.entries))

    def close(self) -> None:
        """Adapter-specific lifecycle cleanup, not part of
        `AccountingSystemAdapter` -- terminates every book's live
        subprocess. Callers (tests) must call this when done.
        """
        for book in self._books.values():
            book.bridge.close()
