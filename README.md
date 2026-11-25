# Saldima Accounting Validation

Independent accounting-correctness validation for Saldima and GnuCash
compatibility. **GitHub repository name:** `saldima-accounting-verifier`.
**Internal/package name:** `saldima-accounting-validation` (used in
`pyproject.toml`, module paths, and the rest of the docs in this repo).

The full engineering plan is in [`docs/plan.md`](docs/plan.md). Read that
first — this README only covers how to run what's here today.

**The most important rule in this repository:** the production accounting
engine under test must never be the authority for its own correctness. All
expected results come from an independent reference model, written here in
Python, that never imports or calls Saldima production code.

## Status

Phase 1 ("accounting foundation" — see `docs/plan.md` section 18) is
implemented: core double-entry bookkeeping, chart of accounts, journal
entries, trial balance, income statement, balance sheet, indirect-method
operating cash flow, and period-end closing, plus two reviewed
gold-standard scenarios (`CORE-001`, `CORE-002`) exercised across monthly,
mid-year, and annual reporting periods.

Everything else in the directory tree described in `docs/plan.md` section 3
is scaffolded (a directory and a README saying what's planned and which
phase it lands in) but not yet implemented. See `docs/architecture.md`
for the current implemented/scaffolded split and `docs/test-categories.md`
for test-suite status.

## Getting started

```bash
uv sync --all-extras
uv run pytest
uv run python -m runner.cli run --category foundational
```

See the [Makefile](Makefile) for the other common commands, and
`docs/scenario-authoring.md` for how to write a new scenario.

## Layout

See `docs/plan.md` section 3 for the full target layout and
`docs/architecture.md` for the data flow between `scenarios/` →
`reference/` → `runner/` → `expected/`.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md), and in particular
`docs/release-gates.md` for how `expected/reviewed/` fixtures are approved
— they are not something a test failure gets to silently update.

## License

AGPL-3.0, matching `johnarleyburns/saldima`.
