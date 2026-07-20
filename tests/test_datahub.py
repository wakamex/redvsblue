from __future__ import annotations

from pathlib import Path

import pytest

from rb.sources.datahub import ingest_datahub_series


CSV = b"""Date,SP500,Dividend
1956-12-01,46.67,1.0
1957-01-01,45.43,1.0
1957-02-01,43.47,1.0
"""


def test_ingest_datahub_series_filters_and_reuses_cache(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = 0

    def fake_http_get(url: str):
        nonlocal calls
        calls += 1
        assert url == "https://example.test/data.csv"
        return 200, {"Content-Type": "text/csv"}, CSV

    monkeypatch.setattr("rb.sources.datahub.http_get", fake_http_get)
    source_cfg = {"url": "https://example.test/data.csv"}

    ingest_datahub_series(
        source_name="datahub_sp500",
        series_key="modern",
        series_cfg={
            "date_column": "Date",
            "value_column": "SP500",
            "filters": {"start_date": "1957-01-01"},
        },
        source_cfg=source_cfg,
        refresh=True,
    )
    ingest_datahub_series(
        source_name="datahub_sp500",
        series_key="historical",
        series_cfg={
            "date_column": "Date",
            "value_column": "SP500",
            "filters": {"end_date": "1956-12-31"},
        },
        source_cfg=source_cfg,
        refresh=False,
    )

    assert calls == 1
    assert Path("data/derived/datahub/modern.csv").read_text() == (
        "date,value\n1957-01-01,45.43\n1957-02-01,43.47\n"
    )
    assert Path("data/derived/datahub/historical.csv").read_text() == (
        "date,value\n1956-12-01,46.67\n"
    )


def test_ingest_datahub_series_rejects_schema_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "rb.sources.datahub.http_get",
        lambda _url: (200, {}, b"Date,Close\n1957-01-01,45.43\n"),
    )

    with pytest.raises(ValueError, match=r"missing CSV columns: \['SP500'\]"):
        ingest_datahub_series(
            source_name="datahub_sp500",
            series_key="modern",
            series_cfg={"date_column": "Date", "value_column": "SP500"},
            source_cfg={"url": "https://example.test/data.csv"},
            refresh=True,
        )
