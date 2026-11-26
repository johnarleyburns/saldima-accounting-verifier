"""GNC-001: GnuCash XML semantic round trip (docs/plan.md section 10 and
section 19).

Round-trips `FA-001` (5 years, already reviewed -- see
scenarios/fixed-assets/fa-001-straight-line-equipment-depreciation.yaml)
through `adapters/gnucash_xml`: export to real GnuCash v2 XML, re-import,
and check *semantic* equivalence per section 10's own wording (GUIDs,
dates, amounts, relationships -- not byte-for-byte XML equality), plus a
financial-statement check that the round trip preserves everything
needed to reproduce `FA-001`'s existing reviewed fixtures exactly,
reusing that trusted ground truth rather than inventing new numbers to
hand-verify (the same logic `FA-003` used for its MACRS side).
"""

import json
from decimal import Decimal
from pathlib import Path

from adapters.gnucash_xml import xml_format
from adapters.gnucash_xml.adapter import GnuCashXmlAdapter, rebuild_ledger_from_xml
from runner import compare, reference_runner
from runner.scenario_runner import LoadedScenario, load_scenario

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FA_001 = REPO_ROOT / "scenarios" / "fixed-assets" / "fa-001-straight-line-equipment-depreciation.yaml"


def _round_trip() -> tuple[LoadedScenario, LoadedScenario, bytes]:
    """Returns (the book as built for export, the re-imported book, the XML bytes)."""
    loaded_for_periods = load_scenario(FA_001)
    adapter = GnuCashXmlAdapter()
    book_id = adapter.create_book(loaded_for_periods.raw)
    original_loaded = adapter._books[book_id]  # test-only introspection of adapter-internal state

    xml_bytes = adapter.export_book(book_id)
    reimported_chart, reimported_ledger = rebuild_ledger_from_xml(xml_bytes)
    reimported_loaded = LoadedScenario(raw=loaded_for_periods.raw, chart=reimported_chart, ledger=reimported_ledger)

    return original_loaded, reimported_loaded, xml_bytes


def test_exported_xml_uses_the_real_gnucash_element_and_attribute_names():
    _, _, xml_bytes = _round_trip()
    text = xml_bytes.decode()
    assert text.startswith("<?xml version='1.0' encoding='utf-8'?>")
    for expected_fragment in (
        "<gnc-v2",
        "<gnc:count-data",
        "<gnc:book",
        "<book:id",
        "<gnc:commodity",
        "<gnc:account",
        "<act:name>",
        "<act:type>ROOT</act:type>",
        "<act:type>ASSET</act:type>",
        "<gnc:transaction",
        "<trn:splits>",
        "<trn:split>",
        "<split:reconciled-state>n</split:reconciled-state>",
        "<split:value>",
        "<split:account",
    ):
        assert expected_fragment in text, f"missing {expected_fragment!r} in exported XML"


def test_every_account_round_trips_with_identical_id_name_type_parent_and_cash_flow_category():
    original, reimported, _ = _round_trip()
    assert set(reimported.chart.accounts.keys()) == set(original.chart.accounts.keys())
    for account_id, original_account in original.chart.accounts.items():
        reimported_account = reimported.chart.accounts[account_id]
        assert reimported_account.name == original_account.name
        assert reimported_account.type == original_account.type
        assert reimported_account.parent_id == original_account.parent_id
        assert reimported_account.cash_flow_category == original_account.cash_flow_category


def test_every_journal_entry_round_trips_with_identical_date_closing_flag_and_lines():
    original, reimported, _ = _round_trip()
    original_by_id = {entry.id: entry for entry in original.ledger.entries}
    reimported_by_id = {entry.id: entry for entry in reimported.ledger.entries}
    assert set(reimported_by_id) == set(original_by_id)

    for entry_id, original_entry in original_by_id.items():
        reimported_entry = reimported_by_id[entry_id]
        assert reimported_entry.date == original_entry.date
        assert reimported_entry.is_closing == original_entry.is_closing
        original_lines = {(line.account_id, line.debit, line.credit) for line in original_entry.lines}
        reimported_lines = {(line.account_id, line.debit, line.credit) for line in reimported_entry.lines}
        assert reimported_lines == original_lines, entry_id


def test_reimported_book_reproduces_fa_001s_reviewed_financial_statements_exactly():
    _, reimported, _ = _round_trip()
    loaded_for_periods = load_scenario(FA_001)

    failures = []
    for period in loaded_for_periods.report_periods:
        actual = reference_runner.generate_period_reports(reimported, period)
        for statement_type in ("trial_balance", "income_statement", "balance_sheet", "cash_flow"):
            fixture_path = REPO_ROOT / "expected" / "reviewed" / loaded_for_periods.id / period / f"{statement_type}.json"
            expected = json.loads(fixture_path.read_text())
            result = compare.compare_statement(expected, actual[statement_type])
            if result["status"] == "FAIL":
                failures.append(result)

    assert not failures, json.dumps(failures, indent=2)


def test_decode_numeric_is_the_exact_inverse_of_encode_numeric():
    for value in (Decimal("0.00"), Decimal("1000.00"), Decimal("-500.25"), Decimal("12345.67")):
        assert xml_format.decode_numeric(xml_format.encode_numeric(value)) == value
