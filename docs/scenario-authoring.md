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

## Events (Phase 1 scope)

Only `type: manual_journal_entry` is implemented: the scenario author
supplies explicit `lines` (account_id + debit/credit). This is intentional
-- see `docs/plan.md` section 2.2. Higher-level business events (e.g.
`customer_contract_payment`, where the *engine under test* must derive the
journal entries) arrive with the scenario categories that need them
(Phase 2+). Adding a new event type means:

1. Add it to `schemas/event.schema.json`.
2. Teach `runner/scenario_runner.py` how to translate it into a
   `JournalEntry` for the reference-model run (the reference model's
   translation becomes part of what defines the "expected" treatment).
3. Document the accounting policy it depends on in
   `docs/accounting-policy.md`.

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
