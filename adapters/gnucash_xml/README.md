# adapters/gnucash_xml

**Status:** Implemented (Phase 6, scenario `GNC-001` — see `docs/plan.md`
section 18/19). `GnuCashXmlAdapter` (`adapter.py`) implements
`AccountingSystemAdapter` (`adapters/__init__.py`) as a self-contained
engine backed by GnuCash's own data model, not a live Saldima engine —
`adapters/saldima/` stays unimplemented, since no Saldima engine has been
connected to *this* repository (a real one does exist as the sibling
`saldima` repository — see `adapters/saldima/README.md`).

`scripts/export_gnucash_book.py` writes a scenario's exported book to a
real `.gnucash` file on disk, for opening directly in GnuCash — `GNC-001`
itself only ever round-trips in memory.

`xml_format.py` serializes/parses the minimal GnuCash v2 XML subset this
reference model needs (one `gnc:book`, accounts, transactions/splits),
grounded against the actual, authoritative GnuCash RELAX NG schema
(`libgnucash/backend/xml/DTD/gnucash-v2.rnc` in `Gnucash/gnucash`, fetched
directly rather than guessed). Two reference-model concepts with no
native GnuCash representation (`cash_flow_category`, and the original
reference-model account/entry id, since this module's GUIDs are one-way
hashes) round-trip via GnuCash's own KVP slot extensibility — a
documented convention, not a native GnuCash semantic. See
`docs/accounting-policy.md`.
