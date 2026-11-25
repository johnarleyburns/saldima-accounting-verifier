# Dataset Provenance

Per `docs/plan.md` section 9, every dataset placed under `datasets/` must
record, before it is used by any scenario or test:

- Source and URL/citation.
- License and any usage restrictions.
- What it validates (and, just as importantly, what it does **not**
  validate — e.g. SEC XBRL facts validate statement presentation, not
  transaction-level journal entries; synthetic ledgers validate ingestion
  and scale, not accounting correctness, unless independently reviewed).
- Date imported and import method.
- Any transformation applied before use.

**Status: no datasets have been imported yet.** `datasets/academic/`,
`datasets/public_filings/`, `datasets/synthetic/`, and `datasets/imported/`
are empty placeholders (see their READMEs). The intended initial sources
are listed in `docs/plan.md` section 9.1–9.4 (DFKI/Saarland synthetic GL
dataset, SEC EDGAR XBRL company facts, IRS Publications 946 and 541).
Each import gets its own provenance record (a `PROVENANCE.md` alongside
the data) added in the same change that adds the data.
