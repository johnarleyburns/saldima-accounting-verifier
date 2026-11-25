# Test Categories

| Directory | Purpose | Status |
|---|---|---|
| `tests/unit` | Pure-function tests of `reference/accounting/*` modules | Implemented |
| `tests/invariants` | Core double-entry invariants (docs/plan.md section 13, items 1–3) | Implemented (subset) |
| `tests/integration` | End-to-end: load a scenario, run the reference model, compare to its reviewed fixtures | Implemented (CORE-001, CORE-002) |
| `tests/property` | Hypothesis-based randomized invariant testing across generated books | Planned (Phase 7) |
| `tests/regression` | One test per fixed accounting defect, kept forever (docs/plan.md section 21) | Planned (empty until the first defect is fixed) |
| `tests/compatibility` | GnuCash XML semantic round-trip tests | Planned (Phase 6) |
| `tests/multi_period` | Multi-year carryforward, fiscal-year-boundary, prior-period-adjustment tests | Planned (Phase 2+; CORE-002 is a partial start, covered under `tests/integration`) |
| `tests/performance` | Generated-book-size benchmarks and regression thresholds | Planned (Phase 7) |

See `docs/plan.md` sections 13–15 for what each category is meant to cover
in full, and section 18 for the phase each lands in.
