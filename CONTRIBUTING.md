# Contributing

## Ground rules

- `reference/` is the independent accounting authority. It must never
  import from `adapters/`, and nothing in it may be derived from or
  validated against Saldima production code. See `docs/plan.md` section
  2.1.
- Monetary values are always `decimal.Decimal` built from strings. Never
  `Decimal(1.23)` — see `reference/accounting/rounding.py`.
- `expected/reviewed/` fixtures are approved artifacts, not regenerable
  test snapshots. Follow `docs/release-gates.md` to change one. Never
  "fix" a failing test by regenerating and copying over a reviewed
  fixture without going through review.
- Every scenario states its accounting framework/basis/policies
  explicitly (`docs/plan.md` section 2.4) — don't assume a default.
- A production accounting defect should produce a permanent regression
  scenario or test wherever practical (`docs/plan.md` section 21).

## Adding a new scenario

See `docs/scenario-authoring.md`.

## Adding a new reference-model module

Keep it in the spirit of `reference/accounting/`: explicit formulas, small
functions, Decimal arithmetic, deterministic output, and a comment
explaining *why* wherever the logic is non-obvious (see
`docs/reference-model.md` for examples of the kind of subtlety worth
documenting).

## Running checks locally

```bash
uv sync --all-extras
make test      # pytest
make lint      # ruff check
make typecheck # mypy
```

## Scope boundaries

This repository does not replace the Saldima accounting engine, does not
certify GAAP/IFRS compliance, and does not substitute for a CPA's review
or legal/tax advice. See `docs/plan.md` section 22.
