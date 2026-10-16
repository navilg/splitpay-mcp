import csv
import os
import tempfile
import unittest
from pathlib import Path

from splitpay.ledger import COLUMNS, read_expenses, record_expenses


EXPENSE = {"date": "2026-01-31", "purpose": "Dinner", "amount": "90.00", "paid_by": "Alice", "shared_with": "Alice,Bob"}


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
            ["Date of expense", "Purpose", "Amount", "Paid by", "Alice", "Bob"],
            ["2026-01-31", "Dinner", "90.00", "Alice", "YES", "YES"],
            ["2026-01-31", "Taxi", "12.50", "Bob", "YES", "YES"],
        ])

    def test_new_user_added_as_column(self):
        first = record_expenses([EXPENSE])
        record_expenses([{**EXPENSE, "shared_with": "Carol"}], first["session_id"])
        rows = self.rows(first)
        self.assertEqual(rows[0][4:], ["Alice", "Bob", "Carol"])
        self.assertEqual(rows[1][4:], ["YES", "YES", "NO"])
        self.assertEqual(rows[2][4:], ["NO", "NO", "YES"])

    def test_invalid_batch_writes_nothing(self):
        with self.assertRaises(ValueError):
            record_expenses([EXPENSE, {**EXPENSE, "date": "31/01/2026"}])
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])

    def test_rejects_bad_input(self):
        for expense in ({**EXPENSE, "amount": "0"}, {**EXPENSE, "purpose": " "}, {**EXPENSE, "paid_by": "A,B"}, {"date": "2026-01-31"}, {**EXPENSE, "shared_with": "A,A"}):
            with self.assertRaises(ValueError):
                record_expenses([expense])

    def test_rejects_unknown_or_unsafe_session(self):
        for session_id in ("../x", "0" * 32):
            with self.assertRaises(ValueError):
                record_expenses([EXPENSE], session_id)

    def test_formula_purpose_is_neutralized(self):
        result = record_expenses([{**EXPENSE, "purpose": "=SUM(A1)"}])
        self.assertEqual(self.rows(result)[1][1], "'=SUM(A1)")

    def test_reads_all_rows_without_modifying_file(self):
        result = record_expenses([{**EXPENSE, "purpose": 'Dinner, "friends"'}])
        record_expenses([{**EXPENSE, "shared_with": "Carol"}], result["session_id"])
        path = Path(self.tmp.name) / result["file"]
        before = path.read_bytes()
        self.assertEqual(read_expenses(result["session_id"]), self.rows(result))
        self.assertEqual(path.read_bytes(), before)

    def test_read_rejects_unknown_or_unsafe_session(self):
        for session_id in ("../x", "/etc/passwd", "", "0" * 32):
            with self.subTest(session_id=session_id), self.assertRaises(ValueError):
                read_expenses(session_id)
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])

    def test_read_header_only_and_invalid_csv(self):
        path = Path(self.tmp.name) / f"{'0' * 32}_expenses.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(COLUMNS)
        self.assertEqual(read_expenses("0" * 32), [list(COLUMNS)])
        for content in ("", "wrong,header\n", ",".join(COLUMNS) + "\nshort,row\n"):
            path.write_text(content, encoding="utf-8")
            with self.subTest(content=content), self.assertRaises(ValueError):
                read_expenses("0" * 32)


if __name__ == "__main__":
    unittest.main()
