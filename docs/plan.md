# Saldima Accounting Validation Repository — Engineering Plan

**Status:** Proposed
**Priority:** Foundational infrastructure
**GitHub repository:** `johnarleyburns/saldima-accounting-verifier`
**Internal/package name:** `saldima-accounting-validation` (used for the Python package, CLI module paths, and docs below — kept distinct from the GitHub repo name at the author's direction)
**Purpose:** Independently validate accounting correctness, multi-period financial reporting, GnuCash compatibility, and tax-accounting schedules across Saldima implementations.

---

## 1. Executive Summary

Saldima will maintain a separate accounting validation repository containing reproducible business scenarios, reference accounting calculations, authoritative expected results, real-world datasets, and automated test runners.

The repository will serve as an independent correctness benchmark for the Saldima accounting engine.

Its purpose is not merely to verify that transactions balance. It must establish that business events produce the correct accounting treatment, that financial statements are correct across multiple reporting periods, and that balances and supporting schedules remain correct through years of business activity.

The repository will validate:

1. Double-entry bookkeeping.
2. General ledger and chart-of-accounts behavior.
3. Monthly, quarterly, and annual trial balances.
4. Income statements.
5. Balance sheets.
6. Statements of cash flows.
7. Period closing and opening balances.
8. Accrual and cash accounting behavior.
9. Revenue recognition and deferred revenue.
10. Fixed assets and depreciation.
11. Inventory and cost of goods sold.
12. Debt and interest amortization.
13. Payroll and tax liabilities.
14. Partnership capital accounts and outside tax basis.
15. Multi-entity accounting and consolidation.
16. GnuCash XML import/export compatibility.
17. Multi-book isolation and reconciliation.
18. Long-running, multi-year accounting integrity.

The repository must be independently executable. It must not require a running Saldima server, cloud account, database, or user interface.

The same test scenarios should be usable against:

- The reference accounting model.
- The Saldima TypeScript accounting engine.
- The mobile accounting implementation.
- GnuCash XML import/export adapters.
- Future accounting-engine implementations.

The repository will establish a release gate: changes to accounting logic cannot be accepted until the relevant validation suites pass.

## 2. Core Design Principles

### 2.1 Independent reference implementation

The validation system must not use Saldima's production accounting code to calculate expected results.

Otherwise, the same defect could exist in both the accounting engine and the expected-result generator.

The reference implementation will be written independently, preferably in Python.

It should favor:
- Explicit formulas.
- Small, understandable functions.
- Decimal arithmetic.
- Clear accounting assumptions.
- Human-reviewable calculations.
- Deterministic output.

The reference model is not intended to become a second production accounting engine. It exists to establish expected accounting results.

### 2.2 Business events are the primary input

Tests should describe what happened in a business, not only the journal entries that should have been generated.

For example:

```yaml
event_id: contract-001
event_type: customer_contract_payment
date: 2026-01-01

customer: customer-001
amount: "12000.00"
currency: USD

contract:
  service_start: 2026-01-01
  service_end: 2026-12-31
  recognition_method: straight_line
```

The accounting engine should translate this event into journal entries.

The validation harness independently determines the expected entries and financial results.

This allows the same scenario to test transaction processing, accounting rules, and financial statement generation.

### 2.3 Deterministic and reproducible

Every scenario must produce identical results when executed repeatedly using the same:
- Scenario inputs.
- Accounting policies.
- Fiscal calendar.
- Currency configuration.
- Reference implementation version.
- Rounding rules.

No random transaction generation should occur during a deterministic test run.

Randomized tests are permitted in a separate property-testing suite, with recorded seeds.

### 2.4 Accounting assumptions must be explicit

Every scenario must specify its accounting basis and relevant policies.

Examples:

```yaml
accounting:
  basis: accrual
  framework: US_GAAP
  functional_currency: USD
  fiscal_year_end: "12-31"

rounding:
  currency_precision: 2
  method: HALF_UP

policies:
  inventory: FIFO
  depreciation: straight_line
  revenue_recognition: over_time
```

Do not silently assume that every accounting scenario uses the same accounting framework or tax treatment.

US GAAP, IFRS, cash-basis accounting, tax accounting, and management accounting must be distinguishable.

## 3. Repository Architecture

```text
saldima-accounting-verifier/
│
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── pyproject.toml
├── Makefile
│
├── schemas/
│   ├── scenario.schema.json
│   ├── event.schema.json
│   ├── account.schema.json
│   ├── journal-entry.schema.json
│   ├── financial-statement.schema.json
│   ├── schedule.schema.json
│   └── comparison.schema.json
│
├── scenarios/
│   ├── foundational/
│   ├── accounting-cycle/
│   ├── accruals/
│   ├── revenue-recognition/
│   ├── fixed-assets/
│   ├── inventory/
│   ├── debt/
│   ├── payroll/
│   ├── partnerships/
│   ├── multi-entity/
│   ├── foreign-currency/
│   └── long-running/
│
├── reference/
│   ├── accounting/
│   │   ├── journal.py
│   │   ├── ledger.py
│   │   ├── trial_balance.py
│   │   ├── income_statement.py
│   │   ├── balance_sheet.py
│   │   ├── cash_flow.py
│   │   ├── closing.py
│   │   └── rounding.py
│   │
│   ├── schedules/
│   │   ├── depreciation.py
│   │   ├── deferred_revenue.py
│   │   ├── receivables.py
│   │   ├── payables.py
│   │   ├── inventory.py
│   │   └── debt.py
│   │
│   ├── tax/
│   │   ├── macrs.py
│   │   ├── partnership_basis.py
│   │   ├── capital_accounts.py
│   │   ├── liabilities.py
│   │   └── section_704c.py
│   │
│   └── reporting/
│       ├── statements.py
│       └── schedules.py
│
├── expected/
│   ├── generated/
│   └── reviewed/
│
├── datasets/
│   ├── academic/
│   ├── public_filings/
│   ├── synthetic/
│   └── imported/
│
├── adapters/
│   ├── saldima/
│   ├── gnucash_xml/
│   ├── csv/
│   ├── ofx/
│   └── qfx/
│
├── runner/
│   ├── scenario_runner.py
│   ├── reference_runner.py
│   ├── system_runner.py
│   ├── compare.py
│   ├── report.py
│   └── cli.py
│
├── tests/
│   ├── invariants/
│   ├── unit/
│   ├── integration/
│   ├── property/
│   ├── regression/
│   ├── compatibility/
│   ├── multi_period/
│   └── performance/
│
├── reports/
│   ├── templates/
│   └── generated/
│
└── docs/
    ├── architecture.md
    ├── scenario-authoring.md
    ├── accounting-policy.md
    ├── reference-model.md
    ├── dataset-provenance.md
    ├── test-categories.md
    └── release-gates.md
```

The directory structure should be extensible without requiring all accounting features to be implemented initially.

## 4. Technology Stack

| Purpose | Library |
|---|---|
| Runtime | Python 3.12+ |
| Test framework | pytest |
| Decimal calculations | Python `decimal` |
| Schema validation | Pydantic |
| JSON Schema validation | jsonschema |
| Property-based testing | Hypothesis |
| Tabular data analysis | pandas |
| Numerical analysis | NumPy, only where appropriate |
| Data fixtures | YAML and JSON |
| CLI | Typer |
| Reporting | pytest reports and custom JSON/HTML |
| Coverage | coverage.py |
| Static typing | mypy or pyright |
| Formatting/linting | Ruff |

Do not use floating-point values for monetary calculations. All monetary inputs and expected amounts are represented as decimal strings in fixture files and converted into `Decimal` values (`Decimal("1234.56")`, never `Decimal(1234.56)`).

## 5. Scenario Definition Format

Scenarios use YAML for human authoring and JSON-compatible normalized objects internally. Each scenario represents a complete fictional business or a focused accounting problem. See `docs/scenario-authoring.md` for the full schema and examples.

## 6. Expected Results and Gold-Standard Fixtures

Each scenario has expected results at defined reporting dates, split into `expected/generated/` (reference-model output, regenerable) and `expected/reviewed/` (approved gold-standard fixtures, never silently overwritten). See `docs/release-gates.md` for the approval workflow.

## 7. Accounting Validation Modules

Implemented progressively: core double-entry accounting → financial statements → accruals/deferrals → revenue recognition → fixed assets/depreciation → inventory → debt/interest → payroll → partnership accounting/tax basis → multi-entity accounting. See section 18 (roadmap) below and `docs/test-categories.md`.

## 8. Multi-Period and Multi-Year Scenarios

A scenario is not complete simply because its final balance sheet is correct — intermediate reporting periods (monthly, quarterly, annual) must all be verified, and a later period must never conceal an error in an earlier one.

## 9. Reference Data and External Datasets

Combines authoritative worked examples with real-world and synthetic datasets (DFKI/Saarland synthetic GL dataset, SEC EDGAR XBRL, IRS publications 946/541, synthetic generators), each with documented provenance and purpose, per `docs/dataset-provenance.md`. None of these are treated as a complete accounting-correctness oracle on their own.

## 10. GnuCash Compatibility Testing

GnuCash XML is Saldima's canonical native book format. Compatibility tests round-trip real GnuCash XML fixtures through the Saldima import/export adapters and compare semantic equivalence (GUIDs, dates, amounts, relationships, reconciliation status) — not byte-for-byte XML equality.

## 11. Saldima System Adapter

A narrow `AccountingSystemAdapter` contract (see `adapters/saldima/`) lets the suite drive an actual Saldima engine without ever using that engine to calculate expected results.

## 12. Comparison Engine

Compares actual system output against approved expected output at exact currency precision — no floating-point tolerances — and reports the first meaningful discrepancy plus related downstream discrepancies.

## 13. Invariant and Property-Based Testing

Hypothesis-based property tests enforce accounting invariants (balanced entries, trial balance balances, accounting equation, idempotent replay, immutable history, etc.) across randomly generated valid books, with every failing seed recorded for reproduction.

## 14. Multi-Book Isolation and Reconciliation Testing

Validates book isolation and multi-device merge/reconciliation scenarios at the accounting-semantics level, without duplicating the production cryptographic/sync implementation.

## 15. Performance and Scale Testing

Generated books from 1,000 to 1,000,000 transactions, with performance baselines tracked over time before any regression thresholds are introduced.

## 16. CLI and Developer Workflow

A Typer-based CLI (`runner/cli.py`) runs scenario categories, individual scenarios, system/compatibility validation, and generates reports, without requiring all external datasets to be downloaded.

## 17. CI/CD Integration

Pull-request, main-branch, nightly, and release-candidate CI stages of increasing scope, per `docs/release-gates.md`. Changes to expected output always require separate review.

## 18. Test Scenario Roadmap

- **Phase 1 — Accounting foundation:** chart of accounts, journal entries, double-entry balancing, opening balances, trial balance, income statement, balance sheet, cash flow statement, closing entries.
- **Phase 2 — Normal business accounting:** AR/AP, accruals, prepayments, deferred revenue, recurring transactions, expense allocations.
- **Phase 3 — Fixed assets and inventory:** depreciation, disposals, inventory valuation, COGS, write-downs.
- **Phase 4 — Debt and payroll:** loan schedules, interest, payroll accruals/liabilities/taxes.
- **Phase 5 — Partnership accounting:** capital accounts, contributions, distributions, allocations, outside basis, 704(b)/704(c)/743(b).
- **Phase 6 — Compatibility and multi-book integration:** GnuCash XML fixtures, semantic round-trips, multi-book isolation, multi-device merge.
- **Phase 7 — Scale and long-running regression:** large datasets, million-transaction stress tests, extended multi-year simulations, performance regression tracking, randomized property tests.

This repository's first commits implement **Phase 1** end-to-end (working reference accounting core plus two fully worked gold-standard scenarios) and scaffold every later phase's directories and interfaces so they can be filled in incrementally. **Phase 2** (AR/AP, accruals, prepayments, deferred revenue) is implemented next, with four more gold-standard scenarios (ACCR-001/002, REV-001/002). **Phase 3** (fixed assets and inventory) follows, with five more (FA-001/002/003, INV-001/002). **Phase 4** (debt and payroll) follows that, with two more (DEBT-001, PAY-001) — see section 19 and `docs/architecture.md`.

## 19. Initial Gold-Standard Scenario Corpus

| ID | Scenario | Duration | Primary validation | Status |
|---|---|---:|---|---|
| CORE-001 | Initial balances and opening entries | 1 month | Opening balances | Implemented |
| CORE-002 | Basic service business | 1 year | Accounting cycle | Implemented |
| CORE-003 | Cash and bank transactions | 1 year | Cash and reconciliation | Planned |
| ACCR-001 | Accrued payroll and utilities | 1 year | Accruals | Implemented |
| ACCR-002 | Prepaid insurance and rent | 2 years | Prepayments | Implemented |
| REV-001 | Advance service contract | 1 year | Deferred revenue | Implemented |
| REV-002 | Multiple performance obligations | 2 years | Revenue recognition | Implemented |
| FA-001 | Straight-line equipment depreciation | 5 years | Depreciation | Implemented |
| FA-002 | Asset disposal | 5 years | Gain/loss on disposal | Implemented |
| FA-003 | Tax versus book depreciation | 5 years | MACRS and book schedules | Implemented |
| INV-001 | FIFO retail inventory | 2 years | Inventory and COGS | Implemented |
| INV-002 | Inventory write-down | 2 years | Valuation | Implemented |
| DEBT-001 | Fixed-rate business loan | 5 years | Debt and interest | Implemented |
| PAY-001 | Payroll and withholding | 1 year | Payroll liabilities | Implemented |
| PART-001 | Two-partner formation | 2 years | Capital accounts | Planned |
| PART-002 | Partnership debt and outside basis | 5 years | Tax basis | Planned |
| PART-003 | Property contribution and 704(c) | 5 years | Built-in gain/loss | Planned |
| PART-004 | Partnership liquidation | 10 years | Final basis and distributions | Planned |
| MULTI-001 | Intercompany transactions | 2 years | Consolidation | Planned |
| MULTI-002 | Multi-entity reporting | 5 years | Consolidated statements | Planned |
| SYNC-001 | Concurrent independent transactions | Multiple branches | Reconciliation | Planned |
| SYNC-002 | Conflicting transaction edits | Multiple branches | Conflict preservation | Planned |
| GNC-001 | GnuCash XML round trip | Multiple years | Compatibility | Planned |

## 20. Quality and Acceptance Criteria / Release Gate

See `docs/release-gates.md` for the full list. In summary: no accounting engine release is production-ready if any approved core scenario fails, any posted journal entry or trial balance is unbalanced, any balance sheet fails the accounting equation, any historical reporting period changes unexpectedly, any multi-book operation cross-contaminates, any reconciliation silently discards valid data, or any financial discrepancy is unresolved or incorrectly waived.

## 21. Governance and Maintenance

Every production accounting defect should produce a permanent regression scenario whenever practical (see `docs/release-gates.md` for the regression-scenario template).

## 22. Scope Boundaries

This repository does not replace the Saldima accounting engine, does not become a production tax-preparation application, does not independently certify GAAP/IFRS compliance, does not replace a CPA's review or legal/tax advice, and does not treat synthetic data or SEC XBRL facts as transaction-level ground truth. Each scenario states what it validates and what it does not. Tax calculations are labeled by jurisdiction and tax year.

## 23. Long-Term Strategic Value

Accounting correctness, GnuCash compatibility, regression protection, portability across implementations, auditability, and release confidence — this repository is intended to become Saldima's internal accounting conformance benchmark.

## 24. Final Architectural Decision

Adopt this repository as a separate, independently maintained validation system using Python, YAML/JSON scenarios, Decimal arithmetic, pytest/Hypothesis, independently reviewed gold-standard fixtures, a narrow production-engine adapter, and separate validation modules for financial accounting, tax accounting, GnuCash compatibility, and multi-book reconciliation.

**Most important rule: the production accounting engine must never be the authority for its own correctness.** This repository provides that independent authority through reproducible scenarios, explicit accounting assumptions, independently calculated expected results, and permanent regression tests.
