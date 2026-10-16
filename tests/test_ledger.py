import csv
import os
import tempfile
import unittest
from pathlib import Path

from splitpay.ledger import record_expenses


EXPENSE = {"date": "2026-01-31", "purpose": "Dinner", "amount": "90.00", "paid_by": "Alice"}


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["SPLITPAY_DATA_DIR"] = self.tmp.name
        self.addCleanup(os.environ.pop, "SPLITPAY_DATA_DIR")

    def rows(self, result):
        with (Path(self.tmp.name) / result["file"]).open(newline="", encoding="utf-8") as handle:
            return list(csv.reader(handle))

    def test_creates_then_appends(self):
        first = record_expenses([EXPENSE])
        self.assertEqual(first["file"], f"{first['session_id']}_expenses.csv")
        second = record_expenses([{**EXPENSE, "purpose": "Taxi", "amount": 12.5, "paid_by": "Bob"}], first["session_id"])
        self.assertEqual(second["session_id"], first["session_id"])
        self.assertEqual(self.rows(first), [
            ["Date of expense", "Purpose", "Amount", "Paid by"],
            ["2026-01-31", "Dinner", "90.00", "Alice"],
            ["2026-01-31", "Taxi", "12.50", "Bob"],
        ])

    def test_invalid_batch_writes_nothing(self):
        with self.assertRaises(ValueError):
            record_expenses([EXPENSE, {**EXPENSE, "date": "31/01/2026"}])
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])

    def test_rejects_bad_input(self):
        for expense in ({**EXPENSE, "amount": "0"}, {**EXPENSE, "purpose": " "}, {**EXPENSE, "paid_by": "A,B"}, {"date": "2026-01-31"}):
            with self.assertRaises(ValueError):
                record_expenses([expense])

    def test_rejects_unknown_or_unsafe_session(self):
        for session_id in ("../x", "0" * 32):
            with self.assertRaises(ValueError):
                record_expenses([EXPENSE], session_id)

    def test_formula_purpose_is_neutralized(self):
        result = record_expenses([{**EXPENSE, "purpose": "=SUM(A1)"}])
        self.assertEqual(self.rows(result)[1][1], "'=SUM(A1)")


if __name__ == "__main__":
    unittest.main()
