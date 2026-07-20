from pathlib import Path


def test_homepage_metric_count_comes_from_loaded_data():
    html = Path("site/index.html").read_text(encoding="utf-8")

    assert 'id="metric-count"' in html
    assert "metricCount.textContent = String(metricsData.length)" in html
    assert "across 83 U.S. economic metrics" not in html
    assert html.index('load("./data.json")') < html.index("load(CDN)")
