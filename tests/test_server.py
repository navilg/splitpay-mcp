import csv
import os
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport
from toon_format import decode

from server import main, mcp
from splitpay.formatting import to_tsv


ROOT = Path(__file__).resolve().parents[1]


class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = Client(mcp)
        await self.client.__aenter__()

    async def asyncTearDown(self):
        await self.client.__aexit__(None, None, None)

    async def call_text(self, name, arguments):
        result = await self.client.call_tool(name, arguments)
        self.assertIsNone(result.structured_content)
        self.assertEqual(len(result.content), 1)
        self.assertEqual(result.content[0].type, "text")
        return result.content[0].text

    async def test_tool_discovery(self):
        tools = await self.client.list_tools()
        self.assertEqual({tool.name for tool in tools}, {"splitpay_add_expense", "splitpay_current_shares", "splitpay_total_paid", "splitpay_show_balances", "splitpay_record_expenses_csv", "splitpay_read_expenses_csv"})
        for tool in tools:
            self.assertIsNone(tool.outputSchema)
            self.assertEqual(tool.annotations.readOnlyHint, tool.name != "splitpay_record_expenses_csv")

    async def test_csv_record_and_read(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"SPLITPAY_DATA_DIR": directory}):
            saved = await self.call_text("splitpay_record_expenses_csv", {"expenses": [{
                "date": "2026-01-31", "purpose": 'Dinner, "friends"', "amount": "90.00",
                "paid_by": "Alice", "shared_with": "Alice,Bob",
            }]})
            session_id = next(csv.DictReader(StringIO(saved), delimiter="\t"))["session_id"]
            text = await self.call_text("splitpay_read_expenses_csv", {"session_id": session_id})
            self.assertEqual(list(csv.reader(StringIO(text), delimiter="\t")), [
                ["Date of expense", "Purpose", "Amount", "Paid by", "Alice", "Bob"],
                ["2026-01-31", 'Dinner, "friends"', "90.00", "Alice", "YES", "YES"],
            ])
            for invalid in ("../x", "0" * 32):
                result = await self.client.call_tool(
                    "splitpay_read_expenses_csv", {"session_id": invalid}, raise_on_error=False,
                )
                self.assertTrue(result.is_error)

    async def test_two_expense_workflow(self):
        shares = {}
        paid = {}
        for payments in ({"Alice": "60.00", "Bob": "30.00"}, {"Carol": "30.00"}):
            expense = await self.call_text("splitpay_add_expense", {"participants": "Alice,Bob,Carol", "paid": payments})
            rows = list(csv.DictReader(StringIO(expense), delimiter="\t"))
            share_text = await self.call_text("splitpay_current_shares", {
                "last_shares": shares, "new_shares": {row["user"]: row["share"] for row in rows},
            })
            paid_text = await self.call_text("splitpay_total_paid", {
                "last_paid": paid, "new_paid": {row["user"]: row["paid"] for row in rows},
            })
            shares = {row["user"]: row["share"] for row in csv.DictReader(StringIO(share_text), delimiter="\t")}
            paid = {row["user"]: row["paid"] for row in csv.DictReader(StringIO(paid_text), delimiter="\t")}
        self.assertEqual(shares, {"Alice": "40.00", "Bob": "40.00", "Carol": "40.00"})
        report = decode(await self.call_text("splitpay_show_balances", {"shares": shares, "paid": paid}))
        self.assertEqual(report["summary"], {
            "total_shares": "120.00", "total_paid": "120.00", "difference": "0.00", "totals_match": True,
        })
        self.assertEqual([row["balance"] for row in report["users"]], ["20.00", "-10.00", "-10.00"])

    async def test_validation_errors_are_mcp_errors(self):
        cases = [
            ("splitpay_add_expense", {"participants": "Alice", "paid": {"Alice": -1}}),
            ("splitpay_add_expense", {"participants": "Alice", "paid": {"Alice": True}}),
            ("splitpay_add_expense", {"participants": "Alice,Alice", "paid": {"Alice": 1}}),
            ("splitpay_current_shares", {"last_shares": {}, "new_shares": {"Alice": "0.001"}}),
            ("splitpay_total_paid", {"last_paid": {"Alice": "NaN"}, "new_paid": {}}),
        ]
        for name, arguments in cases:
            with self.subTest(tool=name, arguments=arguments):
                result = await self.client.call_tool(name, arguments, raise_on_error=False)
                self.assertTrue(result.is_error)

    async def test_empty_tsv_keeps_header(self):
        self.assertEqual(await self.call_text("splitpay_current_shares", {"last_shares": {}, "new_shares": {}}), "user\tshare")

    async def test_stdio_round_trip(self):
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as log:
            transport = PythonStdioTransport(
                script_path=str(ROOT / "server.py"),
                python_cmd=sys.executable,
                args=["--transport", "stdio"],
                cwd=str(ROOT),
                keep_alive=False,
                log_file=log,
            )
            async with Client(transport) as client:
                self.assertEqual(len(await client.list_tools()), 6)
                result = await client.call_tool("splitpay_add_expense", {"participants": "Alice,Bob", "paid": {"Alice": "10.00"}})
                self.assertIn("Bob\t0.00\t5.00\t-5.00", result.content[0].text)
                self.assertIsNone(result.structured_content)


class FormattingAndCLITests(unittest.TestCase):
    def test_tsv_quotes_special_characters(self):
        rows = [{"user": 'Alice "A"', "paid": "1.00"}]
        text = to_tsv(rows, ("user", "paid"))
        self.assertEqual(list(csv.DictReader(StringIO(text), delimiter="\t")), rows)

    def test_network_transports(self):
        for transport in ("streamable-http", "http", "sse"):
            with self.subTest(transport=transport), patch("sys.argv", ["server.py", "--transport", transport]), patch.object(mcp, "run") as run:
                main()
                run.assert_called_once_with(transport=transport, host="127.0.0.1", port=8000)

    def test_stdio_does_not_receive_network_options(self):
        with patch("sys.argv", ["server.py", "--transport", "stdio"]), patch.object(mcp, "run") as run:
            main()
            run.assert_called_once_with(transport="stdio")


if __name__ == "__main__":
    unittest.main()