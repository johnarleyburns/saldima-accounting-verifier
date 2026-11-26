"""Partner share of partnership liabilities (IRC section 752).

Pure Decimal, no dependency on Saldima production code -- see
docs/plan.md section 2.1. Phase 5 scope: assumes partnership liabilities
are shared in the same ratio as profits and losses. Real section 752
sharing rules distinguish recourse from nonrecourse debt and can diverge
from the profit-sharing ratio (e.g. a nonrecourse loan is shared by the
"partnership minimum gain" rules, not simple pro rata) -- this reference
model does not model that distinction; see docs/accounting-policy.md for
the documented scope boundary. `PART-002`'s single partnership-level loan
is shared by the partners' ordinary profit/loss ratio, which this module
assumes throughout.
"""

from __future__ import annotations

from decimal import Decimal

from reference.accounting.journal import AccountingError
from reference.accounting.rounding import ZERO, round_currency

ONE = Decimal("1.00")


def partner_share_of_liability(
    total_liability: Decimal,
    sharing_ratios: dict[str, Decimal],
    precision: int = 2,
    method: str = "HALF_UP",
) -> dict[str, Decimal]:
    """Split `total_liability` across partners by `sharing_ratios` (a
    `{partner_id: ratio}` mapping whose ratios must sum to exactly 1.00).

    Each partner gets `round_currency(total_liability * ratio)` except the
    *last* partner in `sharing_ratios`'s iteration order, who gets the
    exact remainder -- the same remainder-to-last convention every
    reference/schedules/* module already uses.
    """
    total_ratio = sum(sharing_ratios.values(), ZERO)
    if total_ratio != ONE:
        raise AccountingError(f"sharing_ratios must sum to 1.00 (got {total_ratio})")

    partner_ids = list(sharing_ratios.keys())
    shares: dict[str, Decimal] = {}
    allocated_so_far = ZERO
    for i, partner_id in enumerate(partner_ids):
        if i == len(partner_ids) - 1:
            amount = total_liability - allocated_so_far
        else:
            amount = round_currency(total_liability * sharing_ratios[partner_id], precision, method)
            allocated_so_far += amount
        shares[partner_id] = amount
    return shares
