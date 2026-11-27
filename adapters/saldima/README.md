# adapters/saldima

**Status:** Partially implemented, environment-gated. `SaldimaAdapter`
(`adapter.py`) is a real `AccountingSystemAdapter` implementation
(`adapters/__init__.py`) driving the actual Saldima engine — the sibling
`saldima` repository's `packages/gnucash` pure ledger functions, via a
small NDJSON stdin/stdout bridge merged there (`pnpm accounting-bridge`,
`packages/gnucash/src/{cli,cli-bridge}.ts`). `adapters/saldima/bridge.py`
is the subprocess transport.

This repo's own CI never has the `saldima` repo checked out, so every
caller must go through `bridge.is_available()` first (true only when the
`SALDIMA_REPO_PATH` environment variable points at a real checkout and
`pnpm` is on `PATH`) — see `tests/integration/
test_saldima_bridge_cross_validation.py`, which skips cleanly when it
returns `False`, and `docs/accounting-policy.md`'s "Saldima bridge"
section for the scope boundaries (aggregate-only balance sheet/income
statement, no per-account lines yet; no `apply_event`/closing-entry
concept on the bridge's side, same honest reason as
`adapters/gnucash_xml`'s).

This adapter must implement `AccountingSystemAdapter` and return normalized
data in the comparison schema (`schemas/financial-statement.schema.json`,
`schemas/schedule.schema.json`). It must never calculate expected results —
see `docs/plan.md` section 2.1 and section 11.
