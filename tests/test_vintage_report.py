from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from rb.vintage import write_fred_primary_metric_vintage_report


class VintageReportTests(unittest.TestCase):
    def test_vintage_report_rows_cover_ok_and_non_fred_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            spec_path = root / "spec.yaml"
            raw_root = root / "data" / "raw" / "fred"
            (raw_root / "series" / "GDPC1").mkdir(parents=True, exist_ok=True)

            snapshot = raw_root / "series" / "GDPC1" / "20260211T120000Z__sha256_deadbeef.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "realtime_start": "2026-01-22",
                        "realtime_end": "2026-01-22",
                        "seriess": [
                            {
                                "id": "GDPC1",
                                "realtime_start": "2026-01-22",
                                "realtime_end": "2026-01-22",
                                "observation_start": "1947-01-01",
                                "observation_end": "2025-07-01",
                                "frequency_short": "Q",
                                "units_short": "Bil. 2017$",
                                "seasonal_adjustment_short": "SAAR",
                                "last_updated": "2026-01-22 07:46:36-06",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            spec_path.write_text(
                "\n".join(
                    [
                        "version: 1",
                        "series:",
                        "  gdpc1_real_gdp:",
                        "    source: fred",
                        "    series_id: GDPC1",
                        "  dji_level:",
                        "    source: stooq",
                        "    symbol: '^dji'",
                        "metrics:",
                        "  - id: gdp_primary",
                        "    family: gdp_growth",
                        "    primary: true",
                        "    label: GDP Primary",
                        "    inputs:",
                        "      series: gdpc1_real_gdp",
                        "  - id: stock_non_fred",
                        "    family: stock_levels",
                        "    primary: true",
                        "    label: Stock Non-FRED",
                        "    inputs:",
                        "      series: dji_level",
                        "  - id: table_input_primary",
                        "    family: stock_returns",
                        "    primary: true",
                        "    label: Table Input",
                        "    inputs:",
                        "      table: ff_factors_monthly",
                        "  - id: fred_missing_snapshot",
                        "    family: inflation",
                        "    primary: true",
                        "    label: Missing Snapshot",
                        "    inputs:",
                        "      series: missing_fred_series",
                        "  - id: not_primary",
                        "    family: gdp_growth",
                        "    primary: false",
                        "    label: Not Primary",
                        "    inputs:",
                        "      series: gdpc1_real_gdp",
                    ]
                ),
                encoding="utf-8",
            )

            out_csv = root / "report.csv"
            out_md = root / "report.md"
            write_fred_primary_metric_vintage_report(
                spec_path=spec_path,
                raw_root=raw_root,
                out_csv=out_csv,
                out_md=out_md,
            )

            with out_csv.open("r", encoding="utf-8", newline="") as handle:
                rows = {r["metric_id"]: r for r in csv.DictReader(handle)}

            self.assertEqual(rows["gdp_primary"]["status"], "ok")
            self.assertEqual(rows["gdp_primary"]["series_id"], "GDPC1")
            self.assertEqual(rows["gdp_primary"]["artifact_timestamp_utc_compact"], "20260211T120000Z")
            self.assertEqual(rows["gdp_primary"]["series_realtime_start"], "2026-01-22")

            self.assertEqual(rows["stock_non_fred"]["status"], "non_fred_source")
            self.assertEqual(rows["table_input_primary"]["status"], "non_series_input")
            self.assertEqual(rows["fred_missing_snapshot"]["status"], "missing_spec_series")
            self.assertNotIn("not_primary", rows)

            md = out_md.read_text(encoding="utf-8")
            self.assertIn("FRED Vintage Report (Primary Metrics)", md)
            self.assertIn("gdp_primary", md)


if __name__ == "__main__":
    unittest.main()
