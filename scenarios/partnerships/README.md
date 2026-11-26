# scenarios/partnerships

**Status:** Implemented (Phase 5, see `docs/plan.md` section 18 and the
scenario corpus table in section 19): `part-001-two-partner-formation.yaml`,
`part-002-partnership-debt-and-outside-basis.yaml`,
`part-003-property-contribution-704c.yaml`, and
`part-004-partnership-liquidation.yaml`. None of these need a new event
type — contributions/withdrawals/liquidating distributions are
`manual_journal_entry`, a partnership loan is an ordinary
`loan_origination`, and a property contribution uses
`fixed_asset_purchase`'s `contributed_capital_account_id` field — see
`docs/scenario-authoring.md` and `docs/accounting-policy.md`. Each
closing uses the new `closing.partner_allocations` field to split net
income by ratio across multiple partner capital accounts instead of one
retained-earnings account. Outside tax basis (`PART-002`) and the
section 704(c) built-in-gain allocation (`PART-003`) are computed
independently in `reference/tax/` and validated by dedicated tests —
never posted to either scenario's ledger.
