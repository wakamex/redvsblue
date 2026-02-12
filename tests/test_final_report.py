from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from rb.final_report import write_final_product_report


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


class FinalReportTests(unittest.TestCase):
    def test_final_report_includes_bottom_line_and_congress_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            claims = root / "claims.csv"
            inference = root / "inference.csv"
            congress = root / "congress.csv"
            vintage = root / "vintage.csv"
            out_md = root / "final.md"

            _write_csv(
                inference,
                ["metric_id", "metric_family", "metric_label"],
                [
                    {"metric_id": "gdp_primary", "metric_family": "gdp_growth", "metric_label": "GDP"},
                    {"metric_id": "infl_primary", "metric_family": "inflation", "metric_label": "Inflation"},
                ],
            )

            _write_csv(
                claims,
                [
                    "analysis",
                    "metric_id",
                    "metric_label",
                    "metric_family",
                    "pres_party",
                    "effect_baseline",
                    "effect_strict",
                    "q_baseline",
                    "q_strict",
                    "n_baseline",
                    "n_strict",
                    "tier_baseline",
                    "tier_strict",
                    "tier_baseline_publication",
                    "tier_strict_publication",
                ],
                [
                    {
                        "analysis": "term_party",
                        "metric_id": "gdp_primary",
                        "metric_label": "GDP",
                        "metric_family": "gdp_growth",
                        "pres_party": "",
                        "effect_baseline": "1.5",
                        "effect_strict": "1.2",
                        "q_baseline": "0.02",
                        "q_strict": "0.03",
                        "n_baseline": "20",
                        "n_strict": "20",
                        "tier_baseline": "confirmatory",
                        "tier_strict": "confirmatory",
                        "tier_baseline_publication": "confirmatory",
                        "tier_strict_publication": "confirmatory",
                    },
                    {
                        "analysis": "term_party",
                        "metric_id": "infl_primary",
                        "metric_label": "Inflation",
                        "metric_family": "inflation",
                        "pres_party": "",
                        "effect_baseline": "-0.8",
                        "effect_strict": "-0.6",
                        "q_baseline": "0.20",
                        "q_strict": "0.22",
                        "n_baseline": "20",
                        "n_strict": "20",
                        "tier_baseline": "exploratory",
                        "tier_strict": "exploratory",
                        "tier_baseline_publication": "exploratory",
                        "tier_strict_publication": "exploratory",
                    },
                    {
                        "analysis": "within_unified",
                        "metric_id": "gdp_primary",
                        "metric_label": "GDP",
                        "metric_family": "gdp_growth",
                        "pres_party": "D",
                        "effect_baseline": "0.5",
                        "effect_strict": "0.5",
                        "q_baseline": "0.6",
                        "q_strict": "0.7",
                        "n_baseline": "5",
                        "n_strict": "5",
                        "tier_baseline": "exploratory",
                        "tier_strict": "exploratory",
                        "tier_baseline_publication": "exploratory",
                        "tier_strict_publication": "exploratory",
                    },
                    {
                        "analysis": "congress_unified_binary",
                        "metric_id": "gdp_primary",
                        "metric_label": "GDP",
                        "metric_family": "gdp_growth",
                        "pres_party": "all",
                        "effect_baseline": "0.3",
                        "effect_strict": "0.3",
                        "q_baseline": "0.4",
                        "q_strict": "0.4",
                        "n_baseline": "12",
                        "n_strict": "12",
                        "tier_baseline": "exploratory",
                        "tier_strict": "exploratory",
                        "tier_baseline_publication": "exploratory",
                        "tier_strict_publication": "exploratory",
                    },
                ],
            )

            _write_csv(
                congress,
                [
                    "metric_id",
                    "metric_label",
                    "metric_primary",
                    "pres_party",
                    "observed_diff_unified_minus_divided",
                    "q_bh_fdr",
                    "p_two_sided",
                    "small_cell_warning",
                    "evidence_tier",
                ],
                [
                    {
                        "metric_id": "gdp_primary",
                        "metric_label": "GDP",
                        "metric_primary": "1",
                        "pres_party": "all",
                        "observed_diff_unified_minus_divided": "0.3",
                        "q_bh_fdr": "0.4",
                        "p_two_sided": "0.1",
                        "small_cell_warning": "0",
                        "evidence_tier": "exploratory",
                    }
                ],
            )

            _write_csv(
                vintage,
                [
                    "metric_id",
                    "status",
                    "observation_end",
                    "artifact_timestamp_utc_compact",
                    "top_realtime_end",
                ],
                [
                    {
                        "metric_id": "gdp_primary",
                        "status": "ok",
                        "observation_end": "2025-07-01",
                        "artifact_timestamp_utc_compact": "20260212T000000Z",
                        "top_realtime_end": "2026-01-22",
                    }
                ],
            )

            write_final_product_report(
                claims_table_csv=claims,
                inference_table_csv=inference,
                congress_binary_csv=congress,
                vintage_csv=vintage,
                out_md=out_md,
            )

            md = out_md.read_text(encoding="utf-8")
            self.assertIn("# Final Product Summary", md)
            self.assertIn("## Bottom Line", md)
            self.assertIn("Primary term-level metrics: `2`", md)
            self.assertIn("## Congress Control Diagnostic (Unified vs Divided)", md)
            self.assertIn("| gdp_growth | GDP | 1.200 | D > R | 0.0300 | confirmatory | 20 |", md)


if __name__ == "__main__":
    unittest.main()
