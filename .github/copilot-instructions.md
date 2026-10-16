# SplitPay MCP

- Python 3.11+; FastMCP registration in server.py, tool adapters in splitpay/tools.py,
  and transport-independent money calculations in splitpay/expenses.py.
- Keep the four tools stateless. Callers own each group's cumulative totals.
- Use integer cents and Decimal validation; never use float arithmetic for money.
- Successful flat results are TSV; nested reports use the official toon-format encoder.
  Use ToolResult with text content only, without JSON structured content.
- Run `python -m unittest discover -s tests -v` after changes and keep README.md current.
- FastMCP documentation: https://gofastmcp.com/servers/tools
- Official Python MCP SDK: https://github.com/modelcontextprotocol/python-sdk
- MCP protocol documentation: https://modelcontextprotocol.io/llms-full.txt