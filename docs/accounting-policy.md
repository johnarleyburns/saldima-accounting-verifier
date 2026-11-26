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

As of Phase 3, `policies.depreciation` and `policies.inventory` are now
real reference-model behaviors too (straight-line depreciation via
`fixed_asset_purchase`; FIFO costing via `inventory_purchase`/
`inventory_sale` — see "Event model" below), the same way
`policies.revenue_recognition` became real in Phase 2: only as applied by
the matching event type, never just by setting the field alone with no
such event. Every other `policies.*` field (e.g. a depreciation method
other than straight-line, an inventory method other than FIFO) is accepted
by the schema (`"policies": {"type": "object"}`, free-form) but has no
reference-model behavior yet. Do not infer that setting one of these
fields currently changes output.

## `cash_flow_category` (Phase 3)

Every `Account` now has an optional `cash_flow_category`
(`operating`/`investing`/`financing`, default `operating` —
`reference/accounting/journal.py`'s `CashFlowCategory`), which
`cash_flow.py` uses to classify each non-cash account's period delta into
the matching section of the statement of cash flows. It defaults to
`operating` because that's the only category any Phase 1/2 scenario ever
needed — a fixed asset is the first case where an account's balance
changes represent investing activity rather than ordinary operations. See
`docs/reference-model.md`'s "Phase 3 adds investing/financing
classification" section for the reconciliation math and the proof that
this was additive, not a change to Phase 1/2 scenarios' numbers.

**Known coarseness:** `cash_flow.py` classifies by *whole-account period
delta*, not by individual transaction. In a period where an asset is both
depreciated and disposed of, the account's delta mixes "depreciation
add-back" and "the disposal zeroing the balance out" into one number,
which doesn't match a textbook indirect-method presentation line-by-line
(that would separately show "depreciation", "gain/loss removed from net
income", and "proceeds from sale of equipment"). The *aggregate*
reconciliation (`operating_cash_flow + investing_cash_flow +
financing_cash_flow == net_change_in_cash`) is exact in every period
regardless — see FA-002's `approval.json` for a concrete worked example of
this nuance, and `docs/reference-model.md`.

## `cash_flow_category: financing` now populated for real (Phase 4)

`DEBT-001` is the first scenario to tag an account `cash_flow_category:
financing` (`loan_payable`) — `docs/reference-model.md` had already
predicted this ("Debt (Phase 4) is expected to be the next phase to
populate `financing_activities`"). No further code change was needed:
`cash_flow.py`'s classification is purely by `account.cash_flow_category`
regardless of whether the account is an asset or a liability, so loan
proceeds (a liability increase, a financing *source* of cash) and every
principal repayment (a liability decrease, a financing *use*) both flow
through the existing generic logic. `tests/invariants/
test_debt_accounts_flow_through.py` proves both directions directly,
independent of any scenario — the liability-side counterpart to
`FA-001`/`FA-002`'s asset-side proof.

## Event model: Phase 1 vs Phase 2 vs Phase 3 vs Phase 4

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

Phase 3 adds four more higher-level event types, by the same test: is the
amount a stated business fact, or does the model have to apply a policy
to derive it?

- **`fixed_asset_purchase`** (`FA-001`/`002`/`003`): straight-line
  depreciation over a declared useful life is a policy the model must
  apply to a schedule (`reference/schedules/depreciation.py`), same
  convention as deferred revenue (calendar-month boundaries, remainder in
  the last month). It additionally derives the correct depreciation
  *stop* date when a matching `fixed_asset_disposal` event (linked by
  `asset_id`) exists for the same asset — `runner/scenario_runner.py`
  pre-scans all `fixed_asset_disposal` events by `asset_id` before
  translating any `fixed_asset_purchase`, since depreciation can't be
  fully pre-generated the way deferred revenue could (an asset's life can
  end early; a contract's can't).
- **`fixed_asset_disposal`** (`FA-002`): the gain or loss on disposal
  (`reference/schedules/depreciation.py`'s `disposal_gain_loss`) is
  computed from the matching purchase event's own cost/salvage/useful-life
  (looked up by `asset_id`, no ledger queries needed) — a derived result,
  not something the scenario author states directly.
- **`inventory_purchase`** / **`inventory_sale`** (`INV-001`/`002`): the
  purchase and sale dollar totals are plain multiplication, but the cost
  of goods sold on a sale is derived by consuming FIFO lots oldest-first
  (`reference/schedules/inventory.py`'s `consume_fifo`) from the running
  list of open lots built up by prior purchases in the same scenario —
  the one Phase 1-3 event type whose translation needs state carried
  *across* events (`runner/scenario_runner.py` keeps a
  `dict[inventory_account_id, list[Lot]]` through the event loop, in file
  order, which must therefore be chronological per inventory account).

An **inventory write-down** (`INV-002`) stays on `manual_journal_entry`,
by the same accruals-and-prepayments logic as Phase 2: the write-down
dollar amount is management's own stated valuation judgment (market value
is below cost by $X), not something derivable from a schedule.

Phase 4 adds one more higher-level event type and, for the first time
since Phase 2, confirms a whole scenario can stay on plain
`manual_journal_entry`:

- **`loan_origination`** (`DEBT-001`): the scenario author states the
  loan's principal, annual rate, and term; the reference model derives
  the full month-by-month principal/interest split from the declining
  balance (`reference/schedules/debt.py`'s `build_amortization_schedule`)
  — a genuine computation, not a restated number. Deliberately modeled
  as an **equal-principal, declining-interest** loan rather than the
  standard level-total-payment annuity: solving the annuity formula
  (`payment = P·r / (1 − (1+r)⁻ⁿ)`) for an arbitrary rate/term essentially
  never lands on a clean cent, which would make a gold fixture's hand-
  verification arithmetic tedious for no real gain in what's being
  tested. Equal-principal loans are a real, common business-loan
  structure, and with principal divisible evenly by the term, the
  resulting interest schedule is a clean arithmetic sequence (every
  month's interest drops by the same fixed amount) that's fully hand-
  verifiable month-by-month, not just spot-checked.
- **`PAY-001`** (payroll and withholding) is, deliberately, **not** a new
  event type: gross pay, every withholding amount, and the employer's
  matching FICA are all stated business facts the payroll system/
  bookkeeper supplies directly — there's no schedule for the reference
  model to derive, the same reasoning that kept Phase 2's accruals on
  `manual_journal_entry`. It reuses `ACCR-001`'s one-month accrual/
  payment lag (withheld and employer amounts accrue monthly, remitted
  the following month), which is both realistic and lets the fixture's
  arithmetic reuse an already-proven pattern.

## FA-003 scope boundary: MACRS schedule only, no deferred tax

`reference/tax/macrs.py` implements the published IRS Publication 946
Table A-1 percentages for 5-year property under the half-year convention
(20.00%, 32.00%, 19.20%, 11.52%, 11.52%, 5.76%, across six tax years).
`FA-003` uses it to validate the MACRS schedule *computation* — accelerated
depreciation spanning six tax years, versus the same asset's flat
straight-line book schedule spanning exactly five — via a dedicated test
(`tests/integration/test_fa_003_tax_vs_book_depreciation.py`), not by
posting a book-vs-tax journal entry.

Modeling the actual divergence between MACRS and book depreciation as GAAP
journal entries requires deferred tax asset/liability accounting, which is
out of scope for "fixed assets and inventory" (`docs/plan.md` Phase 3) —
that's real tax-accounting territory, deferred to a later phase the same
way partnership tax basis and 704(c) are. `FA-003`'s ledger only ever
posts the book (straight-line) schedule, identical in shape to `FA-001`'s.

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

## Contra-asset and gain/loss accounts flowing through the existing statements (Phase 3 confirmation)

Accumulated depreciation is declared `type: asset` in every Phase 3 fixed-
asset scenario's chart, even though it's a *contra*-asset (it only ever
receives credits). No change was needed anywhere: `balance_sheet.py`'s
`signed_balance` (debit-normal for `ASSET`) naturally goes negative as
credits accumulate, and summing it with the gross asset account in
`total_assets` produces net book value for free — the same "already
generic" result Phase 2 found for AR/AP. Gain/loss-on-disposal accounts
are likewise ordinary `revenue`/`expense`-type accounts; `income_statement.py`
needed no changes either. `tests/invariants/
test_fixed_asset_accounts_flow_through.py` proves both claims directly,
independent of any scenario.

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
