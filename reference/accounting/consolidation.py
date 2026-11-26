"""Multi-entity consolidation: combine several entities' books into one
set of statements, eliminating intercompany balances and activity.

See docs/plan.md section 1 item 15 and section 19's `MULTI-001`/
`MULTI-002` -- this is out-of-roadmap follow-on work (it doesn't map to
any of the 7 named phases in section 18), filling in the one remaining
gap in the gold-standard scenario corpus. See docs/accounting-policy.md
for the scope boundaries (wholly-owned subsidiary, cost method, no
noncontrolling interest, consolidation only at a fiscal year end after
each entity's own closing, no consolidated cash flow).

Every entity is an ordinary, independently-loadable scenario (its own
`ChartOfAccounts` + `Ledger`, built by the unchanged `runner/
scenario_runner.py`) -- there is no new "multi-entity scenario" shape.
Combining them is pure Decimal/dataclass logic, reusing the *existing*
`TrialBalance`/`IncomeStatement`/`BalanceSheet` dataclasses directly
(constructed from combined, eliminated figures) rather than inventing
parallel "consolidated" result types, so their own `assert_balanced()`/
`assert_balances()` and `reference/reporting/statements.py`'s
`*_to_dict` converters work on consolidated output for free.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from reference.accounting import balance_sheet, income_statement, trial_balance
from reference.accounting.journal import AccountingError, AccountType, ChartOfAccounts
from reference.accounting.ledger import Ledger
from reference.accounting.rounding import ZERO


@dataclass(frozen=True)
class EliminationPair:
    """One intercompany relationship to eliminate on consolidation.

    `debit_normal_account_id` is the asset/expense side (e.g. a parent's
    investment-in-subsidiary, or an intercompany loan receivable, or an
    intercompany interest/fee expense); `credit_normal_account_id` is the
    liability/equity/revenue side it must exactly offset (e.g. the
    subsidiary's contributed capital, or the matching intercompany
    payable, or the matching intercompany interest/fee revenue).
    Investment-vs-equity, receivable-vs-payable, and income-vs-expense
    eliminations are all the same shape -- one generic mechanism handles
    every case this reference model needs.
    """

    debit_normal_account_id: str
    credit_normal_account_id: str


Entity = tuple[ChartOfAccounts, Ledger]


def _combined_account_types(entities: list[Entity]) -> dict[str, AccountType]:
    types: dict[str, AccountType] = {}
    for chart, _ledger in entities:
        for account_id, account in chart.accounts.items():
            types[account_id] = account.type
    return types


def _assert_eliminations_net_to_zero(
    eliminations: list[EliminationPair],
    debit_side: dict[str, Decimal],
    credit_side: dict[str, Decimal],
) -> None:
    """Each elimination pair's two sides must be exactly equal -- they're
    mirror images of the same intercompany transaction recorded on each
    entity's own books. If they don't match, the group's books don't
    actually agree with each other, and consolidation must say so rather
    than silently report a wrong number (release-gate rules 6/7: no
    cross-book contamination, no silently discarded discrepancy).
    """
    for pair in eliminations:
        debit_amount = debit_side.get(pair.debit_normal_account_id, ZERO)
        credit_amount = credit_side.get(pair.credit_normal_account_id, ZERO)
        if debit_amount != credit_amount:
            raise AccountingError(
                f"Intercompany elimination does not net to zero: "
                f"{pair.debit_normal_account_id!r}={debit_amount} vs "
                f"{pair.credit_normal_account_id!r}={credit_amount}"
            )


def consolidated_trial_balance(
    entities: list[Entity],
    eliminations: list[EliminationPair],
    as_of: date,
    scenario_id: str,
    period: str,
) -> trial_balance.TrialBalance:
    combined_debit: dict[str, Decimal] = {}
    combined_credit: dict[str, Decimal] = {}
    for chart, ledger in entities:
        balances = ledger.balances_as_of(as_of)
        for account_id in chart.accounts:
            combined_debit[account_id] = (
                combined_debit.get(account_id, ZERO) + balances[account_id]["debit"]
            )
            combined_credit[account_id] = (
                combined_credit.get(account_id, ZERO) + balances[account_id]["credit"]
            )

    _assert_eliminations_net_to_zero(eliminations, combined_debit, combined_credit)
    eliminated_ids = {p.debit_normal_account_id for p in eliminations} | {
        p.credit_normal_account_id for p in eliminations
    }

    lines = {}
    for account_id, debit_total in combined_debit.items():
        if account_id in eliminated_ids:
            continue
        net = debit_total - combined_credit[account_id]
        if net >= ZERO:
            lines[account_id] = trial_balance.TrialBalanceLine(account_id, debit=net, credit=ZERO)
        else:
            lines[account_id] = trial_balance.TrialBalanceLine(account_id, debit=ZERO, credit=-net)

    tb = trial_balance.TrialBalance(
        scenario_id=scenario_id, period=period, as_of=as_of, lines=lines
    )
    tb.assert_balanced()
    return tb


def consolidated_income_statement(
    entities: list[Entity],
    eliminations: list[EliminationPair],
    start: date,
    end: date,
    scenario_id: str,
    period: str,
) -> income_statement.IncomeStatement:
    account_types = _combined_account_types(entities)
    combined_debit: dict[str, Decimal] = {}
    combined_credit: dict[str, Decimal] = {}
    for chart, ledger in entities:
        activity = ledger.period_activity(start, end)
        for account_id in chart.accounts:
            combined_debit[account_id] = (
                combined_debit.get(account_id, ZERO) + activity[account_id]["debit"]
            )
            combined_credit[account_id] = (
                combined_credit.get(account_id, ZERO) + activity[account_id]["credit"]
            )

    _assert_eliminations_net_to_zero(eliminations, combined_debit, combined_credit)
    eliminated_ids = {p.debit_normal_account_id for p in eliminations} | {
        p.credit_normal_account_id for p in eliminations
    }

    revenue: dict[str, Decimal] = {}
    expenses: dict[str, Decimal] = {}
    for account_id, account_type in account_types.items():
        if account_id in eliminated_ids:
            continue
        if account_type == AccountType.REVENUE:
            net = combined_credit.get(account_id, ZERO) - combined_debit.get(account_id, ZERO)
            if net != ZERO:
                revenue[account_id] = net
        elif account_type == AccountType.EXPENSE:
            net = combined_debit.get(account_id, ZERO) - combined_credit.get(account_id, ZERO)
            if net != ZERO:
                expenses[account_id] = net

    return income_statement.IncomeStatement(
        scenario_id=scenario_id,
        period=period,
        start=start,
        end=end,
        revenue=revenue,
        expenses=expenses,
    )


def consolidated_balance_sheet(
    entities: list[Entity],
    eliminations: list[EliminationPair],
    as_of: date,
    scenario_id: str,
    period: str,
) -> balance_sheet.BalanceSheet:
    """Only valid *at a fiscal year end, after every entity's own closing
    entries for that year have been posted* -- see docs/accounting-
    policy.md's consolidation scope boundaries. At that point every
    entity's revenue/expense accounts are already zero (swept into
    retained earnings), so this never needs balance_sheet.py's synthetic
    `current_period_earnings` machinery: summing real post-closing
    balances and eliminating intercompany pairs is already exactly
    correct.
    """
    account_types = _combined_account_types(entities)
    combined_debit: dict[str, Decimal] = {}
    combined_credit: dict[str, Decimal] = {}
    for chart, ledger in entities:
        balances = ledger.balances_as_of(as_of)
        for account_id in chart.accounts:
            combined_debit[account_id] = (
                combined_debit.get(account_id, ZERO) + balances[account_id]["debit"]
            )
            combined_credit[account_id] = (
                combined_credit.get(account_id, ZERO) + balances[account_id]["credit"]
            )

    _assert_eliminations_net_to_zero(eliminations, combined_debit, combined_credit)
    eliminated_ids = {p.debit_normal_account_id for p in eliminations} | {
        p.credit_normal_account_id for p in eliminations
    }

    assets: dict[str, Decimal] = {}
    liabilities: dict[str, Decimal] = {}
    equity: dict[str, Decimal] = {}
    for account_id, account_type in account_types.items():
        if account_id in eliminated_ids:
            continue
        debit_total = combined_debit.get(account_id, ZERO)
        credit_total = combined_credit.get(account_id, ZERO)
        if account_type == AccountType.ASSET:
            assets[account_id] = debit_total - credit_total
        elif account_type == AccountType.LIABILITY:
            liabilities[account_id] = credit_total - debit_total
        elif account_type == AccountType.EQUITY:
            equity[account_id] = credit_total - debit_total
        elif account_type in (AccountType.REVENUE, AccountType.EXPENSE):
            net = (
                credit_total - debit_total
                if account_type == AccountType.REVENUE
                else debit_total - credit_total
            )
            if net != ZERO:
                raise AccountingError(
                    f"consolidated_balance_sheet: account {account_id!r} has unclosed "
                    f"revenue/expense activity at {as_of} -- consolidation is only valid "
                    "at a fiscal year end after every entity's own closing"
                )

    bs = balance_sheet.BalanceSheet(
        scenario_id=scenario_id,
        period=period,
        as_of=as_of,
        assets=assets,
        liabilities=liabilities,
        equity=equity,
    )
    bs.assert_balances()
    return bs
