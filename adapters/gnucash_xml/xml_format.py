"""GnuCash v2 XML serialization and parsing.

Grounded against the actual, authoritative GnuCash RELAX NG compact schema
(`libgnucash/backend/xml/DTD/gnucash-v2.rnc` in `Gnucash/gnucash`), fetched
directly rather than guessed, since nothing about the GnuCash XML format
existed anywhere in this repository before Phase 6 -- see
docs/accounting-policy.md. Implements the minimal subset this reference
model needs: one `gnc:book`, `gnc:account`, and `gnc:transaction`/
`trn:split` elements. No commodities (beyond a single USD ISO4217
declaration), prices, budgets, scheduled transactions, or business
features.

Two reference-model concepts have no native GnuCash representation, so
they're round-tripped via GnuCash's own KVP slot extensibility
(`act:slots`/`trn:slots`) -- a documented convention, not a native
GnuCash semantic:

- `cash_flow_category` (non-"operating" only) as an account-level slot.
- The original reference-model account/entry id as a slot too, since
  this module's GUIDs are one-way hashes of those ids (deterministic,
  per docs/plan.md section 2.3, but not invertible) -- GnuCash's own
  identity (the GUID) and this adapter's round-trip fidelity (the
  original id) are two different concerns that both need to survive.

`JournalEntry.is_closing` also has no native representation, but needs
no extra slot: `closing.py` already gives every closing entry a
distinctive `trn:description` (its `memo`), so import just detects that
exact prefix.
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal

from reference.accounting.journal import (
    Account,
    AccountingError,
    AccountType,
    CashFlowCategory,
    ChartOfAccounts,
    JournalEntry,
    make_line,
)
from reference.accounting.rounding import ZERO

NS = {
    "gnc": "http://www.gnucash.org/XML/gnc",
    "act": "http://www.gnucash.org/XML/act",
    "book": "http://www.gnucash.org/XML/book",
    "cd": "http://www.gnucash.org/XML/cd",
    "cmdty": "http://www.gnucash.org/XML/cmdty",
    "trn": "http://www.gnucash.org/XML/trn",
    "ts": "http://www.gnucash.org/XML/ts",
    "slot": "http://www.gnucash.org/XML/slot",
    "split": "http://www.gnucash.org/XML/split",
}
for _prefix, _uri in NS.items():
    ET.register_namespace(_prefix, _uri)

ACCOUNT_TYPE_TO_GNUCASH = {
    AccountType.ASSET: "ASSET",
    AccountType.LIABILITY: "LIABILITY",
    AccountType.EQUITY: "EQUITY",
    AccountType.REVENUE: "INCOME",  # GnuCash calls revenue accounts "INCOME".
    AccountType.EXPENSE: "EXPENSE",
}
GNUCASH_TYPE_TO_ACCOUNT_TYPE = {gnucash: ours for ours, gnucash in ACCOUNT_TYPE_TO_GNUCASH.items()}

CLOSING_ENTRY_DESCRIPTION_PREFIX = "Closing entry for "
SCU = 100  # commodity-scu: this reference model is always 2-decimal currency.


def _tag(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def account_guid(account_id: str) -> str:
    return hashlib.md5(f"account:{account_id}".encode()).hexdigest()


def root_account_guid() -> str:
    return hashlib.md5(b"root-account").hexdigest()


def entry_guid(entry_id: str) -> str:
    return hashlib.md5(f"transaction:{entry_id}".encode()).hexdigest()


def split_guid(entry_id: str, line_index: int) -> str:
    return hashlib.md5(f"split:{entry_id}:{line_index}".encode()).hexdigest()


def encode_numeric(value: Decimal, scu: int = SCU) -> str:
    """Decimal -> GnuCash's signed fraction notation (e.g. "10000/100")."""
    numerator = int(value * scu)
    return f"{numerator}/{scu}"


def decode_numeric(value: str) -> Decimal:
    numerator_text, denominator_text = value.split("/")
    return (Decimal(numerator_text) / Decimal(denominator_text)).quantize(Decimal("0.01"))


def encode_timestamp(d: date) -> str:
    return f"{d.isoformat()} 00:00:00 +0000"


def decode_timestamp(value: str) -> date:
    return date.fromisoformat(value[:10])


def _add_slot(slots_el: ET.Element, key: str, value: str) -> None:
    slot_el = ET.SubElement(slots_el, _tag("slot", "slot"))
    ET.SubElement(slot_el, _tag("slot", "key")).text = key
    value_el = ET.SubElement(slot_el, _tag("slot", "value"))
    value_el.set("type", "string")
    value_el.text = value


def _read_slots(slots_el: ET.Element | None) -> dict[str, str]:
    if slots_el is None:
        return {}
    slots: dict[str, str] = {}
    for slot_el in slots_el.findall(_tag("slot", "slot")):
        key = slot_el.findtext(_tag("slot", "key")) or ""
        value_el = slot_el.find(_tag("slot", "value"))
        slots[key] = (value_el.text if value_el is not None else None) or ""
    return slots


def _commodity_element(parent_el: ET.Element, tag_prefix: str) -> None:
    commodity_el = ET.SubElement(parent_el, _tag(tag_prefix, "commodity"))
    ET.SubElement(commodity_el, _tag("cmdty", "space")).text = "ISO4217"
    ET.SubElement(commodity_el, _tag("cmdty", "id")).text = "USD"


def _account_element(book_el: ET.Element, account: Account) -> None:
    el = ET.SubElement(book_el, _tag("gnc", "account"))
    el.set("version", "2.0.0")
    ET.SubElement(el, _tag("act", "name")).text = account.name
    id_el = ET.SubElement(el, _tag("act", "id"))
    id_el.set("type", "guid")
    id_el.text = account_guid(account.id)
    ET.SubElement(el, _tag("act", "type")).text = ACCOUNT_TYPE_TO_GNUCASH[account.type]
    _commodity_element(el, "act")
    ET.SubElement(el, _tag("act", "commodity-scu")).text = str(SCU)

    slots_el = ET.SubElement(el, _tag("act", "slots"))
    _add_slot(slots_el, "saldima_account_id", account.id)
    if account.cash_flow_category != CashFlowCategory.OPERATING:
        _add_slot(slots_el, "cash_flow_category", account.cash_flow_category.value)

    parent_el = ET.SubElement(el, _tag("act", "parent"))
    parent_el.set("type", "guid")
    parent_el.text = account_guid(account.parent_id) if account.parent_id else root_account_guid()


def _root_account_element(book_el: ET.Element) -> None:
    el = ET.SubElement(book_el, _tag("gnc", "account"))
    el.set("version", "2.0.0")
    ET.SubElement(el, _tag("act", "name")).text = "Root Account"
    id_el = ET.SubElement(el, _tag("act", "id"))
    id_el.set("type", "guid")
    id_el.text = root_account_guid()
    ET.SubElement(el, _tag("act", "type")).text = "ROOT"


def _transaction_element(book_el: ET.Element, entry: JournalEntry) -> None:
    el = ET.SubElement(book_el, _tag("gnc", "transaction"))
    el.set("version", "2.0.0")
    id_el = ET.SubElement(el, _tag("trn", "id"))
    id_el.set("type", "guid")
    id_el.text = entry_guid(entry.id)
    _commodity_element(el, "trn")
    date_posted_el = ET.SubElement(el, _tag("trn", "date-posted"))
    ET.SubElement(date_posted_el, _tag("ts", "date")).text = encode_timestamp(entry.date)
    date_entered_el = ET.SubElement(el, _tag("trn", "date-entered"))
    ET.SubElement(date_entered_el, _tag("ts", "date")).text = encode_timestamp(entry.date)
    ET.SubElement(el, _tag("trn", "description")).text = entry.memo

    slots_el = ET.SubElement(el, _tag("trn", "slots"))
    _add_slot(slots_el, "saldima_entry_id", entry.id)
    if entry.source_event_id:
        _add_slot(slots_el, "source_event_id", entry.source_event_id)

    splits_el = ET.SubElement(el, _tag("trn", "splits"))
    for i, line in enumerate(entry.lines):
        split_el = ET.SubElement(splits_el, _tag("trn", "split"))
        split_id_el = ET.SubElement(split_el, _tag("split", "id"))
        split_id_el.set("type", "guid")
        split_id_el.text = split_guid(entry.id, i)
        ET.SubElement(split_el, _tag("split", "reconciled-state")).text = "n"
        value = encode_numeric(line.debit - line.credit)
        ET.SubElement(split_el, _tag("split", "value")).text = value
        ET.SubElement(split_el, _tag("split", "quantity")).text = value
        account_el = ET.SubElement(split_el, _tag("split", "account"))
        account_el.set("type", "guid")
        account_el.text = account_guid(line.account_id)


def export_book(chart: ChartOfAccounts, entries: list[JournalEntry]) -> bytes:
    """Serialize `chart`/`entries` to a real, schema-valid GnuCash v2 XML
    document (see module docstring for the exact subset implemented)."""
    gnc_root = ET.Element("gnc-v2")  # the top-level element itself has no namespace prefix.

    count_data_book = ET.SubElement(gnc_root, _tag("gnc", "count-data"))
    count_data_book.set(_tag("cd", "type"), "book")
    count_data_book.text = "1"

    book_el = ET.SubElement(gnc_root, _tag("gnc", "book"))
    book_el.set("version", "2.0.0")
    book_id_el = ET.SubElement(book_el, _tag("book", "id"))
    book_id_el.set("type", "guid")
    book_id_el.text = hashlib.md5(b"book").hexdigest()

    account_count_el = ET.SubElement(book_el, _tag("gnc", "count-data"))
    account_count_el.set(_tag("cd", "type"), "account")
    account_count_el.text = str(len(chart.accounts) + 1)  # +1 for the synthesized ROOT.
    transaction_count_el = ET.SubElement(book_el, _tag("gnc", "count-data"))
    transaction_count_el.set(_tag("cd", "type"), "transaction")
    transaction_count_el.text = str(len(entries))

    commodity_el = ET.SubElement(book_el, _tag("gnc", "commodity"))
    commodity_el.set("version", "2.0.0")
    ET.SubElement(commodity_el, _tag("cmdty", "space")).text = "ISO4217"
    ET.SubElement(commodity_el, _tag("cmdty", "id")).text = "USD"

    _root_account_element(book_el)
    for account in chart.accounts.values():
        _account_element(book_el, account)
    for entry in entries:
        _transaction_element(book_el, entry)

    result: bytes = ET.tostring(gnc_root, encoding="utf-8", xml_declaration=True)
    return result


def parse_book(xml_bytes: bytes) -> tuple[ChartOfAccounts, list[JournalEntry]]:
    """Parse a GnuCash v2 XML document back into `(chart, entries)`."""
    gnc_root = ET.fromstring(xml_bytes)
    book_el = gnc_root.find(_tag("gnc", "book"))
    if book_el is None:
        raise AccountingError("GnuCash XML is missing its gnc:book element")

    chart = ChartOfAccounts()
    guid_to_account_id: dict[str, str] = {}

    for account_el in book_el.findall(_tag("gnc", "account")):
        gnucash_type = account_el.findtext(_tag("act", "type"))
        guid = account_el.findtext(_tag("act", "id")) or ""
        if gnucash_type == "ROOT":
            continue

        slots = _read_slots(account_el.find(_tag("act", "slots")))
        account_id = slots.get("saldima_account_id")
        if not account_id:
            raise AccountingError(f"GnuCash account {guid!r} is missing its saldima_account_id slot")
        cash_flow_category = CashFlowCategory(slots.get("cash_flow_category", "operating"))

        parent_guid = account_el.findtext(_tag("act", "parent"))
        parent_id = None
        if parent_guid and parent_guid != root_account_guid():
            parent_id = guid_to_account_id[parent_guid]

        chart.add(
            Account(
                id=account_id,
                name=account_el.findtext(_tag("act", "name")) or "",
                type=GNUCASH_TYPE_TO_ACCOUNT_TYPE[gnucash_type or ""],
                parent_id=parent_id,
                cash_flow_category=cash_flow_category,
            )
        )
        guid_to_account_id[guid] = account_id

    entries: list[JournalEntry] = []
    for txn_el in book_el.findall(_tag("gnc", "transaction")):
        slots = _read_slots(txn_el.find(_tag("trn", "slots")))
        entry_id = slots.get("saldima_entry_id")
        if not entry_id:
            raise AccountingError("GnuCash transaction is missing its saldima_entry_id slot")

        date_posted_el = txn_el.find(_tag("trn", "date-posted"))
        entry_date = decode_timestamp((date_posted_el.findtext(_tag("ts", "date")) if date_posted_el is not None else None) or "")
        description = txn_el.findtext(_tag("trn", "description")) or ""
        is_closing = description.startswith(CLOSING_ENTRY_DESCRIPTION_PREFIX)

        lines = []
        splits_el = txn_el.find(_tag("trn", "splits"))
        for split_el in splits_el.findall(_tag("trn", "split")) if splits_el is not None else []:
            value = decode_numeric(split_el.findtext(_tag("split", "value")) or "0/1")
            account_guid_ref = split_el.findtext(_tag("split", "account")) or ""
            account_id = guid_to_account_id[account_guid_ref]
            if value >= ZERO:
                lines.append(make_line(account_id, debit=str(value)))
            else:
                lines.append(make_line(account_id, credit=str(-value)))

        entries.append(
            JournalEntry(
                id=entry_id,
                date=entry_date,
                lines=tuple(lines),
                memo=description,
                source_event_id=slots.get("source_event_id"),
                is_closing=is_closing,
            )
        )

    return chart, entries
