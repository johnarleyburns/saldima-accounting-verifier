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

Scaffolded only (directory + README explaining what's planned, see
`docs/plan.md` section 18 for phases): `reference/schedules/{depreciation,
inventory,debt}.py`, `reference/tax/`, every `adapters/*` implementation,
every scenario category besides `foundational/`, `accruals/`, and
`revenue-recognition/`, `datasets/*`, and the `property`, `regression`,
`compatibility`, and `performance` test suites.
