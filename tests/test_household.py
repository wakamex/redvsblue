from __future__ import annotations

import csv
import json
import tempfile
import unittest
from contextlib import chdir
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import yaml
from openpyxl import Workbook

from rb.metrics import compute_term_metrics
from rb.sources.household import ingest_household_series, parse_household_workbook
from rb.spec import load_spec

ROOT = Path(__file__).resolve().parents[1]


def workbook_bytes(rows):
    """Synthetic spreadsheet using the publisher's year-label conventions."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Poverty Rates"
    sheet.append(["Total Population"])
    sheet.append(["Year", "Historical SPM Poverty Rate"])
    for row in rows:
        sheet.append(row)
    data = BytesIO()
    workbook.save(data)
    workbook.close()
    return data.getvalue()


class HouseholdTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {
            "sheet": "Poverty Rates", "expected_cells": {
                "A1": "Total Population", "A2": "Year", "B2": "Historical SPM Poverty Rate",
            }, "first_data_row": 3, "value_column": 2, "scale": 100,
            "preferred_year_labels": {2013: "2013b"},
            "start_year": 2013, "end_year": 2014, "minimum": 0, "maximum": 100,
        }

    def test_revised_rows_units_footnotes_and_sorting(self):
        data = workbook_bytes([(2014, .12), ("2013a", .14), ("2013b", .13), ("1 Note", None)])
        rows, labels = parse_household_workbook(data, self.cfg)
        self.assertEqual(rows, [(2013, 13), (2014, 12)])
        self.assertEqual(labels[2013], "2013b")
        cfg = {**self.cfg, "preferred_year_labels": {}}
        rows, _ = parse_household_workbook(workbook_bytes([("2013 20, 21", .13), ("2014*", .12)]), cfg)
        self.assertEqual(rows, [(2013, 13), (2014, 12)])

    def test_rejects_schema_drift_missing_years_and_duplicates(self):
        cases = [
            ([("2013a", .13), (2014, .12)], self.cfg, "Preferred row missing"),
            ([("2013b", .13)], self.cfg, "coverage"),
            ([("2013b", .13), (2014, .12), (2014, .11)], self.cfg, "duplicate"),
            ([("2013b", .13), (2014, 120)], self.cfg, "Invalid value"),
            ([("2013b", .13), (2014, .12)], {**self.cfg, "expected_cells": {"B2": "Wrong"}}, "header"),
        ]
        for rows, cfg, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                parse_household_workbook(workbook_bytes(rows), cfg)

    def test_ingest_caches_and_records_selected_rows(self):
        data = workbook_bytes([("2013a", .14), ("2013b", .13), (2014, .12)])
        with tempfile.TemporaryDirectory() as temp, chdir(temp):
            with patch("rb.sources.household.http_get", return_value=(200, {}, data)) as get:
                for refresh in (True, False):
                    ingest_household_series(source_name="synthetic", series_key="poverty",
                        series_cfg={"parse": self.cfg, "units": "percent"},
                        source_cfg={"url": "https://example.test/source.xlsx"}, refresh=refresh)
                self.assertEqual(get.call_count, 1)
            self.assertEqual(Path("data/derived/household/poverty.csv").read_text(),
                             "date,value\n2013-01-01,13\n2014-01-01,12\n")
            meta = json.loads(Path("data/derived/household/poverty.meta.json").read_text())
            self.assertEqual(meta["selected_year_labels"]["2013"], "2013b")
            self.assertEqual(len(meta["sha256"]), 64)

    def test_registry_has_only_four_new_series_and_paired_changes(self):
        spec = load_spec(ROOT / "spec/metrics_v1.yaml")
        metrics = [m for m in spec["metrics"] if m["family"] in {"income", "inequality", "poverty"}]
        self.assertEqual(len(metrics), 8)
        self.assertEqual(len({m["inputs"]["series"] for m in metrics}), 4)

    def test_annual_attribution_and_previous_year_baseline(self):
        spec = load_spec(ROOT / "spec/metrics_v1.yaml")
        spec["metrics"] = [m for m in spec["metrics"] if m["family"] in {"income", "inequality", "poverty"}]
        keys = {m["inputs"]["series"] for m in spec["metrics"]}
        with tempfile.TemporaryDirectory() as temp, chdir(temp):
            Path("spec.yaml").write_text(yaml.safe_dump(spec))
            for key in keys:
                folder = "fred/observations" if spec["series"][key]["source"] == "fred" else "household"
                path = Path("data/derived") / folder / f"{key}.csv"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("date,value\n2020-01-01,8\n2021-01-01,10\n2022-01-01,11\n2023-01-01,12\n2024-01-01,13\n2025-01-01,14\n")
            compute_term_metrics(spec_path=Path("spec.yaml"),
                attribution_path=ROOT / "spec/attribution_v1.yaml",
                presidents_csv=ROOT / "tests/fixtures/presidents_min.csv",
                output_terms_csv=Path("terms.csv"), output_party_csv=Path("party.csv"))
            with Path("terms.csv").open() as stream:
                rows = list(csv.DictReader(stream))
            for row in rows:
                if row["term_start"] == "2021-01-20":
                    self.assertFalse(row["error"])
                    self.assertEqual(row["start_obs_date"], "2020-01-01")
                    self.assertEqual(row["end_obs_date"], "2024-01-01")
                    if row["agg_kind"] == "end_minus_start":
                        self.assertEqual(float(row["value"]), 5)
                    if row["agg_kind"] == "pct_change_from_levels":
                        self.assertAlmostEqual(float(row["value"]), 62.5)
                if row["term_start"] == "2025-01-20":
                    self.assertFalse(row["error"])
                    self.assertEqual(row["start_obs_date"], "2024-01-01")
                    self.assertEqual(row["end_obs_date"], "2025-01-01")
                    if row["agg_kind"] == "end_minus_start":
                        self.assertEqual(float(row["value"]), 1)
                    elif row["agg_kind"] == "pct_change_from_levels":
                        self.assertAlmostEqual(float(row["value"]), 100 / 13, places=5)
                    else:
                        self.assertGreater(float(row["value"]), 0)



if __name__ == "__main__":
    unittest.main()
