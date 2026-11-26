# reference/schedules

Supporting-schedule reference implementations: depreciation, deferred
revenue, receivables, payables, inventory, debt amortization.

**Status:** `deferred_revenue.py`, `receivables.py`, and `payables.py` are
implemented (Phase 2 — see `docs/plan.md` section 18 and
`docs/accounting-policy.md`). `depreciation.py` and `inventory.py` are
implemented (Phase 3, same sections). `debt.py` is not yet implemented; it
lands with Phase 4 (debt) scenarios. Each module follows the same rules as
`reference/accounting/`: pure Decimal arithmetic, no dependency on
Saldima production code, deterministic output.
