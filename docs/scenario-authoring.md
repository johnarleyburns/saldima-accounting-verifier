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
  closings only (fiscal year == calendar year).
- `policies`, `rounding`: see `docs/accounting-policy.md`.

## Events

Two event types are implemented. Adding a new one means:

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
