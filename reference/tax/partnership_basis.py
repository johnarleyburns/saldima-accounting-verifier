"""Partner outside tax basis (IRC sections 705(a) and 752).

Pure Decimal, no dependency on Saldima production code -- see
docs/plan.md section 2.1 and docs/dataset-provenance.md's citation
convention (parallel to reference/tax/macrs.py citing IRS Publication
946; this module's authority is IRS Publication 541, Partnerships).

Phase 5 scope (see docs/accounting-policy.md): outside basis is a tax
concept with **no GAAP journal-entry counterpart** -- a partnership's
books never post an "outside basis" entry. This module computes it
independently from a partner's own contribution/allocation/distribution
history (the same facts the scenario already states or the ledger already
reflects), for comparison in a dedicated test
(tests/integration/test_part_002_outside_basis.py), never for posting.
"""

from __future__ import annotations

from decimal import Decimal

from reference.accounting.journal import AccountingError

ZERO = Decimal("0.00")


def outside_basis(
    contribution: Decimal,
    share_of_liabilities: Decimal,
    cumulative_allocated_income: Decimal,
    cumulative_allocated_losses: Decimal,
    distributions_received: Decimal,
) -> Decimal:
    """IRC section 705(a): a partner's outside basis is their contributed
    capital, plus their section 752 share of partnership liabilities, plus
    their cumulative allocated income, minus their cumulative allocated
    losses, minus cash/property distributions they've received.

    Raises `AccountingError` if the result would be negative: a partner's
    basis can never go below zero (IRC section 704(d) limits loss
    deductions to basis, and a distribution exceeding basis is taxable
    gain, not a basis reduction below zero) -- a scenario that produces a
    negative result here describes a situation this reference model does
    not (yet) model correctly, not a valid negative basis.
    """
    basis = (
        contribution
        + share_of_liabilities
        + cumulative_allocated_income
        - cumulative_allocated_losses
        - distributions_received
    )
    if basis < ZERO:
        raise AccountingError(
            f"outside basis cannot be negative (got {basis}); see IRC section 704(d)"
        )
    return basis
