# Reference Model Notes

The reference model (`reference/accounting/`) is the independent authority
for expected results — see `docs/plan.md` section 2.1. This document
records non-obvious design decisions so they aren't re-litigated (or
silently broken) later.

## Closing entries must be excluded from period activity

`Ledger.period_activity(start, end)` (used by `income_statement.py`)
**always excludes entries flagged `is_closing`**. Without this, a report
whose window ends exactly on a closing date would see its own revenue and
expense zeroed out by the very entry that closed them — e.g. a fiscal-year
income statement for 2026, generated after the 2026-12-31 closing entry has
been posted, would show $0 revenue and $0 expense instead of the year's
real activity, because the closing entry's lines (which zero out revenue/
expense into retained earnings) fall inside the Jan 1–Dec 31 window.

## `balance_sheet.py`'s unclosed-earnings window must start after the last closing

The balance sheet reports a synthetic `current_period_earnings` equity line
to keep the accounting equation true *before* a fiscal year's closing
entry has run (revenue/expense balances are real equity that just hasn't
been swept into retained earnings yet). Naively computing that line as
"income statement from fiscal-year-start to as_of" double-counts once a
closing entry has actually posted: the retained-earnings account already
reflects the closed amount, and summing fiscal-year-start-to-date revenue/
expense again would add it a second time. The fix:
`Ledger.last_closing_date_through(as_of)` finds the most recent closing on
or before `as_of`, and `current_period_earnings` is computed only from the
day after that closing (or from the fiscal year start, if none has
happened yet). When `as_of` *is* a closing date, that window is empty and
`current_period_earnings` is correctly zero.

## `cash_flow.py` must be blind to closing entries entirely

Closing entries never touch cash, but they do move balances between
revenue/expense and retained earnings — both of which cash_flow.py's
indirect-method reconciliation touches (net income, and the equity-account
adjustment). If `net_income` excludes closing effects (per the first point
above) while the retained-earnings adjustment *includes* them (via the
default `balances_as_of`), the two no longer reconcile to the real change
in cash — the closing's effect gets double-counted into
`operating_cash_flow` without ever hitting cash. The fix:
`Ledger.balances_as_of(as_of, exclude_closing=True)` computes balances as
if closing entries were never posted, and `cash_flow.generate` uses that
consistently for both its opening and closing balance snapshots. This
makes the reconciliation identity
`operating_cash_flow == ending_cash - beginning_cash` hold by construction
for *any* period, including one that spans or ends on a closing date — see
the proof sketch below.

### Proof sketch for the reconciliation identity

For any window `[start, end]`, every journal entry posted in that window
balances (`total_debit == total_credit`), so summing debits-minus-credits
across *all* accounts over the window is exactly zero. Splitting that sum
by account type (debit-normal: assets + expenses; credit-normal:
liabilities + equity + revenue) and rearranging:

```
Δcash = Δliabilities + Δequity + Δrevenue − Δexpenses − Δ(other assets)
      = net_income + Δliabilities + Δequity − Δ(other assets)
      = net_income + Σ(operating_adjustments)
```

This holds for *any* consistent choice of what counts as a "delta" (balance
deltas, or balance deltas with closing entries excluded) as long as the
same choice is applied to every term. `cash_flow.py` uses the
exclude-closing basis throughout; `trial_balance.py` and `balance_sheet.py`
use the real (including-closing) basis throughout. Mixing the two bases
within one calculation is exactly the bug described above.

## Phase 1/2 cash flow was operating-only; Phase 3 adds investing/financing classification

Through Phase 2, every non-cash balance-sheet account's change was
reported as an "operating" adjustment — accurate (the reconciliation still
tied to actual cash movement) but not a GAAP-presentable statement of cash
flows, since there was no investing/financing activity in any scenario to
classify. Phase 3 (fixed assets) is the first phase where that activity
actually exists (an equipment purchase/disposal), so `Account` gained an
optional `cash_flow_category` field (`reference/accounting/journal.py`'s
`CashFlowCategory`, defaulting to `OPERATING`), and `cash_flow.py` now
buckets each account's delta by it into `operating_adjustments`,
`investing_activities`, or `financing_activities` instead of always the
first. See `docs/accounting-policy.md`'s `cash_flow_category` section for
how scenarios opt an account into a category, and its noted coarseness
(whole-account-delta classification, not per-transaction).

This is additive, not a behavior change for Phase 1/2 scenarios: the
reconciliation identity above still holds term-for-term, just partitioned
three ways instead of one --
`operating_cash_flow + investing_cash_flow + financing_cash_flow ==
ending_cash - beginning_cash`. Since every Phase 1/2 account defaults to
`OPERATING`, `investing_activities`/`financing_activities` are empty dicts
for all six of those scenarios at every reported period, and
`runner/reference_runner.py` only emits the `investing_cash_flow`/
`financing_cash_flow` lines when the corresponding dict is non-empty — so
all six scenarios' reviewed fixtures are byte-for-byte unchanged by this.
Fixed-asset depreciation also gets its classic "added back to net income"
indirect-method treatment for free: a contra-asset like accumulated
depreciation defaults to `OPERATING`, and its delta (which goes more
*negative* as depreciation accrues, since it only ever receives credits)
produces a *positive* operating adjustment via the same generic asset-delta
formula already in place — see the next section and
`docs/accounting-policy.md`'s "Contra-asset and gain/loss accounts"
section.

Debt (Phase 4) is expected to be the next phase to populate
`financing_activities` (loan proceeds/principal repayments).

**Update, Phase 4:** this is now real. `DEBT-001` tags `loan_payable`
`cash_flow_category: financing`, and the loan proceeds (a liability
increase) and every monthly principal repayment (a liability decrease)
land in `financing_activities` with **no further code change** — the same
generic `by_category[account.cash_flow_category][account.id] = delta`
logic in `cash_flow.generate()` that already handled the asset side in
Phase 3 handles the liability side identically, since the branch is keyed
only on `AccountType.ASSET` vs. not, with the category lookup applied
uniformly either way. `tests/invariants/test_debt_accounts_flow_through.py`
proves both directions (proceeds in, principal out) on a hand-built
ledger, independent of `DEBT-001`'s own bookkeeping.

## Phase 2 confirms (not just assumes) that AR/AP/prepaid/deferred-revenue flow correctly

The proof sketch above shows the cash-flow reconciliation holds for *any*
consistent choice of what counts as a balance "delta" across *every*
non-cash account, by construction of the balanced-journal-entry invariant
— it was never actually specific to the handful of account types Phase 1's
two scenarios happened to use. Phase 2 (`ACCR-001/002`, `REV-001/002`)
exercises accrued liabilities, prepaid-expense assets, and a deferred-
revenue liability for the first time, and confirms the proof holds for
them too, with no changes to `cash_flow.py`, `trial_balance.py`,
`income_statement.py`, or `balance_sheet.py` (all already generic over
`AccountType`). `tests/invariants/test_accrual_accounts_flow_through.py`
proves this directly on a small hand-built ledger, independent of any
scenario's specific bookkeeping — see `docs/accounting-policy.md` for the
full writeup.

## Phase 3 confirms the same genericity for contra-assets, gain/loss, and FIFO COGS

Phase 3 (`FA-001/002/003`, `INV-001/002`) exercises a contra-asset
(accumulated depreciation), gain/loss-on-disposal accounts, and FIFO cost
of goods sold for the first time, and -- like Phase 2's AR/AP/deferred-
revenue finding -- none of it required changes to `trial_balance.py`,
`income_statement.py`, or `balance_sheet.py`. A contra-asset declared
`type: asset` naturally carries a negative signed balance (it only ever
receives credits), which nets against the gross asset account in
`total_assets` to produce net book value; gain/loss accounts are ordinary
`revenue`/`expense`-type accounts. `tests/invariants/
test_fixed_asset_accounts_flow_through.py` proves the contra-asset and
cash-flow-classification claims directly; `tests/integration/
test_core_scenarios.py`'s `test_inv_001_fifo_cogs_corroborates_the_ledger_independently`
cross-checks FIFO COGS the same way the ACCR-001 payables cross-check
corroborates accrued liabilities.

## Phase 4 confirms genericity once more, and is the first phase to need no Phase 1 code changes at all

`DEBT-001` and `PAY-001` exercise a liability tagged `cash_flow_category:
financing`, a liability/expense split derived from a declining balance,
and payroll liabilities for the first time, and required **zero** changes
anywhere in `reference/accounting/*.py` -- unlike Phase 3, which needed
the additive `cash_flow_category` field itself. Interest expense and a
loan payable are ordinary `AccountType` accounts; the financing
classification is the pre-existing Phase 3 mechanism applied to a
liability instead of an asset (see the update above). This is Phase 2's
situation repeating, not Phase 3's -- the infrastructure Phase 3 added
turned out to be general enough that Phase 4 needed none of its own.

## Phase 5 is the first phase since Phase 3 to need a real reference/accounting change -- and it's a small, additive one

`closing.py`'s `close_period` hardcoded crediting/debiting exactly **one**
account (`retained_earnings_account_id`) for a period's whole net income/
loss. A partnership needs that split across multiple partner capital
accounts by ratio, so `close_period` gained an alternative
`partner_allocations: dict[str, Decimal] | None` parameter — exactly one
of it or `retained_earnings_account_id` must be given. The allocation
loop gives each target `round_currency(net_to_retained_earnings * ratio)`
except the last target in the given order, which gets the exact
remainder (the same remainder-to-last convention `reference/schedules/*`
already uses everywhere). **For a single target this reduces to exactly
the pre-Phase-5 behavior** — the sole target always *is* "the last one,"
so it gets the full, unrounded amount, with no rounding step even
entering the picture. All eleven pre-Phase-5 scenarios' reviewed fixtures
were confirmed byte-for-byte unchanged before a single Phase 5 fixture
was written.

Multiple partner capital accounts needed no further changes anywhere:
`balance_sheet.py`/`trial_balance.py` already sum every `AccountType.
EQUITY` account generically (the same genericity Phase 2 found for AR/AP
and Phase 3 found for contra-assets), and `cash_flow.py` needed no
changes either -- a partner's own contributions/distributions (not the
closing allocation itself, which is excluded the same way every other
closing entry is) are the only things that show up as that period's
cash-flow adjustment for a partner capital account, exactly as the
exclude-closing mechanism above already guarantees for any equity
account.

Outside basis and the section 704(c) built-in-gain allocation
(`PART-002`, `PART-003`) are schedule-only, like MACRS before them (see
the FA-003 section above) -- see `docs/accounting-policy.md` for the full
writeup and scope boundaries (traditional method only, no section 743(b)).

## Straight-line revenue recognition's rounding remainder goes to the last period

`reference/schedules/deferred_revenue.py`'s `build_straight_line_schedule`
divides a total evenly across every month in the service period and rounds
each monthly amount with `round_currency`; dividing most totals evenly
leaves a fractional-cent remainder that doesn't disappear on its own. The
fix is the same one `closing.py` already uses for its own computed totals:
absorb the remainder into the *last* period, so the per-period amounts
always sum to exactly the contract total instead of silently drifting a
cent short or over. See `tests/unit/test_deferred_revenue.py`'s
`test_straight_line_schedule_absorbs_rounding_remainder_into_last_month`.

`reference/schedules/depreciation.py`'s `build_straight_line_schedule`
(Phase 3) uses the identical convention for the same reason, including
when a `fixed_asset_disposal` truncates the schedule early -- truncation
only ever removes trailing months, so an early disposal never actually
reaches the remainder month, and every truncated amount is the plain even
per-month figure (see `tests/unit/test_depreciation.py`'s
`test_schedule_truncated_by_disposal_before_the_final_month`).

`reference/schedules/debt.py`'s `build_amortization_schedule` (Phase 4)
applies the same remainder-in-the-last-period convention to the equal
*principal* payment (not interest, which is recomputed fresh each period
from the actual remaining balance and needs no remainder handling of its
own). `DEBT-001`'s own numbers happen to divide evenly (`$60,000 / 60 =
$1,000.00` exactly), so see `tests/unit/test_debt.py`'s
`test_schedule_absorbs_rounding_remainder_into_last_month` for a case that
doesn't.

`reference/tax/liabilities.py`'s `partner_share_of_liability` (Phase 5)
applies the identical remainder-to-last convention when a liability
doesn't split evenly by ratio across partners -- see
`tests/unit/test_liabilities.py`'s
`test_uneven_split_with_remainder_on_the_last_partner`. The same
convention, generalized to an arbitrary number of named targets rather
than a fixed time sequence, is also what `closing.py`'s new
`partner_allocations` path uses (see the Phase 5 section above).

## The double-entry invariants, numbered (Phase 7)

`docs/plan.md` section 13 describes the invariants this reference model
enforces in prose only. The numbering actually in use comes from
`tests/invariants/test_double_entry_invariants.py`'s own scheme, which
this section now makes canonical, recording for each invariant whether
it's covered by a hand-built example (`tests/invariants/`), a
Hypothesis property test generalizing it across randomly generated
books (`tests/property/`, Phase 7), or both:

| # | Invariant | Hand-built example | Property test |
|---|---|---|---|
| 1 | Every posted journal entry balances | `test_invariant_1_...` (construction-time enforcement) | — (enforced unconditionally by `JournalEntry.__post_init__`; every other property test's input is already balanced by construction) |
| 2 | The trial balance always balances | `test_invariant_2_...` | `tests/property/test_balanced_ledger_invariants.py::test_trial_balance_always_balances_for_arbitrary_valid_postings` |
| 3 | The balance sheet satisfies the accounting equation | `test_invariant_3_...` (also checks the broken-ledger detector fires) | `tests/property/test_balanced_ledger_invariants.py::test_accounting_equation_holds_for_arbitrary_valid_ledgers` |
| 6 | Posted transactions are immutable | `test_invariant_6_...` | — (a `FrozenInstanceError` check; there is no randomized input to vary) |
| 7 | A reversal restores original balances | `test_invariant_7_...` | — |
| 8 | Every split references a valid account | `test_invariant_8_...` | — (an `AccountingError` check; there is no randomized input to vary) |
| 12 | Closing does not change historical entries | `test_invariant_12_...` | — |

Two further properties this phase adds have no pre-existing hand-built
example or assigned invariant number, so they're recorded here directly
rather than forcing a number onto them:

- **Idempotent replay**: posting the same set of valid entries in a
  different order produces identical final account balances —
  `tests/property/test_balanced_ledger_invariants.py::test_posting_order_does_not_affect_final_balances`.
- **Cash-flow reconciliation holds for arbitrary activity**, generalizing
  the proof sketch above beyond the specific scenarios that exercise it
  today — `tests/property/test_cash_flow_reconciliation.py`.

Two more Phase 7 property suites generalize claims this document already
makes in prose, beyond their one hand-picked example apiece:
`tests/property/test_closing_allocation_invariants.py` (the Phase 5
partner-allocation remainder convention, for arbitrary partner counts and
ratios) and `tests/property/test_rounding_remainder_invariant.py` (the
shared remainder-to-last convention across every `reference/schedules/*`
and `reference/tax/liabilities.py` module that uses it). A fifth,
`tests/property/test_merge_invariants.py`, generalizes `reference/sync/
merge.py`'s conflict semantics (see below) across randomly generated
branch sizes and edit amounts.

## Phase 7's performance baseline surfaced (and fixed) a real O(n²) bottleneck

Building `scripts/run_performance_benchmark.py`'s large synthetic ledgers
for the first time (see "the double-entry invariants, numbered" above)
did exactly what `docs/plan.md` section 15 says a baseline is for:
`Ledger.post`'s duplicate-id check was `any(existing.id == entry.id for
existing in self.entries)`, an O(n) linear scan on every post, making
posting `n` entries O(n²) overall. At 100,000 transactions this took over
a thousand CPU-seconds; at 1,000,000 it would never have finished in any
practical time. The fix is a `Ledger._entry_ids: set[str]` tracked
alongside `entries` (seeded from any pre-existing entries in
`__post_init__`, updated on every successful `post`) — an O(1) membership
check with identical behavior and the identical `AccountingError` message
for a genuine duplicate. This is the one `reference/accounting/*.py`
change this phase makes: every other Phase 7 addition (`tests/property/`,
`scripts/generate_synthetic_ledger.py`,
`scripts/run_performance_benchmark.py`) only calls existing public
functions. All 17 pre-Phase-7 scenarios' reviewed fixtures were confirmed
byte-for-byte unchanged before and after this fix (it doesn't change
`Ledger`'s externally observable behavior at all, only its internal
duplicate-id algorithm), and a full 1,000,000-transaction benchmark run
completes in well under a minute after the fix (building the ledger:
~18s; each report: under 1.5s).

## `reference/sync/merge.py` models an "edit" as a replacement, never a mutation (Phase 6)

Invariant 6 (docs/plan.md section 13; `tests/invariants/
test_double_entry_invariants.py`'s
`test_invariant_6_posted_transactions_are_immutable`) means a posted
`JournalEntry` is frozen and `Ledger` is append-only -- there is no
in-place "edit" API anywhere in this reference model, by design. So when
`reference/sync/merge.py` needs to represent "a device corrected an
existing posted entry while offline," it does so as a `BranchState.edits`
mapping (`{original_entry_id: replacement_entry}`) that lives entirely
outside any `Ledger` -- the original entry is never touched, only ever
superseded in a *merge result*, and only when the merge can actually
resolve which replacement (if any) should apply. See
docs/accounting-policy.md's "Multi-book merge semantics" section for the
conflict rule itself.
