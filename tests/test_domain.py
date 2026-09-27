import random
import unittest
from decimal import Decimal
from kpi_management.domain import (
    calculate,
    category,
    decimal,
    display_value,
    eligible,
    normalized_weights,
    period_containing,
    periods,
    typed_value,
    valid_rating,
    validate_weights,
)


def row(weight, index=1, excluded=False, self_rating=None, final_rating=None):
    return dict(
        kpi_component=f"KPI {index}",
        structure_item_id=f"row-{index}",
        idx=index,
        original_weight=weight,
        not_applicable=excluded,
        self_rating=weight if self_rating is None else self_rating,
        final_rating=weight if final_rating is None else final_rating,
        self_rating_entered=1,
        final_rating_entered=1,
    )


class TestCalendar(unittest.TestCase):
    def test_canonical_periods(self):
        cases = [
            ("2024-02-17", "Monthly", ("2024-02-01", "2024-02-29", "2024-02")),
            ("2025-04-15", "Quarterly", ("2025-04-01", "2025-06-30", "2025-Q2")),
            ("2025-12-31", "Semi-Annual", ("2025-07-01", "2025-12-31", "2025-H2")),
        ]
        for d, f, expected in cases:
            with self.subTest(d=d, f=f):
                self.assertEqual(tuple(map(str, period_containing(d, f))), expected)

    def test_no_partial_quarter(self):
        result = list(periods("2025-04-15", "2025-12-31", "Quarterly"))
        self.assertEqual([p[2] for p in result], ["2025-Q3", "2025-Q4"])
        self.assertEqual(list(periods("2025-04-15", "2025-05-15", "Quarterly")), [])

    def test_open_period_excluded(self):
        self.assertEqual(
            list(
                periods(
                    "2025-04-01", "2025-06-30", "Quarterly", closed_before="2025-06-30"
                )
            ),
            [],
        )
        self.assertEqual(
            len(
                list(
                    periods(
                        "2025-04-01",
                        "2025-06-30",
                        "Quarterly",
                        closed_before="2025-07-01",
                    )
                )
            ),
            1,
        )

    def test_cutoff_and_expired_catchup(self):
        self.assertEqual(
            [
                p[2]
                for p in periods(
                    "2024-01-01",
                    "2024-12-31",
                    "Quarterly",
                    closed_before="2026-01-01",
                    not_before="2024-04-02",
                )
            ],
            ["2024-Q3", "2024-Q4"],
        )

    def test_all_month_boundaries_over_leap_cycle(self):
        for year in range(2023, 2029):
            for frequency, n in [("Monthly", 12), ("Quarterly", 4), ("Semi-Annual", 2)]:
                result = list(periods(f"{year}-01-01", f"{year}-12-31", frequency))
                self.assertEqual(len(result), n)
                self.assertEqual(
                    sum((e - s).days + 1 for s, e, k in result),
                    366 if year in [2024, 2028] else 365,
                )

    def test_invalid_interval(self):
        with self.assertRaises(ValueError):
            list(periods("2025-12-31", "2025-01-01", "Quarterly"))

    def test_expired_assignment_remains_eligible(self):
        a = dict(
            docstatus=1,
            start_date="2025-04-01",
            end_date="2025-06-30",
            review_frequency="Quarterly",
        )
        s = dict(docstatus=1, effective_from="2025-01-01", effective_to=None)
        self.assertEqual(
            eligible(a, s, "2025-04-01", "2025-06-30", "2026-01-01"), "2025-Q2"
        )
        for change in (
            {"docstatus": 0},
            {"start_date": "2025-04-02"},
            {"end_date": "2025-06-29"},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                eligible({**a, **change}, s, "2025-04-01", "2025-06-30", "2026-01-01")

    def test_eligibility_guards(self):
        a = dict(
            docstatus=1,
            start_date="2025-01-01",
            end_date="2025-12-31",
            review_frequency="Quarterly",
        )
        s = dict(docstatus=1, effective_from="2025-01-01")
        for start, end, today, ss in [
            ("2025-04-01", "2025-06-30", "2025-06-30", s),
            ("2025-04-02", "2025-06-30", "2026-01-01", s),
            ("2025-04-01", "2025-06-30", "2026-01-01", {**s, "docstatus": 2}),
            (
                "2025-04-01",
                "2025-06-30",
                "2026-01-01",
                {**s, "effective_to": "2025-06-29"},
            ),
        ]:
            with (
                self.subTest(start=start, end=end, ss=ss),
                self.assertRaises(ValueError),
            ):
                eligible(a, ss, start, end, today)


class TestTypedValues(unittest.TestCase):
    def test_seven_indicator_types(self):
        cases = [
            ({"indicator": "Percentage", "target_number": 95}, "95%"),
            ({"indicator": "Number", "target_number": 0}, "0"),
            (
                {"indicator": "Currency", "target_number": 1000, "currency": "TZS"},
                "1000 TZS",
            ),
            (
                {"indicator": "Duration", "target_number": 4, "duration_unit": "Hours"},
                "4 Hours",
            ),
            ({"indicator": "Yes No", "target_choice": "No"}, "No"),
            ({"indicator": "Date", "target_date": "2025-06-30"}, "2025-06-30"),
            ({"indicator": "Text", "target_text": "Deliver plan"}, "Deliver plan"),
        ]
        for data, display in cases:
            with self.subTest(indicator=data["indicator"]):
                self.assertEqual(display_value(data, "target"), display)

    def test_negative_and_over_100_percentage_are_valid(self):
        for value in [-15, 120, 0]:
            self.assertEqual(
                typed_value(
                    {"indicator": "Percentage", "target_number": value}, "target"
                ),
                Decimal(value),
            )

    def test_invalid_values(self):
        cases = [
            {"indicator": "Duration", "target_number": -1, "duration_unit": "Hours"},
            {"indicator": "Duration", "target_number": 1},
            {"indicator": "Currency", "target_number": 1},
            {"indicator": "Yes No", "target_choice": "Maybe"},
            {"indicator": "Date", "target_date": "2025-02-30"},
            {"indicator": "Text", "target_text": " "},
            {"indicator": "Number", "target_number": "NaN"},
            {"indicator": "Number", "target_number": 1, "target_text": "wrong"},
        ]
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ValueError):
                typed_value(data, "target")

    def test_unused_numeric_default_zero_is_not_operative(self):
        self.assertEqual(
            typed_value(
                {"indicator": "Yes No", "target_choice": "Yes", "target_number": 0},
                "target",
            ),
            "Yes",
        )

    def test_decimal_input_precision_and_finiteness(self):
        for value in [
            "NaN",
            "Infinity",
            "-Infinity",
            None,
            "",
            True,
            "garbage",
            "1.001",
        ]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                decimal(value, 2)
        self.assertEqual(decimal("0.00", 2), 0)

    def test_duration_units(self):
        for unit in ["Hours", "Days", "Weeks", "Months", "Years"]:
            self.assertEqual(
                display_value(
                    {
                        "indicator": "Duration",
                        "actual_number": 2,
                        "duration_unit": unit,
                    },
                    "actual",
                ),
                "2 " + unit,
            )


class TestScoring(unittest.TestCase):
    def test_specification_example(self):
        rows = [
            row(40, 1, self_rating=32, final_rating=36),
            row(30, 2, self_rating=24, final_rating=21),
            row(20, 3, True, 0, 0),
            row(10, 4, self_rating=8, final_rating=10),
        ]
        results, totals = calculate(rows)
        self.assertEqual(
            [r["effective_weight"] for r in results],
            list(map(Decimal, ["50", "37.5", "0", "12.5"])),
        )
        self.assertEqual(totals["self_total"], Decimal("80.00"))
        self.assertEqual(totals["final_total"], Decimal("83.75"))
        self.assertEqual(category(totals["final_total"]), "Exceeds Expectations")

    def test_largest_remainder_order(self):
        self.assertEqual(
            normalized_weights([row(20, 1), row(20, 2), row(20, 3), row(40, 4, True)]),
            list(map(Decimal, ["33.34", "33.33", "33.33", "0"])),
        )

    def test_all_excluded(self):
        results, totals = calculate([row(40, 1, True), row(60, 2, True)])
        self.assertIsNone(totals["self_total"])
        self.assertIsNone(totals["final_total"])
        self.assertEqual(totals["effective_weight_total"], 0)
        self.assertEqual(totals["excluded_weight"], 100)

    def test_one_applicable_and_raw_cap(self):
        results, totals = calculate([row(40, 1, True), row(60, 2)])
        self.assertEqual(totals["final_total"], 100)
        with self.assertRaises(ValueError):
            valid_rating(61, 60)

    def test_missing_flags_not_zero(self):
        r = row(100)
        r["self_rating_entered"] = 0
        r["self_rating"] = 0
        results, totals = calculate([r])
        self.assertIsNone(totals["self_total"])
        r["self_rating_entered"] = 1
        results, totals = calculate([r])
        self.assertEqual(totals["self_total"], 0)

    def test_half_up(self):
        results, totals = calculate(
            [row(8, 1, final_rating=0.01), row(72, 2, final_rating=0), row(20, 3, True)]
        )
        self.assertEqual(results[0]["final_points"], Decimal("0.01"))

    def test_categories_complete_and_boundary_correct(self):
        for value, label in [
            ("0", "Poor"),
            ("39.99", "Poor"),
            ("40", "Improvement Needed"),
            ("59.99", "Improvement Needed"),
            ("60", "Meets Expectations"),
            ("70.99", "Meets Expectations"),
            ("71", "Exceeds Expectations"),
            ("89.99", "Exceeds Expectations"),
            ("90", "Outstanding"),
            ("100", "Outstanding"),
        ]:
            with self.subTest(value=value):
                self.assertEqual(category(value), label)
        for value in [-1, 101]:
            with self.assertRaises(ValueError):
                category(value)

    def test_invalid_ratings(self):
        for value in [-1, 10.01, "NaN", "Infinity", "1.001", None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                valid_rating(value, 10)

    def test_weights(self):
        validate_weights([row(40, 1), row(60, 2)])
        for rows in [[], [row(99)], [row(-1), row(101, 2)], [row(40), row(60)]]:
            with self.assertRaises(ValueError):
                validate_weights(rows)

    def test_randomized_invariants(self):
        random.seed(417)
        for _ in range(1000):
            count = random.randint(1, 30)
            cuts = [0] + sorted(random.sample(range(1, 10000), count - 1)) + [10000]
            weights = [Decimal(cuts[i + 1] - cuts[i]) / 100 for i in range(count)]
            rows = [row(w, i + 1, random.random() < 0.3) for i, w in enumerate(weights)]
            results, totals = calculate(rows)
            if any(not r["not_applicable"] for r in rows):
                self.assertEqual(sum(r["effective_weight"] for r in results), 100)
                self.assertEqual(totals["final_total"], 100)
            for r, result in zip(rows, results):
                if r["not_applicable"]:
                    self.assertEqual(result["final_points"], 0)


if __name__ == "__main__":
    unittest.main()

