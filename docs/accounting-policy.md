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

`accrual` or `cash`. Not yet enforced by the reference model — scenarios
using `manual_journal_entry` events are responsible for making their
journal entries consistent with the declared basis, and
`customer_contract_payment` (Phase 2) always produces accrual-basis
entries (cash received now, revenue recognized on its own schedule)
regardless of the declared basis. Enforcement (e.g. rejecting an
accrual-basis scenario with no receivable/payable accounts) is future
work.

## Rounding

`rounding.currency_precision` (default 2) and `rounding.method` (`HALF_UP`,
`HALF_EVEN`, `DOWN`) are implemented in `reference/accounting/rounding.py`.
Only `closing.py`'s computed closing amounts currently apply rounding
explicitly (via `round_currency`); all other scenario inputs are expected
to already be expressed as 2-decimal-place strings matching the
scenario's declared precision.

## Policies not yet modeled

`policies.inventory`, `policies.depreciation` etc. are accepted by the
schema (`"policies": {"type": "object"}`, free-form) but have no
reference-model behavior yet — they arrive with Phase 3 (fixed assets/
inventory). Do not infer that setting one of these fields currently
changes output.

`policies.revenue_recognition` is the one exception as of Phase 2:
`straight_line` and `point_in_time` are real reference-model behaviors, but
only as applied by the `customer_contract_payment` event type (see "Event
model: Phase 1 vs Phase 2" below) — setting the field alone, with no such
event, still changes nothing.

## Event model: Phase 1 vs Phase 2

Phase 1 implements exactly one event type, `manual_journal_entry`: the
scenario author supplies explicit debit/credit lines, and the reference
model just posts them (see `docs/scenario-authoring.md`). Phase 2 keeps
that for accruals and prepayments (`ACCR-001`, `ACCR-002`) but adds one
higher-level event type, `customer_contract_payment`, for deferred revenue
(`REV-001`, `REV-002`) — the example from `docs/plan.md` section 2.2.

The distinction that decided this, scenario by scenario: an accrual or a
prepayment amount is a business fact the scenario author just states ("the
business accrued $1,200 of payroll this month," "amortize $100/month of
prepaid insurance") — there's no accounting *method* for the reference
model to apply beyond posting the stated entry, so staying on
`manual_journal_entry` is honest about what's actually being tested.
Revenue recognition is different: straight-line recognition over a
service period, or allocating one contract price across several
performance obligations recognized by different methods, is a genuine
policy decision (`policies.revenue_recognition`) that the model itself
must apply to a declared schedule, not just copy from author-supplied
numbers. `customer_contract_payment` is the first event type to exercise
that architecture; see `docs/scenario-authoring.md` for its exact shape and
`reference/schedules/deferred_revenue.py` for the schedule math.

Straight-line recognition currently assumes `service_start` is the first
day of its month and `service_end` is the last day of its month —
partial-month proration is not implemented yet
(`reference/schedules/deferred_revenue.py` raises `AccountingError` if
violated).

## AR/AP flowing through the existing statements (Phase 2 confirmation)

`trial_balance.py`, `income_statement.py`, `balance_sheet.py`, and
`closing.py` are generic over `AccountType` and needed no Phase 2 code
changes for accounts receivable, accounts payable, accrued liabilities,
prepaid expenses, or deferred revenue — they were already correct by
construction. `cash_flow.py`'s indirect-method adjustment (every non-cash
asset increase is a use of cash; every liability/equity increase is a
source of cash) is likewise already the correct treatment for all of
these account types, not a Phase-1-only coincidence — see the
reconciliation proof sketch in `docs/reference-model.md`, and
`tests/invariants/test_accrual_accounts_flow_through.py`, which proves
this directly against a small hand-built ledger independent of any one
scenario's bookkeeping choices.

## `reference/schedules/receivables.py` and `payables.py`

Both are pure-Decimal, ledger-independent open-item/aging calculators
(`Invoice`/`Payment` and `Bill`/`Payment`), meant to *corroborate* a
ledger's AR/AP balance rather than restate it. `payables.py` is exercised
for real in `tests/integration/test_core_scenarios.py`'s ACCR-001
cross-check (its accrued-liability accounts are treated as a form of
payable — a month's accrual is an open bill, the following month's
payment closes it). `receivables.py` has no end-to-end gold-standard
scenario yet: none of Phase 2's four target scenarios (`ACCR-001/002`,
`REV-001/002`) involve a trade receivable (invoice-now-collect-later
credit sale), and `docs/plan.md` section 19 doesn't list a dedicated AR
scenario in this batch. It's unit-tested directly
(`tests/unit/test_receivables.py`) pending a future credit-sales scenario.
