"""Thin NDJSON stdin/stdout transport to the real Saldima engine's
accounting bridge (`pnpm accounting-bridge`, run from the sibling
`saldima` repository -- `packages/gnucash/src/{cli,cli-bridge}.ts`).

This module is transport only -- it knows nothing about our own
`reference/accounting/*` shapes, GUID derivation, or scenario loading;
see `adapters/saldima/adapter.py` for that translation. This mirrors the
split on the other side of the wire (`cli.ts` is a thin, behaviourless
loop; `cli-bridge.ts`'s `handleRequest` holds all the logic).

This repo's own CI never has the `saldima` repo checked out, so every
caller must go through `saldima_repo_path()`/`is_available()` first and
skip gracefully when it returns `None`/`False` -- see
`docs/accounting-policy.md`'s "Saldima bridge" section.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any

from reference.accounting.journal import AccountingError

WireMoney = dict[str, str]


def to_wire_money(value: Decimal) -> WireMoney:
    """Our Decimal -> the bridge's `{num, denom}` decimal-string pair,
    at a fixed denominator of 100 (this reference model's currency
    precision throughout -- see docs/accounting-policy.md). Raises if
    `value` isn't already at 2 decimal places (never silently rounds).
    """
    cents = (value * 100).to_integral_exact()
    return {"num": str(int(cents)), "denom": "100"}


def from_wire_money(wire: WireMoney) -> Decimal:
    """The inverse of `to_wire_money`, but general over *any* denominator
    the bridge returns -- `packages/gnucash`'s own arithmetic reduces
    fractions to lowest terms (e.g. `1300/1`, not always `130000/100`),
    confirmed by hand-testing the real bridge. Decimal division is exact
    here since every amount is already a whole number of cents.
    """
    num = Decimal(wire["num"])
    denom = Decimal(wire["denom"])
    return (num / denom).quantize(Decimal("0.01"))


def saldima_repo_path() -> Path | None:
    """The sibling `saldima` repository's path, from `SALDIMA_REPO_PATH`,
    or None if that variable isn't set or doesn't point at a real
    checkout. Never guesses a sibling-directory location.
    """
    raw = os.environ.get("SALDIMA_REPO_PATH")
    if not raw:
        return None
    path = Path(raw)
    if not (path / "package.json").exists():
        return None
    return path


def is_available() -> bool:
    return saldima_repo_path() is not None and shutil.which("pnpm") is not None


class SaldimaBridge:
    """One live `pnpm accounting-bridge` subprocess, holding one ledger
    (set by `reset`) for its lifetime. Not thread-safe; one bridge per
    book, used sequentially -- matches every other adapter's book model
    in this repo.
    """

    def __init__(self, repo_path: Path) -> None:
        self._process = subprocess.Popen(
            ["pnpm", "accounting-bridge"],
            cwd=str(repo_path),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,  # the `pnpm` command-echo line; harmless, never read
            text=True,
            bufsize=1,
        )

    def _call(self, request: dict[str, Any]) -> dict[str, Any]:
        assert self._process.stdin is not None
        assert self._process.stdout is not None
        self._process.stdin.write(json.dumps(request) + "\n")
        self._process.stdin.flush()
        line = self._process.stdout.readline()
        if not line:
            raise AccountingError("Saldima bridge closed its stdout unexpectedly")
        response: dict[str, Any] = json.loads(line)
        if not response.get("ok"):
            error = response.get("error", {})
            raise AccountingError(
                f"Saldima bridge error [{error.get('code', 'UNKNOWN')}]: {error.get('message', '')}"
            )
        return response

    def reset(self, accounts: list[dict[str, Any]]) -> None:
        self._call({"op": "reset", "accounts": accounts})

    def post(self, transaction: dict[str, Any]) -> None:
        self._call({"op": "post", "transaction": transaction})

    def trial_balance(self, as_of: str) -> dict[str, Any]:
        result: dict[str, Any] = self._call({"op": "trialBalance", "asOf": as_of})["result"]
        return result

    def balance_sheet(self, as_of: str) -> dict[str, Any]:
        result: dict[str, Any] = self._call({"op": "balanceSheet", "asOf": as_of})["result"]
        return result

    def income_statement(self, start: str, end: str) -> dict[str, Any]:
        result: dict[str, Any] = self._call({"op": "incomeStatement", "from": start, "to": end})[
            "result"
        ]
        return result

    def verify(self, as_of: str) -> dict[str, Any]:
        result: dict[str, Any] = self._call({"op": "verify", "asOf": as_of})["result"]
        return result

    def close(self) -> None:
        if self._process.poll() is not None:
            return
        try:
            self._call({"op": "exit"})
        except (AccountingError, OSError):
            pass
        if self._process.stdin is not None:
            self._process.stdin.close()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
