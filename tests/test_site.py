import csv
import json
from pathlib import Path

from rb.site import write_site_json


def test_homepage_metric_count_comes_from_loaded_data():
    html = Path("site/index.html").read_text(encoding="utf-8")

    assert 'id="metric-count"' in html
    assert "metricCount.textContent = String(metricsData.length)" in html
    assert "across 83 U.S. economic metrics" not in html
    assert html.index('load("./data.json")') < html.index("load(CDN)")


def test_homepage_explains_and_displays_p_and_q_values():
    html = Path("site/index.html").read_text(encoding="utf-8")

    assert "How to use p and q values" in html
    assert "the metric was chosen in advance" in html
    assert "Use it when scanning, comparing, or selecting metrics" in html
    assert 'fmt(m.p, 3)' in html
    assert 'fmt(m.q, 3)' in html
    assert "var COL_SPAN = 12" in html


def test_site_json_exports_raw_p_and_adjusted_q_values(tmp_path):
    party_summary = tmp_path / "party.csv"
    with party_summary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "party_abbrev", "metric_id", "metric_family", "metric_label",
                "agg_kind", "units", "n_terms", "mean", "median",
            ],
        )
        writer.writeheader()
        writer.writerows([
            {
                "party_abbrev": "D", "metric_id": "example", "metric_family": "test",
                "metric_label": "Example metric", "agg_kind": "mean", "units": "units",
                "n_terms": "2", "mean": "3", "median": "3",
            },
            {
                "party_abbrev": "R", "metric_id": "example", "metric_family": "test",
                "metric_label": "Example metric", "agg_kind": "mean", "units": "units",
                "n_terms": "2", "mean": "1", "median": "1",
            },
        ])

    randomization = tmp_path / "randomization.csv"
    with randomization.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "metric_id", "p_two_sided", "q_bh_fdr",
                "bootstrap_ci95_low", "bootstrap_ci95_high",
            ],
        )
        writer.writeheader()
        writer.writerow({
            "metric_id": "example", "p_two_sided": "0.0123456", "q_bh_fdr": "0.0456789",
            "bootstrap_ci95_low": "0.5", "bootstrap_ci95_high": "3.5",
        })

    output_dir = tmp_path / "site"
    write_site_json(
        party_summary_csv=party_summary,
        term_randomization_csv=randomization,
        term_metrics_csv=None,
        output_dir=output_dir,
    )

    metric = json.loads((output_dir / "data.json").read_text(encoding="utf-8"))["metrics"][0]
    assert metric["p"] == 0.012346
    assert metric["q"] == 0.045679
