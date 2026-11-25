"""Developer CLI. See docs/plan.md section 16.

    uv run python -m runner.cli run --category foundational
    uv run python -m runner.cli run --scenario core-002-basic-service-business
    uv run python -m runner.cli validate --adapter saldima
    uv run python -m runner.cli compatibility --adapter gnucash_xml
    uv run python -m runner.cli report
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import typer

from runner import compare, reference_runner, report
from runner.scenario_runner import load_scenario

app = typer.Typer(add_completion=False)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = REPO_ROOT / "scenarios"
REVIEWED_DIR = REPO_ROOT / "expected" / "reviewed"


def _iter_scenario_files(category: str | None, scenario_id: str | None) -> Iterator[Path]:
    if scenario_id is not None:
        matches = list(SCENARIOS_DIR.glob(f"**/{scenario_id}.yaml"))
        if not matches:
            raise typer.BadParameter(f"No scenario file found for id {scenario_id!r}")
        yield from matches
        return
    base = SCENARIOS_DIR / category if category else SCENARIOS_DIR
    yield from sorted(base.glob("**/*.yaml"))


@app.command()
def run(
    category: str = typer.Option(None, help="Scenario category directory under scenarios/"),
    scenario: str = typer.Option(None, help="A single scenario id to run"),
) -> None:
    """Run the reference model for one or more scenarios and compare to reviewed fixtures."""
    any_fail = False
    for path in _iter_scenario_files(category, scenario):
        loaded = load_scenario(path)
        actual_reports = reference_runner.run(loaded)

        statuses = {}
        for period, statement_dicts in actual_reports.items():
            reviewed_dir = REVIEWED_DIR / loaded.id / period
            if not reviewed_dir.exists():
                statuses[period] = "NO REVIEWED FIXTURE"
                continue
            period_pass = True
            for statement_type, actual in statement_dicts.items():
                fixture_path = reviewed_dir / f"{statement_type}.json"
                if not fixture_path.exists():
                    statuses[period] = "NO REVIEWED FIXTURE"
                    period_pass = False
                    continue
                expected = json.loads(fixture_path.read_text())
                result = compare.compare_statement(expected, actual)
                if result["status"] == "FAIL":
                    period_pass = False
                    any_fail = True
                    typer.echo(report.render_comparison(result))
            if period not in statuses:
                statuses[period] = "PASS" if period_pass else "FAIL"

        typer.echo(report.render_scenario_summary(loaded.id, statuses))
        typer.echo("")

    if any_fail:
        raise typer.Exit(code=1)


@app.command()
def validate(adapter: str = typer.Option(..., help="Adapter name under adapters/")) -> None:
    """Run scenarios against a live Saldima system adapter (not yet implemented)."""
    typer.echo(
        f"Adapter {adapter!r}: not yet implemented. See adapters/{adapter}/README.md "
        "and docs/plan.md section 11."
    )
    raise typer.Exit(code=2)


@app.command()
def compatibility(adapter: str = typer.Option(..., help="Adapter name under adapters/")) -> None:
    """Run GnuCash (or other) compatibility fixtures through an adapter (not yet implemented)."""
    typer.echo(
        f"Adapter {adapter!r}: not yet implemented. See adapters/{adapter}/README.md "
        "and docs/plan.md section 10."
    )
    raise typer.Exit(code=2)


@app.command()
def report_cmd() -> None:
    """Generate an aggregate test report (not yet implemented beyond `run`'s console output)."""
    typer.echo("Aggregate HTML/JSON reporting is not yet implemented. See docs/plan.md section 16.")
    raise typer.Exit(code=2)


app.command(name="report")(report_cmd)


if __name__ == "__main__":
    app()
