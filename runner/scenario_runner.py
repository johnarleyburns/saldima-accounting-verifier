"""Loads a scenario YAML file, validates it, and builds a posted Ledger.

Phase 1 implements a single event type, `manual_journal_entry`: the
scenario author supplies explicit debit/credit lines directly. Phase 2 adds
`customer_contract_payment`. Phase 3 adds `fixed_asset_purchase`,
`fixed_asset_disposal`, `inventory_purchase`, and `inventory_sale` -- each
a case where the reference model itself must derive journal entries from a
declared accounting policy (straight-line depreciation, disposal gain/
loss, FIFO costing) rather than just posting author-supplied numbers. See
docs/accounting-policy.md's "Event model: Phase 1 vs Phase 2" and its
Phase 3 addendum, and docs/plan.md section 2.2 for the original design
intent.
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
    CashFlowCategory,
    ChartOfAccounts,
    JournalEntry,
    make_line,
)
from reference.accounting.ledger import Ledger
from reference.accounting.rounding import ZERO, money
from reference.schedules import deferred_revenue, depreciation
from reference.schedules import inventory as inventory_mod

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
                cash_flow_category=CashFlowCategory(acct.get("cash_flow_category", "operating")),
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

    # fixed_asset_purchase must know whether a later fixed_asset_disposal
    # cuts its depreciation schedule short, and fixed_asset_disposal must
    # know its matching purchase's cost/salvage/useful-life to compute book
    # value -- both are scanned up front, keyed by the shared asset_id
    # (see docs/accounting-policy.md).
    disposal_dates_by_asset: dict[str, date] = {
        event["asset_id"]: date.fromisoformat(event["date"])
        for event in raw["events"]
        if event["type"] == "fixed_asset_disposal"
    }
    purchase_events_by_asset: dict[str, dict[str, Any]] = {
        event["asset_id"]: event for event in raw["events"] if event["type"] == "fixed_asset_purchase"
    }
    # inventory_sale's FIFO costing needs the running list of open lots for
    # its inventory account, built up as inventory_purchase events are
    # processed -- this is state carried across events (in file order,
    # which must be chronological per inventory account), unlike every
    # other event type's single-event translation.
    fifo_lots_by_account: dict[str, list[inventory_mod.Lot]] = {}

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
        elif event["type"] == "fixed_asset_purchase":
            for entry in _translate_fixed_asset_purchase(event, disposal_dates_by_asset):
                ledger.post(entry)
        elif event["type"] == "fixed_asset_disposal":
            ledger.post(_translate_fixed_asset_disposal(event, purchase_events_by_asset))
        elif event["type"] == "inventory_purchase":
            ledger.post(_translate_inventory_purchase(event, fifo_lots_by_account))
        elif event["type"] == "inventory_sale":
            for entry in _translate_inventory_sale(event, fifo_lots_by_account):
                ledger.post(entry)
        else:
            raise NotImplementedError(
                f"Event type {event['type']!r} is not supported "
                "(supported: 'manual_journal_entry', 'customer_contract_payment', "
                "'fixed_asset_purchase', 'fixed_asset_disposal', 'inventory_purchase', 'inventory_sale')"
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


def _translate_fixed_asset_purchase(
    event: dict[str, Any], disposal_dates_by_asset: dict[str, date]
) -> list[JournalEntry]:
    """Translate one `fixed_asset_purchase` event into its journal entries.

    Derives the straight-line depreciation schedule
    (reference/schedules/depreciation.py) from the declared cost/salvage/
    useful-life policy, truncated at a later `fixed_asset_disposal` event
    for the same `asset_id`, if any -- see docs/accounting-policy.md.
    """
    event_id = event["id"]
    asset_id = event["asset_id"]
    purchase_date = date.fromisoformat(event["date"])
    asset_account_id = event["asset_account_id"]
    accumulated_depreciation_account_id = event["accumulated_depreciation_account_id"]
    depreciation_expense_account_id = event["depreciation_expense_account_id"]
    cash_account_id = event["cash_account_id"]
    cost = money(event["cost"])
    salvage_value = money(event["salvage_value"])
    useful_life_months = int(event["useful_life_months"])

    entries = [
        JournalEntry(
            id=f"event-{event_id}-purchase",
            date=purchase_date,
            lines=(
                make_line(asset_account_id, debit=str(cost)),
                make_line(cash_account_id, credit=str(cost)),
            ),
            source_event_id=event_id,
        )
    ]

    schedule = depreciation.build_straight_line_schedule(
        cost,
        salvage_value,
        purchase_date,
        useful_life_months,
        through=disposal_dates_by_asset.get(asset_id),
    )
    for period_end, period_amount in schedule:
        entries.append(
            JournalEntry(
                id=f"event-{event_id}-depreciation-{period_end.isoformat()}",
                date=period_end,
                lines=(
                    make_line(depreciation_expense_account_id, debit=str(period_amount)),
                    make_line(accumulated_depreciation_account_id, credit=str(period_amount)),
                ),
                source_event_id=event_id,
            )
        )

    return entries


def _translate_fixed_asset_disposal(
    event: dict[str, Any], purchase_events_by_asset: dict[str, dict[str, Any]]
) -> JournalEntry:
    """Translate one `fixed_asset_disposal` event into its journal entry.

    Computes accumulated depreciation and book value at the disposal date
    analytically, from the matching `fixed_asset_purchase` event's own
    declared cost/salvage/useful-life (looked up by `asset_id`; no ledger
    lookups needed) -- see docs/accounting-policy.md.
    """
    event_id = event["id"]
    asset_id = event["asset_id"]
    disposal_date = date.fromisoformat(event["date"])
    proceeds = money(event["proceeds"])
    cash_account_id = event["cash_account_id"]
    gain_account_id = event["gain_account_id"]
    loss_account_id = event["loss_account_id"]

    purchase_event = purchase_events_by_asset[asset_id]
    cost = money(purchase_event["cost"])
    salvage_value = money(purchase_event["salvage_value"])
    useful_life_months = int(purchase_event["useful_life_months"])
    purchase_date = date.fromisoformat(purchase_event["date"])
    asset_account_id = purchase_event["asset_account_id"]
    accumulated_depreciation_account_id = purchase_event["accumulated_depreciation_account_id"]

    schedule = depreciation.build_straight_line_schedule(
        cost, salvage_value, purchase_date, useful_life_months, through=disposal_date
    )
    accumulated_depreciation_at_disposal = sum((amount for _, amount in schedule), ZERO)
    gain_loss = depreciation.disposal_gain_loss(cost, accumulated_depreciation_at_disposal, proceeds)

    lines = [
        make_line(cash_account_id, debit=str(proceeds)),
        make_line(accumulated_depreciation_account_id, debit=str(accumulated_depreciation_at_disposal)),
        make_line(asset_account_id, credit=str(cost)),
    ]
    if gain_loss > ZERO:
        lines.append(make_line(gain_account_id, credit=str(gain_loss)))
    elif gain_loss < ZERO:
        lines.append(make_line(loss_account_id, debit=str(-gain_loss)))
    # gain_loss == ZERO: the three lines above already balance exactly, no plug needed.

    return JournalEntry(
        id=f"event-{event_id}-disposal",
        date=disposal_date,
        lines=tuple(lines),
        source_event_id=event_id,
    )


def _translate_inventory_purchase(
    event: dict[str, Any], fifo_lots_by_account: dict[str, list[inventory_mod.Lot]]
) -> JournalEntry:
    """Translate one `inventory_purchase` event into its journal entry, and
    record a new FIFO lot for later `inventory_sale` events on the same
    `inventory_account_id` -- see docs/accounting-policy.md.
    """
    event_id = event["id"]
    inventory_account_id = event["inventory_account_id"]
    cash_account_id = event["cash_account_id"]
    quantity = money(event["quantity"])
    unit_cost = money(event["unit_cost"])

    fifo_lots_by_account.setdefault(inventory_account_id, []).append(
        inventory_mod.Lot(quantity=quantity, unit_cost=unit_cost)
    )

    total_cost = quantity * unit_cost
    return JournalEntry(
        id=f"event-{event_id}",
        date=date.fromisoformat(event["date"]),
        lines=(
            make_line(inventory_account_id, debit=str(total_cost)),
            make_line(cash_account_id, credit=str(total_cost)),
        ),
        source_event_id=event_id,
    )


def _translate_inventory_sale(
    event: dict[str, Any], fifo_lots_by_account: dict[str, list[inventory_mod.Lot]]
) -> list[JournalEntry]:
    """Translate one `inventory_sale` event into its journal entries.

    The cost of goods sold is the one derived result here (the sale/COGS
    dollar totals are plain multiplication once quantities are known) --
    computed by consuming FIFO lots oldest-first
    (reference/schedules/inventory.py) from the running per-account lot
    list built up by prior `inventory_purchase` events in this scenario.
    """
    event_id = event["id"]
    event_date = date.fromisoformat(event["date"])
    inventory_account_id = event["inventory_account_id"]
    cogs_account_id = event["cogs_account_id"]
    revenue_account_id = event["revenue_account_id"]
    cash_account_id = event["cash_account_id"]
    quantity = money(event["quantity"])
    unit_price = money(event["unit_price"])

    lots = fifo_lots_by_account.get(inventory_account_id, [])
    cost_of_goods_sold, remaining_lots = inventory_mod.consume_fifo(lots, quantity)
    fifo_lots_by_account[inventory_account_id] = remaining_lots

    total_revenue = quantity * unit_price

    return [
        JournalEntry(
            id=f"event-{event_id}-sale",
            date=event_date,
            lines=(
                make_line(cash_account_id, debit=str(total_revenue)),
                make_line(revenue_account_id, credit=str(total_revenue)),
            ),
            source_event_id=event_id,
        ),
        JournalEntry(
            id=f"event-{event_id}-cogs",
            date=event_date,
            lines=(
                make_line(cogs_account_id, debit=str(cost_of_goods_sold)),
                make_line(inventory_account_id, credit=str(cost_of_goods_sold)),
            ),
            source_event_id=event_id,
        ),
    ]
