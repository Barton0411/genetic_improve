from __future__ import annotations

import sqlite3
import unittest
from decimal import Decimal

from core.group_report.exact_decimal import (
    ExactDecimalError,
    compare_exact_decimal,
    parse_exact_decimal,
    python_sort_key,
    sqlite_order_by_clause,
)


class ExactDecimalTests(unittest.TestCase):
    def test_normalizes_equivalent_text_and_removes_trailing_zeroes(self):
        equivalents = [
            "1.2300",
            "123e-2",
            Decimal("01.23000"),
        ]
        parsed = [parse_exact_decimal(value) for value in equivalents]
        self.assertTrue(all(value.text == "1.23E+0" for value in parsed))
        self.assertTrue(all(value.sign == 1 for value in parsed))
        self.assertTrue(all(value.adjusted_exponent == 0 for value in parsed))
        self.assertTrue(all(value.digits == "123" for value in parsed))
        self.assertTrue(all(value.value == Decimal("1.23") for value in parsed))

        negative = parse_exact_decimal("-0.0012300")
        self.assertEqual(negative.text, "-1.23E-3")
        self.assertEqual(negative.sign, -1)
        self.assertEqual(negative.adjusted_exponent, -3)
        self.assertEqual(negative.digits, "123")

    def test_zero_and_floats_are_canonical(self):
        for value in (0, 0.0, -0.0, "0.000e99", Decimal("-0")):
            parsed = parse_exact_decimal(value)
            self.assertEqual(parsed.text, "0")
            self.assertEqual(parsed.sqlite_fields(), (0, 0, "0"))
            self.assertEqual(parsed.value, Decimal(0))
        self.assertEqual(parse_exact_decimal(0.1).text, "1E-1")
        self.assertEqual(parse_exact_decimal(1e-7).text, "1E-7")

    def test_rejects_non_finite_or_non_decimal_inputs(self):
        invalid = [
            True,
            None,
            float("nan"),
            float("inf"),
            Decimal("NaN"),
            Decimal("-Infinity"),
            "",
            "1,000",
            "1_000",
            "1.2.3",
        ]
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ExactDecimalError):
                    parse_exact_decimal(value)

    def test_python_key_sorts_signs_scientific_notation_and_close_values(self):
        values = [
            "1e2",
            "-1.001",
            "0",
            "1.0000000000000000000002",
            "-10",
            "1.0000000000000000000001",
            "-1",
            "9.999e1",
            "1.2300",
            "123e-2",
        ]
        ordered = sorted(values, key=python_sort_key)
        self.assertEqual(
            ordered,
            [
                "-10",
                "-1.001",
                "-1",
                "0",
                "1.0000000000000000000001",
                "1.0000000000000000000002",
                "1.2300",
                "123e-2",
                "9.999e1",
                "1e2",
            ],
        )
        descending = sorted(values, key=python_sort_key, reverse=True)
        self.assertEqual(
            descending,
            [
                "1e2",
                "9.999e1",
                "1.2300",
                "123e-2",
                "1.0000000000000000000002",
                "1.0000000000000000000001",
                "0",
                "-1",
                "-1.001",
                "-10",
            ],
        )
        self.assertEqual(compare_exact_decimal("1.2300", "123e-2"), 0)
        self.assertLess(
            compare_exact_decimal(
                "1.0000000000000000000001",
                "1.0000000000000000000002",
            ),
            0,
        )

    def test_sqlite_order_matches_python_for_positive_and_negative_values(self):
        values = [
            "-1e100",
            "-12.01",
            "-12",
            "-1.001",
            "-1.000",
            "-0.000001",
            "0",
            "0.000001",
            "1",
            "1.0000000000000000000001",
            "1.0000000000000000000002",
            "9.999e99",
            "1e100",
        ]
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute(
                """
                CREATE TABLE scores (
                    raw TEXT NOT NULL,
                    decimal_sign INTEGER NOT NULL,
                    decimal_adjusted_exponent INTEGER NOT NULL,
                    decimal_digits TEXT NOT NULL
                )
                """
            )
            for raw in values:
                parsed = parse_exact_decimal(raw)
                connection.execute(
                    "INSERT INTO scores VALUES (?, ?, ?, ?)",
                    (raw, *parsed.sqlite_fields()),
                )

            ascending_clause = sqlite_order_by_clause()
            ascending = [
                row[0]
                for row in connection.execute(
                    f"SELECT raw FROM scores ORDER BY {ascending_clause}"
                )
            ]
            expected = sorted(values, key=python_sort_key)
            self.assertEqual(ascending, expected)

            descending_clause = sqlite_order_by_clause(descending=True)
            descending = [
                row[0]
                for row in connection.execute(
                    f"SELECT raw FROM scores ORDER BY {descending_clause}"
                )
            ]
            self.assertEqual(descending, list(reversed(expected)))
        finally:
            connection.close()

    def test_sqlite_column_names_are_not_an_injection_surface(self):
        with self.assertRaisesRegex(ValueError, "不安全"):
            sqlite_order_by_clause(sign_column="sign; DROP TABLE scores")


if __name__ == "__main__":
    unittest.main()
