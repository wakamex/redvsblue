from __future__ import annotations

from pathlib import Path

from rb.spec import load_spec
from rb.sources.fred import ingest_fred_series
from rb.sources.ken_french import ingest_ken_french_dataset
from rb.sources.nber import ingest_nber_cycles
from rb.sources.stooq import ingest_stooq_series


def ingest_from_spec(
    *,
    spec_path: Path,
    refresh: bool,
    only_sources: set[str] | None,
    only_series: set[str] | None,
) -> None:
    spec = load_spec(spec_path)

    sources_cfg: dict[str, dict] = spec.get("sources", {})
    series_cfg: dict[str, dict] = spec.get("series", {})

    data_raw_root = Path("data/raw")
    data_derived_root = Path("data/derived")
    data_raw_root.mkdir(parents=True, exist_ok=True)
    data_derived_root.mkdir(parents=True, exist_ok=True)

    # One-off datasets (not keyed by a single series_id).
    if (not only_sources) or ("nber" in only_sources):
        # Fetch once if the spec references the NBER source.
        if "nber" in sources_cfg:
            ingest_nber_cycles(sources_cfg["nber"], refresh=refresh)

    if (not only_sources) or ("ken_french_ff_factors" in only_sources):
        if "ken_french_ff_factors" in sources_cfg:
            # Fetch once if any series uses this source.
            if any(s.get("source") == "ken_french_ff_factors" for s in series_cfg.values()):
                ingest_ken_french_dataset(
                    sources_cfg["ken_french_ff_factors"],
                    dataset_key="ff_factors_monthly",
                    refresh=refresh,
                )

    # Per-series ingestion.
    for series_key, cfg in sorted(series_cfg.items()):
        if only_series and series_key not in only_series:
            continue

        src_name = cfg.get("source")
        if not src_name:
            continue
        if only_sources and src_name not in only_sources:
            continue

        src_cfg = sources_cfg.get(src_name, {})
        kind = src_cfg.get("kind")

        if kind == "fred":
            ingest_fred_series(series_key=series_key, series_cfg=cfg, fred_cfg=src_cfg, refresh=refresh)
        elif src_name == "stooq":
            ingest_stooq_series(series_key=series_key, series_cfg=cfg, stooq_cfg=src_cfg, refresh=refresh)
        elif src_name in {"nber", "ken_french_ff_factors"}:
            # Handled above as one-off datasets.
            continue
        else:
            raise ValueError(f"Unsupported source for series {series_key}: source={src_name!r} kind={kind!r}")

