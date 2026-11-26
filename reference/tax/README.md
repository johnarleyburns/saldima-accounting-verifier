# reference/tax

Tax-specific reference calculations: MACRS depreciation, partnership outside
tax basis, capital accounts, liability allocations, Section 704(c).

**Status:** `macrs.py` is implemented (Phase 3 — see `docs/plan.md`
section 18, scenario FA-003, and `docs/accounting-policy.md` for its scope
boundary: it validates the MACRS schedule computation only, not a
book/tax deferred-tax journal entry). `partnership_basis.py`,
`capital_accounts.py`, `liabilities.py`, and `section_704c.py` are not yet
implemented; they land with Phase 5 (partnership accounting) — see
`docs/plan.md` section 7.9. Every module here must record tax year,
applicable authority, and election assumptions per scenario, per
`docs/dataset-provenance.md`.
