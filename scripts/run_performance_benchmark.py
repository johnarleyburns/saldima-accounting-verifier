"""Manual performance benchmark: times reference-model report generation
over synthetic ledgers at increasing scale (docs/plan.md section 15 and
section 18's Phase 7).

Not run by `pytest`/`make test` and not part of CI. docs/release-gates.md
puts "large generated ledgers, performance benchmarks" in the *Nightly*
CI stage, which this repository hasn't implemented yet (its current
ci.yml covers only the pull-request stage). This script is the intended
entry point once that stage exists -- today it's a manual tool. It
*measures and records* a baseline; docs/plan.md section 15 is explicit
that regression thresholds come only after baselines have been tracked
over time, so this script never fails a build.

Usage: python scripts/run_performance_benchmark.py [sizes...]
       (default sizes: 1000 10000 100000 1000000)
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from reference.accounting import balance_sheet, cash_flow, trial_balance
from scripts.generate_synthetic_ledger import (
    CASH_ACCOUNT_ID,
    SPAN_YEARS,
    START_DATE,
    build_synthetic_ledger,
)

DEFAULT_SIZES = (1_000, 10_000, 100_000, 1_000_000)


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Not JSON-serializable: {value!r}")


def benchmark_one_size(num_transactions: int) -> dict[str, Any]:
    build_start = time.perf_counter()
    chart, ledger = build_synthetic_ledger(num_transactions)
    build_seconds = time.perf_counter() - build_start

    # Not ledger.entries[-1]: build_synthetic_ledger appends each closed
    # year's closing entry *after* the random transactions it closes, so
    # the true chronological maximum is the last entry by date, not by
    # posting order.
    as_of = max(entry.date for entry in ledger.entries)
    fiscal_year_start = date(as_of.year, 1, 1)

    tb_start = time.perf_counter()
    tb = trial_balance.generate(ledger, chart, as_of, "perf-bench", str(as_of.year))
    tb_seconds = time.perf_counter() - tb_start
    tb.assert_balanced()

    bs_start = time.perf_counter()
    bs = balance_sheet.generate(
        ledger, chart, as_of, fiscal_year_start, "perf-bench", str(as_of.year)
    )
    bs_seconds = time.perf_counter() - bs_start
    bs.assert_balances()

    cf_start = time.perf_counter()
    cash_flow.generate(
        ledger, chart, fiscal_year_start, as_of, {CASH_ACCOUNT_ID}, "perf-bench", str(as_of.year)
    )
    cf_seconds = time.perf_counter() - cf_start

    return {
        "num_transactions": num_transactions,
        "build_ledger_seconds": build_seconds,
        "trial_balance_seconds": tb_seconds,
        "balance_sheet_seconds": bs_seconds,
        "cash_flow_seconds": cf_seconds,
    }


def main() -> None:
    sizes = [int(arg) for arg in sys.argv[1:]] or list(DEFAULT_SIZES)
    results = []
    for size in sizes:
        print(f"Benchmarking {size:,} transactions...")
        result = benchmark_one_size(size)
        results.append(result)
        print(
            f"  build_ledger={result['build_ledger_seconds']:.3f}s trial_balance={result['trial_balance_seconds']:.3f}s "
            f"balance_sheet={result['balance_sheet_seconds']:.3f}s cash_flow={result['cash_flow_seconds']:.3f}s"
        )

    baseline = {
        "generated_at": datetime.now(UTC).isoformat(),
        "generator": {"start_date": START_DATE.isoformat(), "span_years": SPAN_YEARS},
        "results": results,
    }

    out_dir = REPO_ROOT / "reports" / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "performance-baseline.json"
    out_path.write_text(json.dumps(baseline, indent=2, default=_json_default) + "\n")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
