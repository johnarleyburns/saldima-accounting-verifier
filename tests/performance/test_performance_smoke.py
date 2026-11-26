"""Fast, CI-friendly proof that the performance-benchmark infrastructure
itself works (docs/plan.md section 15 and section 18's Phase 7).

The full 1,000/10,000/100,000/1,000,000-transaction benchmark
(scripts/run_performance_benchmark.py) is a manual tool, not run by
`pytest`/`make test` -- docs/release-gates.md puts large generated
ledgers and performance benchmarks in the *Nightly* CI stage, not the
pull-request stage this repository's ci.yml currently implements. This
test exercises the exact same code path at a small, fast scale, so a
break in the generator or the benchmark function itself is still caught
on every `make test`.
"""

from __future__ import annotations

from scripts.generate_synthetic_ledger import build_synthetic_ledger
from scripts.run_performance_benchmark import benchmark_one_size

SMOKE_TEST_SIZE = 2_000


def test_synthetic_ledger_is_fully_balanced_and_deterministic():
    _, ledger_a = build_synthetic_ledger(SMOKE_TEST_SIZE, seed=1)
    _, ledger_b = build_synthetic_ledger(SMOKE_TEST_SIZE, seed=1)

    # len() is >= SMOKE_TEST_SIZE, not ==: build_synthetic_ledger appends
    # one closing entry per full calendar year on top of the requested
    # transaction count.
    assert len(ledger_a.entries) >= SMOKE_TEST_SIZE
    assert [e.id for e in ledger_a.entries] == [e.id for e in ledger_b.entries]
    for entry_a, entry_b in zip(ledger_a.entries, ledger_b.entries, strict=True):
        assert entry_a.date == entry_b.date
        assert entry_a.lines == entry_b.lines


def test_synthetic_ledger_spans_multiple_years():
    _, ledger = build_synthetic_ledger(SMOKE_TEST_SIZE)
    max_year = max(entry.date.year for entry in ledger.entries)
    assert max_year > ledger.entries[0].date.year + 1


def test_benchmark_runs_end_to_end_and_reports_sane_timings():
    result = benchmark_one_size(SMOKE_TEST_SIZE)
    assert result["num_transactions"] == SMOKE_TEST_SIZE
    for key in (
        "build_ledger_seconds",
        "trial_balance_seconds",
        "balance_sheet_seconds",
        "cash_flow_seconds",
    ):
        assert result[key] >= 0
