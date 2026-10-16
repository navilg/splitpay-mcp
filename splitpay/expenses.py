"""Exact two-decimal money calculations, independent of MCP transports."""

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import TypeAlias


Amount: TypeAlias = str | int | float
Amounts: TypeAlias = Mapping[str, Amount]
MAX_AMOUNT = Decimal("1000000000000")


def _name(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("User names must be strings.")
    name = value.strip()
    if not name or "," in name or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("User names must be nonempty and cannot contain commas or control characters.")
    return name


def _cents(value: Amount) -> int:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("Amounts must be decimal strings or numbers, not booleans.")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("Amounts must be valid decimal numbers.") from error
    if not amount.is_finite() or amount < 0 or amount > MAX_AMOUNT:
        raise ValueError("Amounts must be finite and between 0 and 1000000000000.")
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Amounts must have at most two decimal places.")
    return int(amount * 100)


def _amounts(values: Amounts) -> dict[str, int]:
    result = {}
    for raw_name, value in values.items():
        name = _name(raw_name)
        if name in result:
            raise ValueError(f"Duplicate user after trimming whitespace: {name}.")
        result[name] = _cents(value)
    return result


def money(cents: int) -> str:
    """Format integer cents without floating-point rounding."""
    sign = "-" if cents < 0 else ""
    whole, fraction = divmod(abs(cents), 100)
    return f"{sign}{whole}.{fraction:02d}"


def split_expense(participants: str, paid: Amounts) -> list[dict[str, str]]:
    """Split total payments equally, allocating leftover cents in input order."""
    names = [_name(value) for value in participants.split(",")]
    if len(set(names)) != len(names):
        raise ValueError("Participants must not contain duplicate names.")
    payments = _amounts(paid)
    outsiders = set(payments) - set(names)
    if outsiders:
        raise ValueError(f"Payers must be participants: {', '.join(sorted(outsiders))}.")
    total = sum(payments.values())
    if total == 0:
        raise ValueError("An expense must have a positive total payment.")
    base_share, remainder = divmod(total, len(names))
    rows = []
    for index, name in enumerate(names):
        share = base_share + (index < remainder)
        payment = payments.get(name, 0)
        rows.append({"user": name, "paid": money(payment), "share": money(share), "balance": money(payment - share)})
    return rows


def accumulate(previous: Amounts, additions: Amounts, column: str) -> list[dict[str, str]]:
    """Add each user's incremental amount to their previous cumulative total."""
    totals = _amounts(previous)
    for name, amount in _amounts(additions).items():
        totals[name] = totals.get(name, 0) + amount
        if totals[name] > int(MAX_AMOUNT) * 100:
            raise ValueError(f"Cumulative amount exceeds the supported limit for {name}.")
    return [{"user": name, column: money(amount)} for name, amount in totals.items()]


def balance_report(shares: Amounts, paid: Amounts) -> dict[str, object]:
    """Report positive balances as surplus and negative balances as deficiency."""
    owed = _amounts(shares)
    payments = _amounts(paid)
    names = dict.fromkeys([*owed, *payments])
    rows = []
    for name in names:
        share = owed.get(name, 0)
        payment = payments.get(name, 0)
        balance = payment - share
        rows.append({
            "user": name,
            "share": money(share),
            "paid": money(payment),
            "balance": money(balance),
            "deficiency": money(max(-balance, 0)),
            "surplus": money(max(balance, 0)),
            "status": "surplus" if balance > 0 else "deficient" if balance < 0 else "settled",
        })
    total_shares = sum(owed.values())
    total_paid = sum(payments.values())
    return {
        "summary": {
            "total_shares": money(total_shares),
            "total_paid": money(total_paid),
            "difference": money(total_paid - total_shares),
            "totals_match": total_paid == total_shares,
        },
        "users": rows,
    }