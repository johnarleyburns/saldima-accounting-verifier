"""Loads a scenario YAML file, validates it, and builds a posted Ledger.

Phase 1 implements a single event type, `manual_journal_entry`: the
scenario author supplies explicit debit/credit lines directly. Phase 2 adds
`customer_contract_payment`, the first event type where the reference model
itself must derive journal entries from a declared accounting policy
(straight-line or point-in-time revenue recognition) rather than just
posting author-supplied numbers -- see docs/accounting-policy.md's "Event
model: Phase 1 vs Phase 2" for why accruals/prepayments stayed on
`manual_journal_entry` while revenue recognition did not, and
docs/plan.md section 2.2 for the original design intent.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from reference.accounting.journal import (
    Account,
    AccountingError,
    AccountType,
    ChartOfAccounts,
    JournalEntry,
    make_line,
)
from reference.accounting.ledger import Ledger
from reference.accounting.rounding import ZERO, money
from reference.schedules import deferred_revenue

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"


@dataclass
class LoadedScenario:
    raw: dict[str, Any]
    chart: ChartOfAccounts
    ledger: Ledger

    @property
    def id(self) -> str:
        return str(self.raw["id"])

    @property
    def start_date(self) -> date:
        return date.fromisoformat(self.raw["start_date"])

    @property
    def end_date(self) -> date:
        return date.fromisoformat(self.raw["end_date"])

    @property
    def currency(self) -> str:
        return str(self.raw["accounting"]["currency"])

    @property
    def cash_account_ids(self) -> set[str]:
        return set(self.raw.get("cash_accounts", []))

    @property
    def report_periods(self) -> list[str]:
        return [r["period"] for r in self.raw["expected"]["reports"]]


def _load_schema(name: str) -> dict[str, Any]:
    with open(SCHEMAS_DIR / name) as f:
        return json.load(f)  # type: ignore[no-any-return]


def validate_scenario_document(document: dict[str, Any]) -> None:
    schema = _load_schema("scenario.schema.json")
    # Every schema in schemas/ declares a remote-looking "$id" for
    # documentation purposes, but $ref resolution must never hit the
    # network: pre-populate the resolver's store with every local schema,
    # keyed by both its $id and its bare filename, so refs resolve locally
    # regardless of which URI they're written against.
    store: dict[str, Any] = {}
    for schema_file in SCHEMAS_DIR.glob("*.schema.json"):
        loaded = _load_schema(schema_file.name)
        store[schema_file.name] = loaded
        if "$id" in loaded:
            store[loaded["$id"]] = loaded
    # jsonschema.RefResolver is deprecated in favor of the `referencing`
    # library as of jsonschema 4.18, but is still the simplest way to force
    # fully-local $ref resolution; revisit if it's actually removed.
    resolver = jsonschema.validators.RefResolver(base_uri=schema["$id"], referrer=schema, store=store)
    jsonschema.validate(instance=document, schema=schema, resolver=resolver)


def _stringify_dates(value: Any) -> Any:
    """PyYAML auto-parses ISO date-looking scalars into datetime.date objects.
    Scenario dates are meant to be plain strings throughout this codebase
    (date.fromisoformat is called on them explicitly), so normalize back.
    """
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _stringify_dates(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_stringify_dates(v) for v in value]
    return value


def load_scenario(path: Path) -> LoadedScenario:
    with open(path) as f:
        document = _stringify_dates(yaml.safe_load(f))
    validate_scenario_document(document)
    raw = document["scenario"]

    chart = ChartOfAccounts()
    for acct in raw["accounts"]:
        chart.add(
            Account(
                id=acct["id"],
                name=acct["name"],
                type=AccountType(acct["type"]),
                parent_id=acct.get("parent_id"),
            )
        )

    ledger = Ledger(chart=chart)

    opening_balances = raw.get("opening_balances", [])
    if opening_balances:
        # All opening_balances lines for a scenario are posted together as a
        # single journal entry, so the scenario author must supply a
        # balancing set of debit/credit lines (e.g. cash debited, opening
        # equity credited).
        ledger.post(_balance_opening_entries(opening_balances, raw["start_date"]))

    seen_event_ids: set[str] = set()
    for event in raw["events"]:
        if event["id"] in seen_event_ids:
            raise AccountingError(f"Duplicate event id: {event['id']!r}")
        seen_event_ids.add(event["id"])

        if event["type"] == "manual_journal_entry":
            lines = tuple(
                make_line(line["account_id"], debit=line.get("debit", "0.00"), credit=line.get("credit", "0.00"))
                for line in event["lines"]
            )
            ledger.post(
                JournalEntry(
                    id=f"event-{event['id']}",
                    date=date.fromisoformat(event["date"]),
                    lines=lines,
                    source_event_id=event["id"],
                )
            )
        elif event["type"] == "customer_contract_payment":
            for entry in _translate_customer_contract_payment(event):
                ledger.post(entry)
        else:
            raise NotImplementedError(
                f"Event type {event['type']!r} is not supported "
                "(supported: 'manual_journal_entry', 'customer_contract_payment')"
            )

    return LoadedScenario(raw=raw, chart=chart, ledger=ledger)


def _balance_opening_entries(opening_balances: list[dict[str, Any]], start_date: str) -> JournalEntry:
    lines = tuple(
        make_line(ob["account_id"], debit=ob.get("debit", "0.00"), credit=ob.get("credit", "0.00"))
        for ob in opening_balances
    )
    return JournalEntry(id="opening-balances", date=date.fromisoformat(start_date), lines=lines, memo="Opening balances")


def _translate_customer_contract_payment(event: dict[str, Any]) -> list[JournalEntry]:
    """Translate one `customer_contract_payment` event into its journal entries.

    This is the reference model's own application of a revenue-recognition
    policy (see docs/accounting-policy.md), not just a restatement of
    author-supplied numbers: it derives the straight-line monthly schedule
    (via reference/schedules/deferred_revenue.py) and the point-in-time
    recognition entries for each performance obligation.
    """
    event_id = event["id"]
    event_date = date.fromisoformat(event["date"])
    cash_account_id = event["cash_account_id"]
    deferred_revenue_account_id = event["deferred_revenue_account_id"]
    obligations = event["obligations"]

    total = sum((money(ob["amount"]) for ob in obligations), ZERO)
    entries = [
        JournalEntry(
            id=f"event-{event_id}-payment",
            date=event_date,
            lines=(
                make_line(cash_account_id, debit=str(total)),
                make_line(deferred_revenue_account_id, credit=str(total)),
            ),
            source_event_id=event_id,
        )
    ]

    for obligation in obligations:
        obligation_id = obligation["id"]
        amount = money(obligation["amount"])
        revenue_account_id = obligation["revenue_account_id"]
        method = obligation["recognition_method"]

        if method == "point_in_time":
            recognition_date = date.fromisoformat(obligation["recognition_date"])
            entries.append(
                JournalEntry(
                    id=f"event-{event_id}-{obligation_id}-recognition",
                    date=recognition_date,
                    lines=(
                        make_line(deferred_revenue_account_id, debit=str(amount)),
                        make_line(revenue_account_id, credit=str(amount)),
                    ),
                    source_event_id=event_id,
                )
            )
        elif method == "straight_line":
            service_start = date.fromisoformat(obligation["service_start"])
            service_end = date.fromisoformat(obligation["service_end"])
            schedule = deferred_revenue.build_straight_line_schedule(amount, service_start, service_end)
            for period_end, period_amount in schedule:
                entries.append(
                    JournalEntry(
                        id=f"event-{event_id}-{obligation_id}-recognition-{period_end.isoformat()}",
                        date=period_end,
                        lines=(
                            make_line(deferred_revenue_account_id, debit=str(period_amount)),
                            make_line(revenue_account_id, credit=str(period_amount)),
                        ),
                        source_event_id=event_id,
                    )
                )
        else:
            raise AccountingError(
                f"Unknown recognition_method {method!r} for obligation {obligation_id!r} "
                f"on event {event_id!r}"
            )

    return entries
