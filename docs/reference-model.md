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

## Phase 1 cash flow is operating-only

There is no investing/financing classification yet — every non-cash
balance-sheet account's change is reported as an "operating" adjustment.
This is accurate (the reconciliation still ties to actual cash movement)
but not a GAAP-presentable statement of cash flows. Classification arrives
with Phase 3 (fixed assets) and Phase 4 (debt), which are the first phases
where investing/financing activity actually exists in a scenario.
