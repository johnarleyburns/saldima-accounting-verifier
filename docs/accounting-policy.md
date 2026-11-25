# Accounting Policy Reference

Every scenario must declare its accounting basis explicitly (docs/plan.md
section 2.4). This document tracks which policies the reference model
currently understands.

## `accounting.framework`

`US_GAAP`, `IFRS`, `CASH_BASIS`, `TAX_BASIS`, `MANAGEMENT` are all valid per
the schema. **Only the mechanics common to all of them (balanced double-
entry, trial balance, income statement, balance sheet, indirect-method
operating cash flow) are implemented so far.** No framework-specific rule
(e.g. IFRS vs. US GAAP revenue recognition differences) is implemented yet.
A scenario's `framework` value is currently documentation of intent, not
yet an input that changes reference-model behavior — this will change as
Phase 2+ scenarios require framework-specific treatment, and that change
must be called out loudly here when it lands.

## `accounting.basis`

`accrual` or `cash`. Not yet enforced by the reference model — Phase 1
scenarios use explicit `manual_journal_entry` events, so the author is
responsible for making the journal entries consistent with the declared
basis. Enforcement (e.g. rejecting an accrual-basis scenario with no
receivable/payable accounts) is future work.

## Rounding

`rounding.currency_precision` (default 2) and `rounding.method` (`HALF_UP`,
`HALF_EVEN`, `DOWN`) are implemented in `reference/accounting/rounding.py`.
Only `closing.py`'s computed closing amounts currently apply rounding
explicitly (via `round_currency`); all other scenario inputs are expected
to already be expressed as 2-decimal-place strings matching the
scenario's declared precision.

## Policies not yet modeled

`policies.inventory`, `policies.depreciation`, `policies.revenue_recognition`
etc. are accepted by the schema (`"policies": {"type": "object"}`, free-
form) but have no reference-model behavior yet — they arrive with Phase 3
(fixed assets/inventory) and the revenue-recognition scenario category. Do
not infer that setting one of these fields currently changes output.
