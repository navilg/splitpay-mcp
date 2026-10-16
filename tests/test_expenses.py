import unittest

from splitpay.expenses import accumulate, balance_report, split_expense


class ExpenseTests(unittest.TestCase):
    def test_split_preserves_every_cent(self):
        rows = split_expense("Alice, Bob, Carol", {"Alice": "100.00"})
        self.assertEqual([row["share"] for row in rows], ["33.34", "33.33", "33.33"])
        self.assertEqual([row["balance"] for row in rows], ["66.66", "-33.33", "-33.33"])

    def test_multiple_payers(self):
        self.assertEqual(split_expense("Alice,Bob", {"Alice": 20, "Bob": 10}), [
            {"user": "Alice", "paid": "20.00", "share": "15.00", "balance": "5.00"},
            {"user": "Bob", "paid": "10.00", "share": "15.00", "balance": "-5.00"},
        ])

    def test_subcent_split_and_single_participant(self):
        self.assertEqual([row["share"] for row in split_expense("A,B,C", {"A": "0.01"})], ["0.01", "0.00", "0.00"])
        self.assertEqual(split_expense("Alice", {"Alice": "0.10"})[0]["balance"], "0.00")

    def test_accumulate_unions_names_without_mutation(self):
        previous = {"Alice": "0.10", "Carol": 5}
        self.assertEqual(accumulate(previous, {"Alice": "0.20", "Bob": 3}, "share"), [
            {"user": "Alice", "share": "0.30"},
            {"user": "Carol", "share": "5.00"},
            {"user": "Bob", "share": "3.00"},
        ])
        self.assertEqual(previous, {"Alice": "0.10", "Carol": 5})

    def test_balances_and_missing_names(self):
        report = balance_report({"Alice": 10, "Bob": 10, "Carol": 0}, {"Alice": 20})
        self.assertEqual(report["summary"]["totals_match"], True)
        self.assertEqual([row["status"] for row in report["users"]], ["surplus", "deficient", "settled"])
        self.assertEqual(report["users"][1]["deficiency"], "10.00")
        self.assertEqual(balance_report({}, {"Alice": 1})["summary"]["difference"], "1.00")

    def test_empty_state(self):
        self.assertEqual(accumulate({}, {}, "paid"), [])
        self.assertEqual(balance_report({}, {})["users"], [])

    def test_invalid_participants(self):
        for names in ("", "Alice,", "Alice,Alice", "Alice, Alice", "Alice\t,Bob"):
            with self.subTest(names=names), self.assertRaises(ValueError):
                split_expense(names, {"Alice": 10})

    def test_invalid_amounts(self):
        for amount in (-1, "NaN", "Infinity", "-Infinity", "0.001", "0.10000000000000000000000000001", "abc", True, "1000000000001"):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                split_expense("Alice", {"Alice": amount})

    def test_invalid_payments(self):
        for payments in ({}, {"Alice": 0}, {"Bob": 1}, {"Alice": 1, " Alice ": 2}):
            with self.subTest(payments=payments), self.assertRaises(ValueError):
                split_expense("Alice", payments)

    def test_cumulative_limit(self):
        with self.assertRaises(ValueError):
            accumulate({"Alice": "1000000000000"}, {"Alice": "0.01"}, "paid")


if __name__ == "__main__":
    unittest.main()