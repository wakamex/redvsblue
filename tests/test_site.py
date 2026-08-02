import csv
import json
from pathlib import Path

from rb.site import _load_metric_sources, write_site_json


def test_homepage_metric_count_comes_from_loaded_data():
    html = Path("site/index.html").read_text(encoding="utf-8")

    assert 'id="metric-count"' in html
    assert "metricCount.textContent = String(metricsData.length)" in html
    assert "across 83 U.S. economic metrics" not in html
    assert html.index('load("./data.json")') < html.index("load(CDN)")


def test_homepage_explains_and_displays_p_and_q_values():
    html = Path("site/index.html").read_text(encoding="utf-8")

    summary_start = html.index('<div class="summary">')
    summary = html[summary_start:html.index("</div>", summary_start)]
    header_start = html.index("<thead>")
    header = html[header_start:html.index("</thead>", header_start)]

    assert "info-button" not in summary
    assert 'aria-label="About p values"' in header
    assert 'aria-label="About q values"' in header
    assert 'id="p-tip" role="tooltip"' in header
    assert 'id="q-tip" role="tooltip"' in header
    assert "the metric was chosen in advance" in html
    assert "Use it when scanning, comparing, or selecting metrics" in html
    assert 'fmt(m.p, 3)' in html
    assert 'fmt(m.q, 3)' in html


def test_homepage_displays_linked_source_with_accessible_details():
    html = Path("site/index.html").read_text(encoding="utf-8")

    assert 'data-col="source" data-label="Source"' in html
    assert "renderSource(m.source, i)" in html
    assert 'class="source-link"' in html
    assert 'role="tooltip"' in html
    assert 'target="_blank" rel="noopener noreferrer"' in html
    assert 'event.target.closest("a,button")' in html


def test_homepage_fits_ranked_columns_without_display_breakpoints():
    html = Path("site/index.html").read_text(encoding="utf-8")

    assert 'data-col="metric" data-label="Metric" data-required' in html
    assert 'data-col="diff" data-label="D-R" data-priority="1"' in html
    assert 'data-col="q" data-label="q" data-priority="2"' in html
    assert 'data-col="agg" data-label="Agg" data-priority="12"' in html
    assert 'data-col="units" data-label="Units" data-priority="11"' in html
    assert 'data-col="family" data-label="Family" data-priority="10"' in html
    assert "function fitColumns()" in html
    assert "table.scrollWidth > tableWrap.clientWidth + 1" in html
    assert "new ResizeObserver(scheduleFitColumns).observe(tableWrap)" in html
    assert "buildHiddenDetails(metricRow)" in html
    assert 'class="hidden-field"' in html
    assert 'data-col="details" data-label="More" data-control hidden' in html
    assert 'class="details-button"' in html
    assert '"Show " + hiddenColumnCount + " hidden columns for "' in html
    assert 'row.querySelector(".details-button").addEventListener("click"' in html
    assert "min-width:1100px" not in html


def test_registry_provides_source_provenance_for_every_metric():
    sources = _load_metric_sources(Path("spec/metrics_v1.yaml"))

    assert len(sources) == 88
    assert sources["payroll_jobs_change_total"]["label"] == "BLS CES · PAYEMS"
    assert sources["manufacturing_jobs_change_total"]["label"] == "BLS CES · MANEMP"
    assert sources["household_employment_change_total"]["label"] == "BLS CPS · CE16OV"


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

    spec = tmp_path / "metrics.yaml"
    spec.write_text(
        """
sources:
  example_api:
    provenance:
      access_provider: Example API
      url: https://example.test/series/{series_id}
series:
  example_series:
    source: example_api
    series_id: EXAMPLE1
    frequency: M
    units: source units
    provenance:
      label: Example Bureau · EXAMPLE1
      publisher: Example Bureau
      program: Example Survey
      source_id: ORIGINAL1
metrics:
  - id: example
    inputs:
      series: example_series
""".lstrip(),
        encoding="utf-8",
    )

    output_dir = tmp_path / "site"
    write_site_json(
        party_summary_csv=party_summary,
        term_randomization_csv=randomization,
        term_metrics_csv=None,
        spec_path=spec,
        output_dir=output_dir,
    )

    metric = json.loads((output_dir / "data.json").read_text(encoding="utf-8"))["metrics"][0]
    assert metric["p"] == 0.012346
    assert metric["q"] == 0.045679
    assert metric["source"] == {
        "label": "Example Bureau · EXAMPLE1",
        "publisher": "Example Bureau",
        "program": "Example Survey",
        "access_provider": "Example API",
        "access_id": "EXAMPLE1",
        "url": "https://example.test/series/EXAMPLE1",
        "frequency": "Monthly",
        "units": "source units",
        "source_id": "ORIGINAL1",
    }
