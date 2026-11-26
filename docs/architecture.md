# Architecture

See `docs/plan.md` section 3 for the full directory layout and section 11
for the adapter contract. This document covers the pieces that are actually
implemented as of Phase 1.

## Data flow

```
scenarios/*.yaml
      │  (runner/scenario_runner.py: load + jsonschema-validate)
      ▼
ChartOfAccounts + Ledger  (reference/accounting/journal.py, ledger.py)
      │  (runner/reference_runner.py)
      ▼
per-period reports: trial balance, income statement, balance sheet,
cash flow  (reference/accounting/{trial_balance,income_statement,
balance_sheet,cash_flow}.py, normalized by reference/reporting/statements.py)
      │
      ├──► expected/generated/  (regenerable, not authoritative)
      │
      └──► expected/reviewed/   (approved gold-standard fixtures, see
                                  docs/release-gates.md section "Golden
                                  result governance")

runner/compare.py compares *any* two normalized statement dicts in the same
shape -- reference-model output, a reviewed fixture, or (once implemented)
a real adapters/saldima or adapters/gnucash_xml adapter's output -- and
produces a comparison.schema.json result. runner/report.py renders that
result as text; runner/cli.py wires it all together.
```

## Independence boundary

`reference/` must never import anything from `adapters/`, and `adapters/`
must never be used to calculate expected results (docs/plan.md section
2.1). The only thing allowed to compare the two is `runner/compare.py`,
which treats both sides as opaque normalized dicts.

## What's implemented vs. scaffolded

Implemented (Phase 1): `reference/accounting/*`, `runner/*`,
`schemas/{scenario,event,account,journal-entry}.schema.json`, scenarios
CORE-001 and CORE-002, their reviewed fixtures, and the corresponding unit/
integration/invariant tests.

Implemented (Phase 2 — AR/AP, accruals, prepayments, deferred revenue; see
`docs/plan.md` section 18): `reference/schedules/{receivables,payables,
deferred_revenue}.py`; the `customer_contract_payment` event type
(`runner/scenario_runner.py`, `schemas/event.schema.json`); scenarios
`ACCR-001`/`ACCR-002` (`scenarios/accruals/`) and `REV-001`/`REV-002`
(`scenarios/revenue-recognition/`), their reviewed fixtures, and the
corresponding unit/integration/invariant tests; `tests/multi_period`
(partial — multi-year closing carryforward, via ACCR-002's two fiscal-year
closings). No Phase 2 code changes were needed in
`reference/accounting/*` — see `docs/reference-model.md` and
`docs/accounting-policy.md` for why it was already generic enough.

Implemented (Phase 3 — fixed assets and inventory; see `docs/plan.md`
section 18): `reference/schedules/{depreciation,inventory}.py`,
`reference/tax/macrs.py`; four new event types (`fixed_asset_purchase`,
`fixed_asset_disposal`, `inventory_purchase`, `inventory_sale` —
`runner/scenario_runner.py`, `schemas/event.schema.json`); scenarios
`FA-001`/`FA-002`/`FA-003` (`scenarios/fixed-assets/`) and `INV-001`/
`INV-002` (`scenarios/inventory/`), their reviewed fixtures, and the
corresponding unit/integration/invariant tests. Unlike Phase 2, this phase
*did* require a small, additive change to Phase 1 code: `Account` gained
an optional `cash_flow_category` field (default `operating`, so Phase 1/2
scenarios' output is byte-for-byte unchanged) and `cash_flow.py` now
classifies by it into operating/investing/financing sections instead of
one — see `docs/reference-model.md`'s "Phase 3 adds investing/financing
classification" section. `reference/accounting/{trial_balance,
income_statement,balance_sheet,closing}.py` needed no changes (same
"already generic" finding as Phase 2, now for contra-assets and gain/loss
accounts too).

Implemented (Phase 4 — debt and payroll; see `docs/plan.md` section 18):
`reference/schedules/debt.py`; the `loan_origination` event type
(`runner/scenario_runner.py`, `schemas/event.schema.json`); scenarios
`DEBT-001` (`scenarios/debt/`) and `PAY-001` (`scenarios/payroll/`),
their reviewed fixtures, and the corresponding unit/integration/invariant
tests. Like Phase 2 (and unlike Phase 3), no `reference/accounting/*`
changes were needed at all: Phase 3's `cash_flow_category` mechanism was
already general enough to classify a liability (the loan payable, tagged
`financing`) with zero further code — see `docs/reference-model.md`.
`reference/schedules/` is now fully implemented (`deferred_revenue`,
`receivables`, `payables`, `depreciation`, `inventory`, `debt` — every
file the directory's README originally listed).

Scaffolded only (directory + README explaining what's planned, see
`docs/plan.md` section 18 for phases): `reference/tax/{partnership_basis,
capital_accounts,liabilities,section_704c}.py`, every `adapters/*`
implementation, every scenario category besides `foundational/`,
`accruals/`, `revenue-recognition/`, `fixed-assets/`, `inventory/`,
`debt/`, and `payroll/`, `datasets/*`, and the `property`, `regression`,
`compatibility`, and `performance` test suites.
