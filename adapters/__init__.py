"""The narrow adapter contract used to test a real accounting engine.

See docs/plan.md section 11. A concrete adapter (adapters/saldima,
adapters/gnucash_xml, ...) implements this interface against a real system
and returns normalized data in the comparison schema
(schemas/financial-statement.schema.json, schemas/schedule.schema.json). An
adapter must never calculate expected results itself.
"""

from __future__ import annotations

from typing import Any, Protocol


class AccountingSystemAdapter(Protocol):
    def create_book(self, scenario: dict[str, Any]) -> str:
        """Create a book for the scenario and return a book id."""
        ...

    def apply_event(self, book_id: str, event: dict[str, Any]) -> None: ...

    def run_adjustments(self, book_id: str, period: str) -> None: ...

    def get_journal_entries(self, book_id: str, period: str) -> list[dict[str, Any]]: ...

    def get_trial_balance(self, book_id: str, period: str) -> dict[str, Any]: ...

    def get_financial_statements(self, book_id: str, period: str) -> dict[str, dict[str, Any]]: ...

    def get_schedules(self, book_id: str, period: str) -> dict[str, Any]: ...

    def export_book(self, book_id: str) -> bytes: ...
