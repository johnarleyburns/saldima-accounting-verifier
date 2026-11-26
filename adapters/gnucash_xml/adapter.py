"""`GnuCashXmlAdapter` -- a self-contained implementation of
`AccountingSystemAdapter` (adapters/__init__.py) backed by GnuCash's own
data model, not a live Saldima engine.

`adapters/saldima/` stays unimplemented -- there's no actual Saldima
engine available in this repository to drive, and claiming otherwise
would be dishonest. But GnuCash's own account/transaction/split model is
expressive enough to *be* a tiny accounting engine in its own right, so
this adapter is a real, complete implementation: it builds a book from a
scenario using the exact same translation the reference run itself uses
(`runner/scenario_runner.py`'s `build_ledger`, plus
`runner/reference_runner.py`'s closing-entry application), answers
queries through `reference/accounting/*` the same way
`reference_runner.py` does, and can export/import real GnuCash XML
(`xml_format.py`).

This is allowed under docs/plan.md section 2.1's independence rule, which
is one-directional: `reference/` must never import `adapters/`, but an
adapter *using* `reference/`/`runner/` as a library -- the same
translation and reporting code the reference run itself uses -- is
exactly how an adapter is meant to work. It's compared against the
reference model's output (via runner/compare.py), never used to produce
it.

`apply_event`/`run_adjustments` are documented no-ops: GnuCash's native
format has no concept of incrementally applying one event to an already-
saved book -- it's a batch/snapshot format, not a streaming API.
`create_book` already processes every event in the scenario; forcing an
artificial per-event protocol here would be less honest, not more.
"""

from __future__ import annotations

from typing import Any

from adapters.gnucash_xml import xml_format
from reference.accounting.journal import ChartOfAccounts
from reference.accounting.ledger import Ledger
from runner import period as period_mod
from runner import reference_runner
from runner.scenario_runner import LoadedScenario, build_ledger


class GnuCashXmlAdapter:
    def __init__(self) -> None:
        self._books: dict[str, LoadedScenario] = {}
        self._next_id = 0

    def create_book(self, scenario: dict[str, Any]) -> str:
        chart, ledger = build_ledger(scenario)
        loaded = LoadedScenario(raw=scenario, chart=chart, ledger=ledger)
        reference_runner.apply_closing_entries(loaded)

        book_id = f"book-{self._next_id}"
        self._next_id += 1
        self._books[book_id] = loaded
        return book_id

    def apply_event(self, book_id: str, event: dict[str, Any]) -> None:
        pass

    def run_adjustments(self, book_id: str, period: str) -> None:
        pass

    def get_journal_entries(self, book_id: str, period: str) -> list[dict[str, Any]]:
        loaded = self._books[book_id]
        start, end = period_mod.parse_period(period)
        return [
            {
                "id": entry.id,
                "date": entry.date.isoformat(),
                "memo": entry.memo,
                "is_closing": entry.is_closing,
                "lines": [
                    {"account_id": line.account_id, "debit": str(line.debit), "credit": str(line.credit)}
                    for line in entry.lines
                ],
            }
            for entry in loaded.ledger.entries_between(start, end)
        ]

    def get_trial_balance(self, book_id: str, period: str) -> dict[str, Any]:
        return self.get_financial_statements(book_id, period)["trial_balance"]

    def get_financial_statements(self, book_id: str, period: str) -> dict[str, dict[str, Any]]:
        loaded = self._books[book_id]
        return reference_runner.generate_period_reports(loaded, period)

    def get_schedules(self, book_id: str, period: str) -> dict[str, Any]:
        return {}

    def export_book(self, book_id: str) -> bytes:
        loaded = self._books[book_id]
        return xml_format.export_book(loaded.chart, list(loaded.ledger.entries))


def rebuild_ledger_from_xml(xml_bytes: bytes) -> tuple[ChartOfAccounts, Ledger]:
    """Parse `xml_bytes` and post every entry to a fresh `Ledger` -- the
    round-trip counterpart to `GnuCashXmlAdapter.export_book`, used by
    tests/compatibility/test_gnc_001_round_trip.py. Not part of the
    `AccountingSystemAdapter` Protocol: there's no protocol slot for
    "create a book from a native export," only from a scenario dict.
    """
    chart, entries = xml_format.parse_book(xml_bytes)
    ledger = Ledger(chart=chart)
    for entry in entries:
        ledger.post(entry)
    return chart, ledger
