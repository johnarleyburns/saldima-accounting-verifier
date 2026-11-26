"""One-off script: run the reference model for a scenario and dump
expected/generated/<id>/<period>/*.json. Not part of the CLI (see
docs/release-gates.md for why generated output is never auto-promoted to
expected/reviewed/).

Usage: python scripts/generate_expected.py scenarios/foundational/core-001-opening-balances.yaml
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from runner import reference_runner
from runner.scenario_runner import load_scenario


def main() -> None:
    scenario_path = Path(sys.argv[1])
    loaded = load_scenario(scenario_path)
    reports = reference_runner.run(loaded)

    out_dir = REPO_ROOT / "expected" / "generated" / loaded.id
    for period, statements in reports.items():
        period_dir = out_dir / period
        period_dir.mkdir(parents=True, exist_ok=True)
        for statement_type, data in statements.items():
            (period_dir / f"{statement_type}.json").write_text(
                json.dumps(data, indent=2, sort_keys=True) + "\n"
            )
        print(f"{loaded.id} {period}: wrote {list(statements.keys())}")


if __name__ == "__main__":
    main()
