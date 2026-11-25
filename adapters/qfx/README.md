# adapters/qfx

**Status:** Interface contract defined (see `adapters/__init__.py` and
`docs/architecture.md`); concrete implementation not yet written.

This adapter must implement `AccountingSystemAdapter` and return normalized
data in the comparison schema (`schemas/financial-statement.schema.json`,
`schemas/schedule.schema.json`). It must never calculate expected results —
see `docs/plan.md` section 2.1 and section 11.
