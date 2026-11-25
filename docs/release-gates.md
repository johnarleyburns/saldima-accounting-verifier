# Release Gates and Golden-Result Governance

## Golden result governance (docs/plan.md section 6.1)

`expected/generated/` holds reference-model output and may be regenerated
freely — it is never authoritative. `expected/reviewed/` holds approved
gold-standard fixtures and must only change through this process:

1. Create or modify a scenario under `scenarios/`.
2. Run the reference model (`uv run python -m runner.cli run --scenario
   <id>`, or the equivalent script) to produce `expected/generated/<id>/`.
3. Review the generated journal entries, trial balance, and financial
   statements by hand against the scenario's stated accounting treatment
   (and, where applicable, an authoritative source — see
   `docs/dataset-provenance.md`).
4. Have a second reviewer approve the output. (For the initial CORE-001/
   CORE-002 fixtures in this repository's first commits, the implementer
   performed and recorded this first-pass review themselves, noted in each
   `approval.json` — a second independent reviewer should still sign off
   before these are relied upon as a release gate.)
5. Copy the approved output into `expected/reviewed/<id>/<period>/`,
   alongside an `approval.json` recording scenario version, reference-model
   state, framework/policies, review date, reviewer, and notes.
6. Commit the scenario and the reviewed fixture together.

A reference-model change must never silently overwrite `expected/reviewed/`
— regenerate into `expected/generated/`, diff, and go through review again
if the approved numbers need to change.

## Release gate (docs/plan.md section 20)

No accounting-engine release is production-ready if:

1. Any approved core scenario fails.
2. Any posted journal entry is unbalanced.
3. Any trial balance fails to balance.
4. Any balance sheet fails the accounting equation.
5. Any historical reporting period changes unexpectedly.
6. Any multi-book operation creates cross-book contamination.
7. Any reconciliation operation silently discards valid accounting data.
8. Any financial discrepancy is unresolved or incorrectly waived.

## CI stages (docs/plan.md section 17)

- **Pull request:** schema validation, unit tests, core accounting
  scenarios, accounting invariants, type checking and linting.
- **Main branch:** complete deterministic scenario suite, multi-period
  tests, (once implemented) GnuCash compatibility tests.
- **Nightly:** property-based tests, large generated ledgers, performance
  benchmarks, extended multi-year scenarios (once implemented).
- **Release candidate:** all approved gold-standard scenarios, full
  compatibility and regression suites, no unexplained discrepancies.

This repository's current `.github/workflows/ci.yml` implements the
pull-request stage only (schema validation + pytest + ruff). The later
stages are added as the corresponding test categories are implemented
(see `docs/test-categories.md`).

## Regression scenarios (docs/plan.md section 21)

Every production accounting defect found should produce a permanent
regression scenario under `scenarios/<category>/` (or a dedicated
`tests/regression/` case for a defect that isn't naturally a full
scenario), following the template in `docs/plan.md` section 21: state the
bug, the correct expected behavior, and the regression scenario/test id.
