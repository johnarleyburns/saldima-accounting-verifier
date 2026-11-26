from decimal import Decimal

from reference.tax import section_704c


def test_ceiling_rule_exactly_binding_leaves_contributing_partner_zero():
    # PART-003's numbers: book depreciation 1000.00/month split 50/50
    # (500.00 book share each); tax depreciation only 500.00/month total
    # (lower carryover tax basis). The non-contributing partner's book
    # share (500.00) exactly consumes all available tax depreciation.
    non_contributing, contributing = section_704c.traditional_method_allocation(
        tax_depreciation_per_period=Decimal("500.00"),
        non_contributing_partners_book_share=Decimal("500.00"),
    )
    assert non_contributing == Decimal("500.00")
    assert contributing == Decimal("0.00")


def test_ceiling_rule_not_binding_when_tax_depreciation_is_larger():
    non_contributing, contributing = section_704c.traditional_method_allocation(
        tax_depreciation_per_period=Decimal("900.00"),
        non_contributing_partners_book_share=Decimal("500.00"),
    )
    assert non_contributing == Decimal("500.00")
    assert contributing == Decimal("400.00")


def test_ceiling_rule_binding_caps_non_contributing_share():
    # Tax depreciation (300.00) is even smaller than the non-contributing
    # partner's book share (500.00) -- the ceiling rule caps them at the
    # total available, and the contributing partner gets nothing.
    non_contributing, contributing = section_704c.traditional_method_allocation(
        tax_depreciation_per_period=Decimal("300.00"),
        non_contributing_partners_book_share=Decimal("500.00"),
    )
    assert non_contributing == Decimal("300.00")
    assert contributing == Decimal("0.00")


def test_allocations_always_sum_to_total_tax_depreciation():
    for tax_dep, book_share in [
        (Decimal("500.00"), Decimal("500.00")),
        (Decimal("900.00"), Decimal("500.00")),
        (Decimal("300.00"), Decimal("500.00")),
        (Decimal("0.00"), Decimal("500.00")),
    ]:
        non_contributing, contributing = section_704c.traditional_method_allocation(tax_dep, book_share)
        assert non_contributing + contributing == tax_dep
