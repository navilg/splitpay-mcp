"""CSV expense ledger, one file per session, independent of MCP transports."""

import csv
import os
import re
import uuid
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

from splitpay.expenses import _cents, _name, money


COLUMNS = ("Date of expense", "Purpose", "Amount", "Paid by")
SESSION_ID = re.compile(r"[0-9a-f]{32}")


def data_dir() -> Path:
    """Directory holding session files; override with SPLITPAY_DATA_DIR."""
    return Path(os.environ.get("SPLITPAY_DATA_DIR", "data"))


def _session_path(session_id: str) -> Path:
    return data_dir() / f"{session_id}_expenses.csv"


def _users(value: object) -> list[str]:
    if not isinstance(value, str):
        raise ValueError("shared_with must be comma-separated names, e.g. Alice,Bob.")
    names = [_name(part) for part in value.split(",")]
    if len(set(names)) != len(names):
        raise ValueError("shared_with contains duplicate names.")
    return names


def _row(expense: Mapping[str, object]) -> tuple[list[str], list[str]]:
    missing = [key for key in ("date", "purpose", "amount", "paid_by", "shared_with") if key not in expense]
    if missing:
        raise ValueError(f"Expense is missing: {', '.join(missing)}.")
    raw_date, purpose, amount, paid_by = (expense[key] for key in ("date", "purpose", "amount", "paid_by"))
    if not isinstance(raw_date, str):
        raise ValueError("date must be a YYYY-MM-DD string.")
    try:
        day = date.fromisoformat(raw_date.strip())
    except ValueError as error:
        raise ValueError("date must be a valid YYYY-MM-DD date.") from error
    if not isinstance(purpose, str) or not purpose.strip() or any(ord(c) < 32 or ord(c) == 127 for c in purpose):
        raise ValueError("purpose must be nonempty text without control characters.")
    cents = _cents(amount)  # type: ignore[arg-type]
    if cents <= 0:
        raise ValueError("amount must be positive.")
    purpose = purpose.strip()
    if purpose[0] in "=+-@":
        purpose = "'" + purpose  # prevent spreadsheet formula injection
    payer = _name(paid_by)  # type: ignore[arg-type]
    return [day.isoformat(), purpose, money(cents), payer], _users(expense["shared_with"])


def record_expenses(expenses: Sequence[Mapping[str, object]], session_id: str | None = None) -> dict[str, str]:
    """Append expenses to the session CSV, creating a new session when none is given.

    Each known user has a YES/NO column; users first seen later are added with NO
    for earlier expenses.
    """
    if not expenses:
        raise ValueError("Provide at least one expense.")
    parsed = [_row(expense) for expense in expenses]
    if session_id is None:
        session_id = uuid.uuid4().hex
        path = _session_path(session_id)
        header: list[str] = list(COLUMNS)
        old_rows: list[list[str]] = []
    else:
        session_id = session_id.strip().lower()
        if not SESSION_ID.fullmatch(session_id):
            raise ValueError("session_id must be a value returned by a previous call.")
        path = _session_path(session_id)
        if not path.is_file():
            raise ValueError("Unknown session_id; omit it to start a new session.")
        with path.open(newline="", encoding="utf-8") as handle:
            header, *old_rows = csv.reader(handle)
    users = header[len(COLUMNS):]
    for base, shared in parsed:
        for user in [base[3], *shared]:
            if user not in users:
                users.append(user)
    header = [*COLUMNS, *users]
    width = len(header)
    rows = [row + ["NO"] * (width - len(row)) for row in old_rows]
    rows += [[*base, *("YES" if user in shared else "NO" for user in users)] for base, shared in parsed]
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with temp.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle, lineterminator="\n").writerows([header, *rows])
    temp.replace(path)
    return {"session_id": session_id, "file": path.name, "rows_added": str(len(expenses))}
