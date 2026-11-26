"""One-off script: run a known consolidation group (see
runner/consolidation_runner.py's registry) and dump
expected/generated/<group_id>/<period>/*.json. Mirrors
scripts/generate_expected.py's single-scenario pattern for a consolidated
multi-entity group instead.

Usage: python scripts/generate_consolidated_expected.py multi-001-intercompany-transactions
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from runner import consolidation_runner


def main() -> None:
    group_id = sys.argv[1]
    reports = consolidation_runner.run(group_id)

    out_dir = REPO_ROOT / "expected" / "generated" / group_id
    for period, statements in reports.items():
        period_dir = out_dir / period
        period_dir.mkdir(parents=True, exist_ok=True)
        for statement_type, data in statements.items():
            (period_dir / f"{statement_type}.json").write_text(
                json.dumps(data, indent=2, sort_keys=True) + "\n"
            )
        print(f"{group_id} {period}: wrote {list(statements.keys())}")


if __name__ == "__main__":
    main()
