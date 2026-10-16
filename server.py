"""Run SplitPay MCP over stdio, Streamable HTTP, or legacy SSE."""

import argparse

from fastmcp import FastMCP

from splitpay.tools import add_expense, current_shares, show_balances, total_paid


mcp = FastMCP(
    name="SplitPay MCP",
    instructions=(
        "Stateless expense calculations in one two-decimal currency. "
        "Use add_expense, accumulate its share column with current_shares and "
        "its paid column with total_paid, then call show_balances. "
        "Keep each group's totals separately in the caller. Flat results are TSV; "
        "nested reports are TOON. Amounts are decimal strings. "
        "Do not add the same expense twice to accumulated totals."
    ),
)

for tool in (add_expense, current_shares, total_paid, show_balances):
    mcp.tool(annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    })(tool)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SplitPay MCP server.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: loopback only)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--transport", choices=("stdio", "streamable-http", "http", "sse"), default="streamable-http")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()