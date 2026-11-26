# Test Categories

| Directory | Purpose | Status |
|---|---|---|
| `tests/unit` | Pure-function tests of `reference/accounting/*` modules | Implemented |
| `tests/invariants` | Core double-entry invariants (docs/plan.md section 13, items 1–3) | Implemented (subset) |
| `tests/integration` | End-to-end: load a scenario, run the reference model, compare to its reviewed fixtures | Implemented (CORE-001/002, ACCR-001/002, REV-001/002, FA-001/002/003, INV-001/002, DEBT-001, PAY-001, PART-001/002/003/004) |
| `tests/property` | Hypothesis-based randomized invariant testing across generated books | Implemented (balanced-ledger, accounting-equation, idempotent-replay, cash-flow-reconciliation, closing-allocation, rounding-remainder, and merge invariants — see docs/reference-model.md's "double-entry invariants, numbered" section) |
| `tests/regression` | One test per fixed accounting defect, kept forever (docs/plan.md section 21) | Planned (still empty — no production accounting defect has occurred in this repository's history; see docs/release-gates.md's regression-scenario template for what goes here when one does) |
| `tests/compatibility` | GnuCash XML semantic round-trip tests | Implemented (GNC-001) |
| `tests/multi_period` | Multi-year carryforward, fiscal-year-boundary, prior-period-adjustment tests | Implemented (partial — multi-year closing carryforward via ACCR-002's two fiscal years; CORE-002's single-year cycle is still covered under `tests/integration`) |
| `tests/multi_book` | Multi-book isolation and merge/reconciliation semantics (docs/plan.md section 14) | Implemented (SYNC-001/002) |
| `tests/performance` | Generated-book-size benchmarks and regression thresholds | Implemented (smoke-tested at a small scale on every `make test`; the full 1,000-1,000,000-transaction benchmark is a manual script, `scripts/run_performance_benchmark.py`, pending a Nightly CI stage — see docs/release-gates.md) |

See `docs/plan.md` sections 13–15 for what each category is meant to cover
in full, and section 18 for the phase each lands in.
