"""One-off script: load a scenario and export it as a real GnuCash v2 XML
file, suitable for opening directly in GnuCash. Uses
`adapters.gnucash_xml.GnuCashXmlAdapter` -- the same adapter
`tests/compatibility/test_gnc_001_round_trip.py` round-trips in memory --
but this script is the first place the exported bytes are actually
written to disk as a standalone artifact, rather than only compared
in-process.

Usage: python scripts/export_gnucash_book.py \
    scenarios/fixed-assets/fa-001-straight-line-equipment-depreciation.yaml \
    fa-001.gnucash
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from adapters.gnucash_xml.adapter import GnuCashXmlAdapter
from runner.scenario_runner import load_scenario


def main() -> None:
    scenario_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    loaded = load_scenario(scenario_path)

    adapter = GnuCashXmlAdapter()
    book_id = adapter.create_book(loaded.raw)
    xml_bytes = adapter.export_book(book_id)

    out_path.write_bytes(xml_bytes)
    print(f"Wrote {len(xml_bytes):,} bytes to {out_path}")


if __name__ == "__main__":
    main()
