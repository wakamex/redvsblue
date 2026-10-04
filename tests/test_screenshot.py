import unittest

from rb.screenshot import select_metrics


class ScreenshotSelectionTests(unittest.TestCase):
    def setUp(self):
        self.metrics = [
            {"metric": "Income growth", "agg": "cagr_from_levels"},
            {"metric": "Poverty change", "agg": "end_minus_start"},
            {"metric": "Poverty change", "agg": "end_minus_start_per_year"},
        ]

    def test_unique_substring(self):
        self.assertEqual(select_metrics(self.metrics, "income", None), [0])

    def test_ambiguous_name_requires_aggregation(self):
        with self.assertRaisesRegex(ValueError, "found 2"):
            select_metrics(self.metrics, "Poverty change", None)
        self.assertEqual(select_metrics(self.metrics, "Poverty change", "end_minus_start"), [1])

    def test_missing_name_and_all(self):
        with self.assertRaisesRegex(ValueError, "found 0"):
            select_metrics(self.metrics, "missing", None)
        self.assertEqual(select_metrics(self.metrics, None, None), [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
