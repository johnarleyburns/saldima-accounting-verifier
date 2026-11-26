# reference/schedules

Supporting-schedule reference implementations: depreciation, deferred
revenue, receivables, payables, inventory, debt amortization.

**Status:** Fully implemented — `deferred_revenue.py`, `receivables.py`,
and `payables.py` (Phase 2), `depreciation.py` and `inventory.py`
(Phase 3), and `debt.py` (Phase 4). See `docs/plan.md` section 18 and
`docs/accounting-policy.md` for each phase's rationale. Each module
follows the same rules as `reference/accounting/`: pure Decimal
arithmetic, no dependency on Saldima production code, deterministic
output.
