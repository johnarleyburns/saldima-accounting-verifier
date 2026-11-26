# reference/sync

Multi-book isolation and merge/reconciliation semantics (docs/plan.md
section 14, Phase 6). Validates book isolation and multi-device merge at
the accounting-semantics level, without duplicating Saldima's production
cryptographic/sync implementation -- see `merge.py`'s docstring and
docs/accounting-policy.md.

**Status:** `merge.py` is implemented (scenarios `SYNC-001`/`SYNC-002`).
Pure functions over `JournalEntry`/`ChartOfAccounts`
(`reference/accounting/journal.py`) -- no change to `Ledger` itself, and
no dependency on Saldima production code.
