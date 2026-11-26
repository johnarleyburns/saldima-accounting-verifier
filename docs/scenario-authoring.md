# Scenario Authoring

A scenario is a YAML file under `scenarios/<category>/<id>.yaml`, validated
against `schemas/scenario.schema.json`. See `scenarios/foundational/
core-002-basic-service-business.yaml` for a fully worked example.

## Required top-level fields

- `id`, `name`, `version`, `category`, `accounting` (framework/basis/
  currency/fiscal_year_end), `start_date`, `end_date`, `accounts`, `events`,
  `expected.reports`.

## Optional fields

- `opening_balances`: a list of `{account_id, debit, credit}` lines posted
  together as a single balanced journal entry dated `start_date`.
- `cash_accounts`: account ids treated as cash for cash-flow reporting.
- `closing`: `{retained_earnings_account, dates}` — fiscal-year-end closing
  entries to post before generating reports. Phase 1 supports calendar-year
  closings only (fiscal year == calendar year). As an alternative to
  `retained_earnings_account` (Phase 5), pass `partner_allocations:
  {account_id: "ratio_string"}` instead — one entry per partner capital
  account, ratios summing to exactly `"1.00"` — to split each closing's net
  income/loss across multiple accounts by ratio. Exactly one of
  `retained_earnings_account`/`partner_allocations` must be given. See
  `docs/accounting-policy.md`.
- `policies`, `rounding`: see `docs/accounting-policy.md`.

Per-account (under `accounts[]`): `cash_flow_category`
(`operating`/`investing`/`financing`, default `operating`) — see
`docs/accounting-policy.md`.

## Events

Seven event types are implemented (Phase 5 added none — see below).
Adding a new one means:

1. Add it to `schemas/event.schema.json`.
2. Teach `runner/scenario_runner.py` how to translate it into
   `JournalEntry`/`JournalEntry`s for the reference-model run (the
   reference model's translation becomes part of what defines the
   "expected" treatment).
3. Document the accounting policy it depends on in
   `docs/accounting-policy.md`.

### `manual_journal_entry` (Phase 1)

The scenario author supplies explicit `lines` (`account_id` +
`debit`/`credit`); the reference model just posts them as a single
`JournalEntry` dated `date`. See `docs/plan.md` section 2.2 for why this
stayed the only event type through Phase 1, and `docs/accounting-policy.md`
for why accruals and prepayments (`ACCR-001`, `ACCR-002`) still use it in
Phase 2.

### `customer_contract_payment` (Phase 2)

The first higher-level event type: the scenario author describes the
business fact (a customer paid for a contract covering one or more
performance obligations, each with its own recognition method), and the
reference model derives the deferred-revenue liability and every
recognition entry itself (`runner/scenario_runner.py`'s
`_translate_customer_contract_payment`, using
`reference/schedules/deferred_revenue.py` for the straight-line schedule
math). See `docs/accounting-policy.md`'s "Event model: Phase 1 vs Phase 2"
for the rationale.

Fields: `customer` (free text), `cash_account_id`, `deferred_revenue_
account_id`, and `obligations` — a list of `{id, amount, revenue_account_id,
recognition_method, ...}`, one per performance obligation funded by this
payment. `recognition_method: point_in_time` additionally requires
`recognition_date`; `recognition_method: straight_line` additionally
requires `service_start`/`service_end`, which must be the first and last
day of their respective months (partial-month proration isn't implemented
yet). The sum of `obligations[].amount` is the total cash received. See
`scenarios/revenue-recognition/rev-001-advance-service-contract.yaml` for a
single-obligation example and
`scenarios/revenue-recognition/rev-002-multiple-performance-obligations.yaml`
for one contract allocated across a `point_in_time` and a `straight_line`
obligation.

### `fixed_asset_purchase` (Phase 3)

The scenario author states the asset's cost/salvage/useful-life policy;
the reference model derives the purchase entry and the full monthly
straight-line depreciation schedule itself
(`reference/schedules/depreciation.py`).

Fields: `asset_id` (links a later `fixed_asset_disposal` to this asset),
`asset_account_id`, `accumulated_depreciation_account_id`,
`depreciation_expense_account_id`, `cost`, `salvage_value`,
`useful_life_months` (the purchase `date` is the in-service date, and
must be the first day of its month), and exactly one of `cash_account_id`
(a cash purchase) or `contributed_capital_account_id` (Phase 5: a partner
contributing the asset itself, at fair market value, credited to their
capital account instead of debiting cash — see
`scenarios/partnerships/part-003-property-contribution-704c.yaml`). If a
`fixed_asset_disposal` for the same `asset_id` exists anywhere in the
scenario's `events`, the depreciation schedule stops at the last full
month on or before the disposal date instead of running the full
`useful_life_months`. `accumulated_depreciation_account_id` should be
declared `type: asset` in `accounts[]` (a contra-asset — see
`docs/accounting-policy.md`), and `asset_account_id` should set
`cash_flow_category: investing` so the purchase shows as investing
activity rather than operating.

### `fixed_asset_disposal` (Phase 3)

Fields: `asset_id` (matching a `fixed_asset_purchase` elsewhere in the
scenario), `proceeds`, `cash_account_id`, `gain_account_id` (a
`revenue`-type account), `loss_account_id` (an `expense`-type account).
The reference model computes accumulated depreciation and book value at
the disposal date from the matching purchase event's own declared
cost/salvage/useful-life (no ledger lookups) and posts one entry: debit
cash for `proceeds`, debit the accumulated-depreciation account to clear
it, credit the asset account to remove its cost, and plug the gain or
loss. See `scenarios/fixed-assets/fa-002-asset-disposal.yaml` for both
directions (one disposal at a gain, one at a loss).

### `inventory_purchase` / `inventory_sale` (Phase 3)

`inventory_purchase` fields: `inventory_account_id`, `cash_account_id`,
`quantity`, `unit_cost`. Posts one entry (debit inventory, credit cash)
and records a new FIFO lot.

`inventory_sale` fields: `inventory_account_id`, `cogs_account_id`,
`revenue_account_id`, `cash_account_id`, `quantity`, `unit_price`. The
sale/revenue dollar total is plain multiplication, but the cost of goods
sold is derived by consuming FIFO lots oldest-first
(`reference/schedules/inventory.py`) from the running list of open lots
for that `inventory_account_id`, built up by every prior
`inventory_purchase` in the scenario's `events` — which means, unlike
every other event type, `inventory_purchase`/`inventory_sale` events for
the same account **must be authored in chronological order** in the YAML
(the existing convention for every scenario's events, just load-bearing
here specifically). Raises `AccountingError` if a sale's quantity exceeds
what's on hand. See `scenarios/inventory/inv-001-fifo-retail.yaml`.

A **write-down** (`INV-002`) is not a separate event type — it's a plain
`manual_journal_entry` (debit a write-down expense account, credit
inventory), since the write-down amount is a stated business judgment,
not something derived from a schedule.

### `loan_origination` (Phase 4)

Fields: `cash_account_id`, `loan_payable_account_id`,
`interest_expense_account_id`, `principal`, `annual_interest_rate` (a
decimal fraction, e.g. `"0.06"` for 6%), `term_months` (the event `date`
is the origination date, first day of its month). Models an
equal-principal, declining-interest loan — the reference model derives
the equal monthly principal payment (`principal / term_months`, remainder
in the last month — the same convention as `fixed_asset_purchase`) and
each month's interest (that month's *remaining* balance times the
monthly rate, rounded) itself, via
`reference/schedules/debt.py`'s `build_amortization_schedule`. Posts one
origination entry (debit cash, credit the loan payable, for `principal`)
and one payment entry per month for the full `term_months` (debit
interest expense and the loan payable's principal portion, credit cash
for the sum). `loan_payable_account_id` should be declared `type:
liability` with `cash_flow_category: financing` in `accounts[]` — see
`docs/accounting-policy.md`. No early-payoff/disposal counterpart exists
yet (not needed by `DEBT-001`); the schedule always runs the full
`term_months`.

**Payroll (`PAY-001`) is not a new event type** — gross pay, every
withholding amount, and the employer's matching payroll tax are all
stated business facts with no schedule to derive, so it's
`manual_journal_entry` throughout. See
`scenarios/payroll/pay-001-payroll-and-withholding.yaml` for the
one-month accrual/remittance-lag pattern (the same shape as
`ACCR-001`'s accrued-liability lag).

### Partnership scenarios (Phase 5): no new event type

`PART-001` through `PART-004` introduce no new event type at all — see
"`closing.partner_allocations`" above for the one scenario-level addition,
and `fixed_asset_purchase`'s `contributed_capital_account_id` above for
the other. Partner contributions, withdrawals, and liquidating
distributions are all `manual_journal_entry`; a partnership-level loan is
an ordinary `loan_origination`. See `docs/accounting-policy.md`'s "Reusing
Phase 2-4 event types for partnership scenarios" for the full rationale,
and `reference/tax/{liabilities,partnership_basis,section_704c}.py` for
the outside-basis/section-704(c) tax schedules `PART-002`/`PART-003`
validate separately (never posted to any ledger).

## Reporting periods

`expected.reports[].period` strings are parsed by `runner/period.py`:
`"YYYY-MM"` (calendar month), `"YYYY-QN"` (calendar quarter), `"YYYY"` or
`"YYYY-FY"` (full calendar year). Request enough periods to exercise
monthly, quarterly, and annual cadence per `docs/plan.md` section 8 --
don't rely solely on the final period's balance sheet being correct.

## Expected results

Scenarios don't embed expected numbers inline. After writing a scenario,
run it through the reference model and go through the review process in
`docs/release-gates.md` to produce `expected/reviewed/<scenario_id>/
<period>/{trial_balance,income_statement,balance_sheet,cash_flow}.json`.
