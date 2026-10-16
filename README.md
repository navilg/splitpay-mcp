# SplitPay MCP

A Python 3.11+ MCP server for splitting friends' expenses. Inspired by
[navilg/media-stack-mcp](https://github.com/navilg/media-stack-mcp): FastMCP,
separate tool modules, and a server entry point supporting Streamable HTTP and SSE.
SplitPay also supports stdio for local MCP clients.

## Setup

Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On Linux/macOS, activate with `source .venv/bin/activate` instead.

## Run

```shell
python server.py
```

The default MCP endpoint is `http://127.0.0.1:8000/mcp`. It is an MCP endpoint,
not a browser page or a REST API. Startup options:

```shell
python server.py --transport streamable-http --host 127.0.0.1 --port 8000
python server.py --transport stdio
python server.py --transport sse
```

`http` is an alias for `streamable-http`; legacy SSE uses `/sse`.
The server binds only to loopback by default and has no authentication.
Do not expose it to untrusted networks without an authenticated gateway and TLS.

### VS Code

The included `.vscode/mcp.json` launches stdio using this project's Windows
virtual environment. Open it and select **Start**, then use the four SplitPay
tools in an MCP-enabled chat. On Linux/macOS, change its command to
`${workspaceFolder}/.venv/bin/python`.

You can now debug this MCP server using VS Code: select the project's interpreter,
choose **SplitPay MCP: HTTP** in Run and Debug, and press F5. Connect an MCP client
to `http://127.0.0.1:8000/mcp` to exercise breakpoints in tool functions.

## Tools

| Tool | Inputs | Output |
| --- | --- | --- |
| `add_expense` | `participants`: comma-separated names; `paid`: name-to-amount object | TSV: `user`, `paid`, `share`, `balance` |
| `current_shares` | `last_shares`, `new_shares`: name-to-amount objects | TSV: `user`, `share` |
| `total_paid` | `last_paid`, `new_paid`: name-to-amount objects | TSV: `user`, `paid` |
| `show_balances` | `shares`, `paid`: cumulative name-to-amount objects | TOON: `summary` and `users` |

These are **stateless calculators**, not a database-backed Splitwise service.
There are no accounts, stored groups, saved expenses, or repayment tracking.
The client retains totals separately for each group and supplies them on each call.
Repeating a call with identical inputs produces the same result; adding an expense
to previously updated totals a second time double-counts it.

### Money and names

- Use a single currency with two decimal places for each group; no currency conversion.
- Amounts accept decimal strings (recommended), integers, or JSON numbers. Outputs
  use fixed two-decimal strings to avoid floating-point loss.
- Amounts must be finite, nonnegative, and exactly representable in cents, up to
  1,000,000,000,000 per user, including cumulative totals. Booleans are rejected.
- Names are trimmed, case-sensitive, nonempty, and cannot contain commas or control
  characters. Duplicate participant names and payer names that collide after trimming
  are rejected. Each payer must be a participant. Omitted payers paid zero.
- An expense must have a positive total. Equal splits differ by at most one cent;
  leftover cents go to participants in input order. Thus 100.00 split three ways
  becomes 33.34, 33.33, 33.33, preserving the total exactly.
- **Share** means cumulative expense liability, not a net balance.
  **Balance = paid - share**: positive means surplus (should receive money), negative
  means deficiency (owes money), and zero means settled.
- Accumulation includes the union of users, with missing amounts treated as zero.
  Empty accumulation results still include a TSV header.
- `show_balances` reports mismatched paid/share totals with `totals_match: false`
  and their signed `difference`; it does not silently rebalance inconsistent inputs.

## Example Workflow

Tool arguments use JSON, as required by MCP. Successful payloads are TSV for flat
records or TOON for nested reports, without Markdown fences or duplicate JSON
structured content. MCP itself still uses standard JSON-RPC envelopes; invalid
arguments return standard MCP tool errors.

### 1. Add an expense

Call `add_expense`:

```json
{"participants": "Alice,Bob,Carol", "paid": {"Alice": "60.00", "Bob": "30.00"}}
```

Output (columns are separated by literal tabs):

```tsv
user	paid	share	balance
Alice	60.00	30.00	30.00
Bob	30.00	30.00	0.00
Carol	0.00	30.00	-30.00
```

### 2. Accumulate shares

Call `current_shares`, passing the expense's `share` column as `new_shares`:

```json
{"last_shares": {}, "new_shares": {"Alice": "30.00", "Bob": "30.00", "Carol": "30.00"}}
```

```tsv
user	share
Alice	30.00
Bob	30.00
Carol	30.00
```

For subsequent expenses, supply the returned totals as `last_shares` and only the
additional expense liabilities as `new_shares`, not net balances.

### 3. Accumulate payments

Call `total_paid`, passing the expense's `paid` column as `new_paid`:

```json
{"last_paid": {}, "new_paid": {"Alice": "60.00", "Bob": "30.00", "Carol": "0.00"}}
```

```tsv
user	paid
Alice	60.00
Bob	30.00
Carol	0.00
```

For subsequent expenses, supply these totals as `last_paid` and only new expense
payments as `new_paid`. Do not count reimbursements as new expense payments.

### 4. Show deficiency or surplus

Call `show_balances`:

```json
{"shares": {"Alice": "30.00", "Bob": "30.00", "Carol": "30.00"}, "paid": {"Alice": "60.00", "Bob": "30.00", "Carol": "0.00"}}
```

The nested result is encoded by the official `toon-format` library. Numeric-looking
amount strings are quoted to preserve their exact types and decimal places:

```text
summary:
  total_shares: "90.00"
  total_paid: "90.00"
  difference: "0.00"
  totals_match: true
users[3]{user,share,paid,balance,deficiency,surplus,status}:
  Alice,"30.00","60.00","30.00","0.00","30.00",surplus
  Bob,"30.00","30.00","0.00","0.00","0.00",settled
  Carol,"30.00","0.00","-30.00","30.00","0.00",deficient
```

## Tests

```shell
python -m unittest discover -s tests -v
```

Tests cover cent conservation, multiple payers, cumulative totals, invalid inputs,
TSV parsing, TOON round trips, MCP discovery, a two-expense workflow, CLI transport
selection, and a real MCP stdio subprocess. No external API credentials are needed.
The subprocess test captures stderr in a temporary file for compatibility with
Windows terminal handles and closes the child process when finished.