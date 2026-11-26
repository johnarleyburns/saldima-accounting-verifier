# reference/tax

Tax-specific reference calculations: MACRS depreciation, partnership outside
tax basis, liability allocations, Section 704(c).

**Status:** `macrs.py` is implemented (Phase 3 — see `docs/plan.md`
section 18, scenario FA-003, and `docs/accounting-policy.md` for its scope
boundary: it validates the MACRS schedule computation only, not a
book/tax deferred-tax journal entry). `liabilities.py`,
`partnership_basis.py`, and `section_704c.py` are implemented (Phase 5 —
scenarios PART-002/PART-003, same section of `docs/accounting-policy.md`
for their scope boundaries: outside basis and the section 704(c)
allocation are computed independently and never posted as journal
entries; section 704(c) implements the traditional method only, not the
curative or remedial methods; section 743(b) is not implemented at all).

**There is no `capital_accounts.py`, deliberately.** "Capital accounts"
is exactly what the ordinary ledger (multiple partner equity accounts)
plus `reference/accounting/closing.py`'s `partner_allocations` already
track — a wrapper module here would have nothing to do beyond restating
`Ledger.balances_as_of`.

Every module records its applicable tax authority (IRS Publications 541
and 946, and the specific Internal Revenue Code sections / Treasury
Regulations cited in each module's docstring) per
`docs/dataset-provenance.md`'s citation convention.
