from __future__ import annotations

import csv
from contextlib import chdir
from pathlib import Path
import tempfile
import unittest

import yaml

from rb.metrics import compute_term_metrics
from rb.spec import load_spec
from rb.site import _load_term_details

ROOT = Path(__file__).resolve().parents[1]
KINDS = ["end_minus_start", "end_minus_start_per_year", "pct_change_from_levels", "cagr_from_levels", "mean", "last"]


class ChangeBaselineTests(unittest.TestCase):
    def compute(self, frequency, values, *, fiscal=False, legacy=False):
        attribution = load_spec(ROOT / "spec/attribution_v1.yaml")
        if legacy:
            attribution["defaults"].pop("period_change_baseline")
        attribution["series_overrides"] = {}
        if fiscal:
            attribution["series_overrides"]["synthetic"] = {
                "kind": "period", "period": "us_fiscal_year",
                "fiscal_year_start_month": 10, "fiscal_year_start_day": 1,
            }
        spec = {"sources": {"fred": {"kind": "fred"}},
                "series": {"synthetic": {"source": "fred", "series_id": "synthetic", "frequency": frequency}},
                "metrics": [{"id": kind, "inputs": {"series": "synthetic"},
                             "term_aggregation": {"kind": kind}} for kind in KINDS]}
        with tempfile.TemporaryDirectory() as temp, chdir(temp):
            Path("spec.yaml").write_text(yaml.safe_dump(spec))
            Path("attribution.yaml").write_text(yaml.safe_dump(attribution))
            folder = Path("data/derived/fred/observations")
            folder.mkdir(parents=True)
            (folder / "synthetic.csv").write_text("date,value\n" + "".join(f"{d},{v}\n" for d, v in values))
            compute_term_metrics(spec_path=Path("spec.yaml"), attribution_path=Path("attribution.yaml"),
                presidents_csv=ROOT / "tests/fixtures/presidents_min.csv",
                output_terms_csv=Path("terms.csv"), output_party_csv=Path("party.csv"))
            with Path("terms.csv").open() as stream:
                return {r["metric_id"]: r for r in csv.DictReader(stream) if r["term_start"] == "2025-01-20"}

    def test_monthly_quarterly_calendar_and_fiscal_year_boundaries(self):
        cases = [
            ("M", False, "2025-01-01", "2025-02-01", "2025-03-01"),
            ("Q", False, "2024-10-01", "2025-01-01", "2025-04-01"),
            ("A", False, "2024-01-01", "2025-01-01", "2026-01-01"),
            ("A", True, "2024-01-01", "2025-01-01", "2026-01-01"),
        ]
        for frequency, fiscal, baseline, first, last in cases:
            with self.subTest(frequency=frequency, fiscal=fiscal):
                values = [(baseline, 100), (first, 110), (last, 120)]
                actual = self.compute(frequency, values, fiscal=fiscal)
                legacy = self.compute(frequency, values, fiscal=fiscal, legacy=True)
                self.assertEqual(actual["mean"], legacy["mean"])
                self.assertEqual(actual["last"], legacy["last"])
                self.assertEqual(float(actual["mean"]["value"]), 115)
                for kind in KINDS[:4]:
                    row = actual[kind]
                    self.assertFalse(row["error"])
                    self.assertEqual(row["start_obs_date"], baseline)
                    self.assertEqual(row["end_obs_date"], last)
                self.assertEqual(float(actual["end_minus_start"]["value"]), 20)
                self.assertEqual(float(actual["pct_change_from_levels"]["value"]), 20)
                self.assertEqual(float(legacy["end_minus_start"]["value"]), 10)

    def test_missing_baseline_or_endpoint_has_no_fallback_zero(self):
        for values in [[("2025-01-01", 100)], [("2024-01-01", 100)],
                       [("2024-01-01", ""), ("2025-01-01", 100)]]:
            with self.subTest(values=values):
                actual = self.compute("A", values)
                for kind in KINDS[:4]:
                    self.assertIn(actual[kind]["error"], {"missing boundary observation", "change requires two distinct observations"})
                    self.assertEqual(actual[kind]["value"], "")

    def test_partial_window_falls_back_and_exports_dates(self):
        actual = self.compute("A", [("2025-01-01", 100), ("2026-01-01", 120)])
        for kind in KINDS[:4]:
            row = actual[kind]
            self.assertFalse(row["error"])
            self.assertEqual(row["baseline_fallback"], "true")
            self.assertEqual(row["start_obs_date"], "2025-01-01")
            self.assertEqual(row["end_obs_date"], "2026-01-01")
        self.assertEqual(float(actual["end_minus_start"]["value"]), 20)
        self.assertAlmostEqual(float(actual["end_minus_start_per_year"]["value"]), 20 * 365.25 / 365, places=5)
        self.assertEqual(actual["mean"]["baseline_fallback"], "")
        self.assertEqual(actual["last"]["baseline_fallback"], "")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "terms.csv"
            with path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(actual["mean"]))
                writer.writeheader()
                writer.writerows(actual.values())
            exported = _load_term_details(path)
            term = exported["end_minus_start"][0]
            self.assertTrue(term["partial_coverage"])
            self.assertEqual(term["start_obs_date"], "2025-01-01")
            self.assertEqual(term["end_obs_date"], "2026-01-01")
            self.assertNotIn("partial_coverage", exported["mean"][0])

    def test_baseline_skips_missing_values(self):
        actual = self.compute("A", [("2023-01-01", 100), ("2024-01-01", ""), ("2025-01-01", 120)])
        self.assertEqual(actual["end_minus_start"]["start_obs_date"], "2023-01-01")
        self.assertEqual(float(actual["end_minus_start"]["value"]), 20)

    def test_daily_boundaries_are_unchanged(self):
        values = [("2025-01-17", 100), ("2025-01-21", 110), ("2025-02-01", 120)]
        self.assertEqual(self.compute("D", values), self.compute("D", values, legacy=True))


if __name__ == "__main__":
    unittest.main()
