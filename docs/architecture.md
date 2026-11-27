# Architecture

See `docs/plan.md` section 3 for the full directory layout and section 11
for the adapter contract. This document covers the pieces that are
actually implemented, progressively through Phase 6 as of this writing —
see "What's implemented vs. scaffolded" below for the phase-by-phase
breakdown.

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
shape -- reference-model output, a reviewed fixture, or a real adapter's
output (adapters/gnucash_xml, implemented as of Phase 6; adapters/saldima,
still not implemented -- see docs/accounting-policy.md) -- and produces a
comparison.schema.json result. runner/report.py renders that result as
text; runner/cli.py wires it all together.
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

Implemented (Phase 5 — partnership accounting; see `docs/plan.md`
section 18): `reference/tax/{liabilities,partnership_basis,
section_704c}.py`; no new event type (`fixed_asset_purchase` gained an
additive `contributed_capital_account_id` field, and `closing.py` gained
a `partner_allocations` alternative to `retained_earnings_account_id` —
see below); scenarios `PART-001` through `PART-004`
(`scenarios/partnerships/`), their reviewed fixtures, and the
corresponding unit/integration/invariant tests, including two dedicated
tax-schedule tests (`test_part_002_outside_basis.py`,
`test_part_003_section_704c.py`) mirroring `FA-003`'s pattern. Like
Phase 3 (and unlike Phase 4), this phase *did* require a real
`reference/accounting/*` change: `closing.close_period` gained an
alternative `partner_allocations` parameter to split net income/loss
across multiple partner capital accounts by ratio, instead of sweeping it
into one retained-earnings account — a small, additive change (confirmed
by rerunning all eleven pre-Phase-5 scenarios' fixtures unchanged) — see
`docs/reference-model.md`. `balance_sheet.py`/`trial_balance.py`/
`cash_flow.py` needed no changes (same "already generic" finding as every
prior phase, now for multiple equity accounts). **No**
`reference/tax/capital_accounts.py` exists — see
`docs/accounting-policy.md` for why.

Implemented (Phase 6 — compatibility and multi-book integration; see
`docs/plan.md` section 18): `adapters/gnucash_xml/{xml_format,
adapter}.py` — the first real `adapters/*` implementation, a
self-contained engine backed by GnuCash's own data model (not a live
Saldima driver; `adapters/saldima/` stays unimplemented, since no Saldima
engine had been connected to this repository — see
`adapters/saldima/README.md`) — and `reference/sync/merge.py`, a
new reference-model subpackage for multi-book branch merge semantics.
Scenario `GNC-001` (`tests/compatibility/test_gnc_001_round_trip.py`,
round-tripping the already-reviewed `FA-001` through real GnuCash v2
XML) and `SYNC-001`/`SYNC-002` (`tests/multi_book/`, the first two
scenarios validated by a dedicated test module instead of a
`scenarios/*.yaml` + reviewed-fixture pair). No change to any
`reference/accounting/*.py`, `reference/schedules/*.py`, or
`reference/tax/*.py` — see `docs/accounting-policy.md` for the two
documented, schema-conformant GnuCash round-trip conventions this phase
needed and the merge algorithm's conflict semantics.

Implemented (Phase 7 — scale and long-running regression; see
`docs/plan.md` section 18): `tests/property/` — Hypothesis-based
generalizations of the hand-built examples in `tests/invariants/
test_double_entry_invariants.py` (balanced postings, the accounting
equation, idempotent replay under posting-order reshuffles, cash-flow
reconciliation, `closing.py`'s partner-allocation remainder convention,
and the shared rounding-remainder convention across
`reference/schedules/{deferred_revenue,depreciation,debt}.py` and
`reference/tax/liabilities.py`, plus `reference/sync/merge.py`'s merge
semantics) over randomly generated inputs instead of one hand-picked
example each — see `docs/reference-model.md`'s "double-entry invariants,
numbered" section. `scripts/generate_synthetic_ledger.py` (a deterministic
large-ledger generator, reused by both the tests and the manual
benchmark) and `scripts/run_performance_benchmark.py` (times report
generation at 1,000 to 1,000,000 transactions, writing a baseline to
`reports/generated/performance-baseline.json` — a manual tool, not run by
`make test`, pending a Nightly CI stage per `docs/release-gates.md`);
`tests/performance/test_performance_smoke.py` exercises the same code
path at a small, fast scale on every `make test`. No new scenario and no
change to any existing scenario or fixture. This phase's one
`reference/accounting/*.py` change is a pure performance fix the
benchmark itself surfaced: `ledger.py`'s `Ledger.post` had an O(n)
duplicate-id scan, making posting `n` entries O(n²) overall (100,000+
transactions took over 1,000 CPU-seconds); it now tracks posted ids in a
set, with no change to observable behavior — see
`docs/reference-model.md`'s "Phase 7's performance baseline" section.
`tests/regression/` is intentionally still empty — see
`docs/release-gates.md`'s regression-scenario template.

Implemented (multi-entity accounting and consolidation — `MULTI-001`/
`MULTI-002`, docs/plan.md section 19; out-of-roadmap follow-on work
after Phase 7, not one of the 7 named phases): `reference/accounting/
consolidation.py` (new, additive — combines several already-closed
entities' books and eliminates intercompany balances/activity, reusing
the existing `TrialBalance`/`IncomeStatement`/`BalanceSheet` dataclasses
directly rather than inventing parallel "consolidated" types);
`runner/consolidation_runner.py` (a small, explicit registry of the two
known consolidation groups — entity file paths plus elimination pairs —
rather than a new scenario schema, since there are only ever two of
these planned); `scripts/generate_consolidated_expected.py`. Each entity
(`scenarios/multi-entity/multi-00{1,2}-{parent,subsidiary}.yaml`) is an
ordinary, independently-loadable scenario with its own reviewed fixtures,
loaded through the completely unmodified `runner/scenario_runner.py`/
`reference_runner.py` — no new event type, no schema change. The
consolidated statements get their own reviewed fixtures too
(`expected/reviewed/multi-00{1,2}-*/`). See `docs/accounting-policy.md`
for the consolidation scope boundaries (wholly-owned subsidiary, cost
method, no noncontrolling interest, fiscal-year-end-only, no consolidated
cash flow).

Implemented (`CORE-003`, cash and bank transactions / bank
reconciliation — docs/plan.md section 19; out-of-roadmap follow-on work,
closing out section 19's corpus entirely): `reference/accounting/
bank_reconciliation.py` (new, additive — the classic `book_balance ==
bank_statement_balance + deposits_in_transit - outstanding_checks`
identity, mirroring `cash_flow.py`'s own result-dataclass-plus-
`assert_reconciles()` shape). A new, optional `bank_reconciliations`
scenario block (`schemas/scenario.schema.json`) and
`runner/reference_runner.generate_bank_reconciliations` produce each
declared reconciliation as its own `reconciliation-<cash_account_id>-
<as_of>` "period" entry, reusing `runner/compare.py` and
`tests/integration/test_core_scenarios.py`'s existing comparison loop
completely unchanged. `CORE-003` also confirms (not just assumes) that
multiple cash accounts and a transfer between them already flow
correctly through `cash_flow.py`'s existing reconciliation with zero
`reference/accounting/*.py` changes beyond the new module above — see
`docs/accounting-policy.md`.

Partially implemented, environment-gated (`adapters/saldima/` — see
`docs/accounting-policy.md`'s "Saldima bridge" section for the full
writeup): `bridge.py` (NDJSON subprocess transport to `pnpm
accounting-bridge` in the sibling `saldima` repository's `packages/
gnucash`) and `adapter.py` (`SaldimaAdapter`, a real
`AccountingSystemAdapter` driving that actual engine) — the first
adapter in this repo validating against a genuinely different,
independently-built accounting engine, not just our own adapter code
against a file-format schema. Gated on the `SALDIMA_REPO_PATH`
environment variable, since this repo's CI never has the sibling repo
checked out; `tests/integration/test_saldima_bridge_cross_validation.py`
skips cleanly without it and runs real cross-engine validation with it
set. Scope boundaries this increment: aggregate-only balance sheet/
income statement (the real engine's reporting is still minimal), no
`apply_event`/closing-entry concept on the bridge (same honest no-op
pattern as `adapters/gnucash_xml`'s).

Scaffolded only (directory + README explaining what's planned, see
`docs/plan.md` section 18 for phases): `adapters/{csv,ofx,qfx}/`, every
scenario category besides `foundational/`, `accruals/`,
`revenue-recognition/`, `fixed-assets/`, `inventory/`, `debt/`,
`payroll/`, `partnerships/`, and `multi-entity/`, `datasets/*`, and the
`tests/regression` suite.
