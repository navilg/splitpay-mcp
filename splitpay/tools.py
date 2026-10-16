"""MCP-facing tools; all state is explicitly supplied by the caller."""

from typing import TypeAlias

from fastmcp.tools import ToolResult
from pydantic import StrictFloat, StrictInt, StrictStr
from toon_format import encode

from splitpay.expenses import accumulate, balance_report, split_expense
from splitpay.formatting import to_tsv
from splitpay.ledger import record_expenses


UserAmounts: TypeAlias = dict[str, StrictStr | StrictInt | StrictFloat]


def add_expense(participants: str, paid: UserAmounts) -> ToolResult:
    """Split an expense equally and return TSV: user, paid, share, balance.

    Share is the amount owed, not a net balance. Positive balance means surplus.
    Leftover cents go to participants in their supplied order. No state is saved.

    Args:
        participants: Comma-separated, case-sensitive names, e.g. Alice,Bob,Carol.
        paid: Amount paid by each payer, e.g. {"Alice": "60.00", "Bob": "30.00"}.
            Payers must be participants; omitted participants paid zero.
            Use one currency and at most two decimal places; strings are preferred.
    """
    return ToolResult(content=to_tsv(split_expense(participants, paid), ("user", "paid", "share", "balance")))


def current_shares(last_shares: UserAmounts, new_shares: UserAmounts) -> ToolResult:
    """Add incremental amounts owed to previous totals; return TSV: user, share.

    Includes users present in either input, treating missing amounts as zero.
    No state is saved. Pass an empty object for last_shares on the first call.
    Do not pass net balances or already-cumulative totals as new_shares.

    Args:
        last_shares: Previous cumulative amounts owed per user.
        new_shares: Additional amounts owed from new expenses, not replacements.
    """
    return ToolResult(content=to_tsv(accumulate(last_shares, new_shares, "share"), ("user", "share")))


def total_paid(last_paid: UserAmounts, new_paid: UserAmounts) -> ToolResult:
    """Add new expense payments to previous totals; return TSV: user, paid.

    Includes users present in either input, treating missing amounts as zero.
    No state is saved. Pass an empty object for last_paid on the first call.
    These are expense payments, not reimbursements between friends.

    Args:
        last_paid: Previous cumulative expense payments per user.
        new_paid: Additional expense payments per user, not cumulative totals.
    """
    return ToolResult(content=to_tsv(accumulate(last_paid, new_paid, "paid"), ("user", "paid")))


def record_expenses_csv(expenses: list[dict[str, StrictStr | StrictInt | StrictFloat]], session_id: str | None = None) -> ToolResult:
    """Append expenses to a session CSV file; return TSV: session_id, file, rows_added.

    Omit session_id on the first call: a unique session id is generated and
    <session_id>_expenses.csv is created with columns Date of expense, Purpose,
    Amount, Paid by, plus one column per user holding YES if the expense is shared
    with that user, else NO. Users first seen later get a new column (NO for earlier
    rows). Pass the returned session_id on later calls to append.
    This only records a ledger; it does not update cumulative totals.

    Args:
        expenses: Expenses to add, each {"date": "2026-01-31", "purpose": "Dinner",
            "amount": "90.00", "paid_by": "Alice",
            "shared_with": "Alice,Bob"}. Date is YYYY-MM-DD; amount is
            positive with at most two decimal places. All are rejected if any is invalid.
        session_id: Session id returned by the first call; omit to start a new session.
    """
    result = record_expenses(expenses, session_id)
    return ToolResult(content=to_tsv([result], ("session_id", "file", "rows_added")))


def show_balances(shares: UserAmounts, paid: UserAmounts) -> ToolResult:
    """Return a TOON report of each user's deficiency or surplus and group totals.

    Balance = paid - share: positive is surplus (owed money), negative is
    deficient (owes money), zero is settled. Missing users have zero amounts.
    summary.totals_match=false flags inconsistent supplied group totals.
    No state is saved; this tool does not transfer money or record repayments.

    Args:
        shares: Cumulative amounts owed per user, from current_shares.
        paid: Cumulative amounts paid per user, from total_paid.
    """
    return ToolResult(content=encode(balance_report(shares, paid)))