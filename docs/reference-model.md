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
