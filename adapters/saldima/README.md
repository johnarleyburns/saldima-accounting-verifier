# adapters/saldima

**Status:** Interface contract defined (see `adapters/__init__.py` and
`docs/architecture.md`); concrete implementation not yet written.

Earlier docs in this repository claimed no Saldima engine existed to
drive, full stop — that was wrong. A real Saldima engine exists as the
sibling repository `saldima` (TypeScript on Cloudflare, currently Phase
P0/Foundations; see its own `docs/spec/`), plus `saldima-ios`/
`saldima-android`. It has simply never been connected to *this*
repository. Implementing this adapter for real requires studying that
engine's actual accounting data model/API first (a separate piece of
work, touching a separate repository with its own contract) before this
suite could drive it.

This adapter must implement `AccountingSystemAdapter` and return normalized
data in the comparison schema (`schemas/financial-statement.schema.json`,
`schemas/schedule.schema.json`). It must never calculate expected results —
see `docs/plan.md` section 2.1 and section 11.
