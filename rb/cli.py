from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from rb.env import load_dotenv
from rb.congress_control import ensure_congress_control
from rb.ingest import ingest_from_spec
from rb.inference import write_inference_table, write_wild_cluster_stability_summary, write_wild_cluster_stability_table
from rb.metrics import compute_term_metrics
from rb.narrative import write_publication_narrative_template
from rb.presidents import ensure_presidents
from rb.randomization import (
    compare_randomization_outputs,
    ensure_within_mde_columns,
    run_randomization,
    run_randomization_seed_stability,
    write_cpi_sa_nsa_level_robustness,
    write_claims_table,
    write_inversion_definition_robustness,
)
from rb.regimes import ensure_regime_pipeline
from rb.scoreboard import write_scoreboard_md
from rb.validate import validate_all

PRESIDENT_SOURCES = ("congress_legislators", "wikidata")
PRESIDENT_GRANULARITY = ("tenure", "term")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _file_meta(path: Path | None) -> dict[str, object]:
    if path is None:
        return {"path": "", "exists": False}
    if not path.exists():
        return {"path": str(path), "exists": False}
    st = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": int(st.st_size),
        "sha256": _sha256_file(path),
    }


def _write_json_atomic(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _parse_int_list_csv(spec: str, *, arg_name: str) -> list[int]:
    parts = [s.strip() for s in str(spec).split(",")] if str(spec).strip() else []
    out: list[int] = []
    for p in parts:
        if not p:
            continue
        try:
            out.append(int(p))
        except ValueError as exc:
            raise ValueError(f"Invalid integer {p!r} in {arg_name}={spec!r}") from exc
    return out


def _git_head(cwd: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd),
            stderr=subprocess.DEVNULL,
        )
        return out.decode("utf-8").strip()
    except Exception:
        return ""


_ARTIFACT_TS_RE = re.compile(r"^(\d{8}T\d{6}Z)__sha256_")


def _artifact_ts_from_name(name: str) -> str:
    m = _ARTIFACT_TS_RE.match(name)
    if not m:
        return ""
    return m.group(1)


def _latest_raw_source_artifacts(raw_root: Path = Path("data/raw")) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    if not raw_root.exists():
        return out
    for source_dir in sorted(p for p in raw_root.iterdir() if p.is_dir()):
        latest_path: Path | None = None
        latest_ts = ""
        for p in source_dir.rglob("*"):
            if not p.is_file():
                continue
            if p.name.endswith(".meta.json"):
                continue
            ts = _artifact_ts_from_name(p.name)
            if not ts:
                continue
            if latest_path is None or ts > latest_ts:
                latest_path = p
                latest_ts = ts
        if latest_path is None:
            out[source_dir.name] = {"exists": False}
            continue
        out[source_dir.name] = {
            "exists": True,
            "artifact_timestamp_utc_compact": latest_ts,
            "artifact_path": str(latest_path),
            "artifact_sha256_from_name": (
                latest_path.name.split("__sha256_")[-1].split(".")[0] if "__sha256_" in latest_path.name else ""
            ),
        }
    return out


def _fred_vintage_summary(raw_root: Path = Path("data/raw")) -> dict[str, object]:
    root = raw_root / "fred" / "series"
    if not root.exists() or not root.is_dir():
        return {"exists": False}

    starts: list[str] = []
    ends: list[str] = []
    latest_updates: list[str] = []
    n_series = 0
    for series_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        candidates = sorted(
            p for p in series_dir.glob("*.json") if not p.name.endswith(".meta.json")
        )
        if not candidates:
            continue
        latest = candidates[-1]
        try:
            obj = json.loads(latest.read_text(encoding="utf-8"))
        except Exception:
            continue
        n_series += 1
        rs = str(obj.get("realtime_start") or "").strip()
        re_ = str(obj.get("realtime_end") or "").strip()
        if rs:
            starts.append(rs)
        if re_:
            ends.append(re_)
        seriess = obj.get("seriess") or []
        if isinstance(seriess, list) and seriess:
            lu = str((seriess[0] or {}).get("last_updated") or "").strip()
            if lu:
                latest_updates.append(lu)

    return {
        "exists": True,
        "n_series_dirs_with_snapshots": n_series,
        "realtime_start_min": min(starts) if starts else "",
        "realtime_start_max": max(starts) if starts else "",
        "realtime_end_min": min(ends) if ends else "",
        "realtime_end_max": max(ends) if ends else "",
        "last_updated_min": min(latest_updates) if latest_updates else "",
        "last_updated_max": max(latest_updates) if latest_updates else "",
    }


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="rb", description="Reproducible D-vs-R performance pipeline tooling.")
    sub = p.add_subparsers(dest="cmd", required=True)

    ingest = sub.add_parser("ingest", help="Fetch and cache raw data + write normalized derived tables.")
    ingest.add_argument("--spec", type=Path, default=Path("spec/metrics_v1.yaml"), help="Metric registry spec YAML.")
    ingest.add_argument("--refresh", action="store_true", help="Re-download and write a new raw artifact version.")
    ingest.add_argument(
        "--sources",
        action="append",
        default=[],
        help="Restrict ingestion to these spec source names (repeatable), e.g. --sources fred --sources stooq.",
    )
    ingest.add_argument(
        "--series",
        action="append",
        default=[],
        help="Restrict ingestion to these series keys from the spec (repeatable).",
    )
    ingest.add_argument("--dotenv", type=Path, default=Path(".env"), help="Optional .env file to load into env vars.")

    presidents = sub.add_parser("presidents", help="Fetch and cache presidential terms + party labels.")
    presidents.add_argument("--refresh", action="store_true", help="Re-download and write a new raw artifact version.")
    presidents.add_argument(
        "--source",
        choices=PRESIDENT_SOURCES,
        default="congress_legislators",
        help="Source of presidential terms/party labels.",
    )
    presidents.add_argument(
        "--output",
        type=Path,
        default=Path("data/derived/presidents.csv"),
        help="Output CSV for presidential windows.",
    )
    presidents.add_argument(
        "--granularity",
        choices=PRESIDENT_GRANULARITY,
        default="tenure",
        help="Emit per-president tenure windows (tenure) or constitutional terms (term).",
    )
    presidents.add_argument("--dotenv", type=Path, default=Path(".env"), help="Optional .env file to load into env vars.")

    congress = sub.add_parser("congress", help="Fetch and derive House/Senate party control by Congress session.")
    congress.add_argument("--refresh", action="store_true", help="Re-download and write a new raw artifact version.")
    congress.add_argument(
        "--output",
        type=Path,
        default=Path("data/derived/congress_control/congress_control.csv"),
        help="Output CSV for Congress party control.",
    )
    congress.add_argument("--dotenv", type=Path, default=Path(".env"), help="Optional .env file to load into env vars.")

    regimes = sub.add_parser("regimes", help="Compute metric tables over (President x Congress) regime windows.")
    regimes.add_argument("--refresh", action="store_true", help="Re-download upstream artifacts when possible.")
    regimes.add_argument("--spec", type=Path, default=Path("spec/metrics_v1.yaml"), help="Metric registry spec YAML.")
    regimes.add_argument("--attribution", type=Path, default=Path("spec/attribution_v1.yaml"), help="Attribution spec YAML.")
    regimes.add_argument("--presidents", type=Path, default=Path("data/derived/presidents.csv"), help="Presidents windows CSV.")
    regimes.add_argument(
        "--president-source",
        choices=PRESIDENT_SOURCES,
        default="congress_legislators",
        help="If --presidents does not exist, generate it from this source.",
    )
    regimes.add_argument(
        "--president-granularity",
        choices=PRESIDENT_GRANULARITY,
        default="tenure",
        help="If generating --presidents, choose tenure vs term windows.",
    )
    regimes.add_argument(
        "--congress-control",
        type=Path,
        default=Path("data/derived/congress_control/congress_control.csv"),
        help="Congress control CSV (generated by `rb congress`).",
    )
    regimes.add_argument(
        "--output-windows-labels",
        type=Path,
        default=Path("data/derived/regimes/regime_windows_labels.csv"),
        help="Output CSV describing regime windows.",
    )
    regimes.add_argument(
        "--output-windows-presidents",
        type=Path,
        default=Path("data/derived/regimes/regime_windows_presidents.csv"),
        help="Presidents.csv-shaped windows CSV used for metric computation.",
    )
    regimes.add_argument(
        "--output-window-metrics",
        type=Path,
        default=Path("reports/regime_window_metrics_v1.csv"),
        help="Output CSV of metrics per regime window.",
    )
    regimes.add_argument(
        "--output-regime-summary",
        type=Path,
        default=Path("reports/regime_summary_v1.csv"),
        help="Output CSV of regime summaries grouped by (P,H,S).",
    )
    regimes.add_argument(
        "--output-alignment-summary",
        type=Path,
        default=Path("reports/regime_alignment_summary_v1.csv"),
        help="Output CSV of regime summaries grouped by president alignment with House/Senate.",
    )
    regimes.add_argument(
        "--output-party-summary",
        type=Path,
        default=Path("reports/regime_party_summary_v1.csv"),
        help="Output CSV of party summaries over regime windows (president party only).",
    )
    regimes.add_argument("--dotenv", type=Path, default=Path(".env"), help="Optional .env file to load into env vars.")

    compute = sub.add_parser("compute", help="Compute term-level metric table + party summaries.")
    compute.add_argument("--spec", type=Path, default=Path("spec/metrics_v1.yaml"), help="Metric registry spec YAML.")
    compute.add_argument("--attribution", type=Path, default=Path("spec/attribution_v1.yaml"), help="Attribution spec YAML.")
    compute.add_argument(
        "--president-source",
        choices=PRESIDENT_SOURCES,
        default="congress_legislators",
        help="If --presidents does not exist, generate it from this source.",
    )
    compute.add_argument(
        "--president-granularity",
        choices=PRESIDENT_GRANULARITY,
        default="tenure",
        help="If generating --presidents, choose tenure vs term windows.",
    )
    compute.add_argument(
        "--presidents",
        type=Path,
        default=Path("data/derived/presidents.csv"),
        help="Presidents terms CSV (generated by `rb presidents`).",
    )
    compute.add_argument("--output-terms", type=Path, default=Path("reports/term_metrics_v1.csv"), help="Output CSV (term-level).")
    compute.add_argument("--output-party", type=Path, default=Path("reports/party_summary_v1.csv"), help="Output CSV (party-level).")
    compute.add_argument("--dotenv", type=Path, default=Path(".env"), help="Optional .env file to load into env vars.")

    validate = sub.add_parser("validate", help="Run basic validation checks on derived data + reports.")
    validate.add_argument("--presidents", type=Path, default=Path("data/derived/presidents.csv"), help="Presidents windows CSV.")
    validate.add_argument(
        "--congress-control",
        type=Path,
        default=Path("data/derived/congress_control/congress_control.csv"),
        help="Congress control CSV (optional; validated if present).",
    )
    validate.add_argument("--term-metrics", type=Path, default=Path("reports/term_metrics_v1.csv"), help="Term metrics CSV (optional; validated if present).")
    validate.add_argument("--party-summary", type=Path, default=Path("reports/party_summary_v1.csv"), help="Party summary CSV (optional; validated if present).")
    validate.add_argument("--spec", type=Path, default=Path("spec/metrics_v1.yaml"), help="Metric registry spec YAML for symmetry checks.")
    validate.add_argument("--dotenv", type=Path, default=Path(".env"), help="Optional .env file to load into env vars.")

    scoreboard = sub.add_parser("scoreboard", help="Render a simple markdown scoreboard from computed CSVs.")
    scoreboard.add_argument("--spec", type=Path, default=Path("spec/metrics_v1.yaml"), help="Metric registry spec YAML.")
    scoreboard.add_argument("--party-summary", type=Path, default=Path("reports/party_summary_v1.csv"), help="Party summary CSV.")
    scoreboard.add_argument(
        "--output",
        type=Path,
        default=Path("reports/scoreboard.md"),
        help="Output markdown path.",
    )
    scoreboard.add_argument(
        "--all-metrics",
        action="store_true",
        help="Include non-primary metrics in addition to primary metrics.",
    )
    scoreboard.add_argument(
        "--window-metrics",
        type=Path,
        default=Path("reports/regime_window_metrics_v1.csv"),
        help="Regime-window metrics CSV (optional; adds unified-vs-divided section if present).",
    )
    scoreboard.add_argument(
        "--window-labels",
        type=Path,
        default=Path("data/derived/regimes/regime_windows_labels.csv"),
        help="Regime-window labels CSV (optional; adds unified-vs-divided section if present).",
    )
    scoreboard.add_argument(
        "--output-within-president-deltas",
        type=Path,
        default=Path("reports/within_president_unified_delta_v1.csv"),
        help="Output CSV for within-president unified-minus-divided diagnostic.",
    )
    scoreboard.add_argument(
        "--within-president-min-window-days",
        type=int,
        default=0,
        help="Minimum window_days required for rows used in within-president unified-vs-divided diagnostics.",
    )
    scoreboard.add_argument(
        "--no-robustness-links",
        action="store_true",
        help="Hide the optional robustness-artifact links section from the markdown output.",
    )
    scoreboard.add_argument(
        "--claims-table",
        type=Path,
        default=Path("reports/claims_table_v1.csv"),
        help="Claims table CSV (optional; adds strict/publication tier columns if present).",
    )
    scoreboard.add_argument(
        "--inference-stability-summary",
        type=Path,
        default=Path("reports/inference_wild_cluster_stability_summary_v1.csv"),
        help="Inference stability summary CSV (optional; adds stability status columns if present).",
    )
    scoreboard.add_argument(
        "--no-publication-tier-columns",
        action="store_true",
        help="Hide strict/publication tier columns in the party summary table.",
    )
    scoreboard.add_argument("--dotenv", type=Path, default=Path(".env"), help="Optional .env file to load into env vars.")

    randomization = sub.add_parser("randomization", help="Run permutation/randomization robustness checks.")
    randomization.add_argument("--term-metrics", type=Path, default=Path("reports/term_metrics_v1.csv"), help="Term metrics CSV.")
    randomization.add_argument(
        "--output-party-term",
        type=Path,
        default=Path("reports/permutation_party_term_v1.csv"),
        help="Output CSV for term-level D-vs-R permutation test.",
    )
    randomization.add_argument(
        "--window-metrics",
        type=Path,
        default=Path("reports/regime_window_metrics_v1.csv"),
        help="Regime-window metrics CSV (optional for unified-within-term test).",
    )
    randomization.add_argument(
        "--window-labels",
        type=Path,
        default=Path("data/derived/regimes/regime_windows_labels.csv"),
        help="Regime-window labels CSV (optional for unified-within-term test).",
    )
    randomization.add_argument(
        "--output-unified-within-term",
        type=Path,
        default=Path("reports/permutation_unified_within_term_v1.csv"),
        help="Output CSV for within-president unified-vs-divided permutation test.",
    )
    randomization.add_argument(
        "--output-evidence-summary",
        type=Path,
        default=Path("reports/permutation_evidence_summary_v1.csv"),
        help="Output CSV summary of evidence tiers by analysis and metric family.",
    )
    randomization.add_argument(
        "--output-evidence-md",
        type=Path,
        default=Path("reports/permutation_evidence_summary_v1.md"),
        help="Output markdown summary of confirmatory/supportive evidence rows.",
    )
    randomization.add_argument(
        "--output-inversion-robustness-csv",
        type=Path,
        default=Path("reports/inversion_definition_robustness_v1.csv"),
        help="Output CSV for T10Y2Y inversion-definition comparison (generated only with --all-metrics).",
    )
    randomization.add_argument(
        "--output-inversion-robustness-md",
        type=Path,
        default=Path("reports/inversion_definition_robustness_v1.md"),
        help="Output markdown for T10Y2Y inversion-definition comparison (generated only with --all-metrics).",
    )
    randomization.add_argument(
        "--skip-inversion-robustness",
        action="store_true",
        help="Do not generate inversion-definition robustness outputs.",
    )
    randomization.add_argument(
        "--output-cpi-robustness-csv",
        type=Path,
        default=Path("reports/cpi_sa_nsa_robustness_v1.csv"),
        help="Output CSV for CPI SA-vs-NSA paired-metric comparison (generated only with --all-metrics).",
    )
    randomization.add_argument(
        "--output-cpi-robustness-md",
        type=Path,
        default=Path("reports/cpi_sa_nsa_robustness_v1.md"),
        help="Output markdown for CPI SA-vs-NSA paired-metric comparison (generated only with --all-metrics).",
    )
    randomization.add_argument(
        "--skip-cpi-robustness",
        action="store_true",
        help="Do not generate CPI SA-vs-NSA robustness outputs.",
    )
    randomization.add_argument("--permutations", type=int, default=10000, help="Number of random permutations.")
    randomization.add_argument("--bootstrap-samples", type=int, default=2000, help="Number of bootstrap samples for CI estimates.")
    randomization.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility.")
    randomization.add_argument(
        "--q-threshold",
        type=float,
        default=0.05,
        help="Confirmatory FDR q-value threshold (default 0.05); supportive tier uses q<0.10.",
    )
    randomization.add_argument(
        "--min-term-n-obs",
        type=int,
        default=12,
        help="Minimum n_obs for term-level rows to pass minimum sample-size check.",
    )
    randomization.add_argument(
        "--min-within-n-both",
        type=int,
        default=5,
        help="Minimum n_presidents_with_both for within-president rows to pass minimum sample-size check.",
    )
    randomization.add_argument(
        "--term-block-years",
        type=int,
        default=20,
        help="If >0, term-party permutation shuffles labels within term-start-year blocks of this size.",
    )
    randomization.add_argument(
        "--within-president-min-window-days",
        type=int,
        default=0,
        help="Minimum window_days to include in within-president unified-vs-divided permutation test.",
    )
    randomization.add_argument(
        "--all-metrics",
        action="store_true",
        help="Include non-primary metrics (default behavior is primary-only).",
    )
    randomization.add_argument(
        "--include-diagnostic-metrics",
        action="store_true",
        help="Include diagnostic-only metrics in randomization outputs (default excludes selected non-headline diagnostics).",
    )
    randomization.add_argument("--dotenv", type=Path, default=Path(".env"), help="Optional .env file to load into env vars.")

    stability = sub.add_parser("randomization-stability", help="Run multi-seed stability checks for term-party randomization outputs.")
    stability.add_argument("--term-metrics", type=Path, default=Path("reports/term_metrics_v1.csv"), help="Term metrics CSV.")
    stability.add_argument(
        "--output",
        type=Path,
        default=Path("reports/permutation_seed_stability_v1.csv"),
        help="Output CSV with q/tier stability ranges across seeds.",
    )
    stability.add_argument(
        "--seeds",
        type=str,
        default="42,137,271",
        help="Comma-separated RNG seeds (e.g., 42,137,271).",
    )
    stability.add_argument("--permutations", type=int, default=10000, help="Number of random permutations per seed.")
    stability.add_argument("--bootstrap-samples", type=int, default=2000, help="Number of bootstrap samples per seed.")
    stability.add_argument(
        "--q-threshold",
        type=float,
        default=0.05,
        help="Confirmatory FDR q-value threshold for tiering.",
    )
    stability.add_argument(
        "--min-term-n-obs",
        type=int,
        default=12,
        help="Minimum n_obs for term-level rows to pass minimum sample-size check.",
    )
    stability.add_argument(
        "--term-block-years",
        type=int,
        default=20,
        help="If >0, term-party permutation shuffles labels within term-start-year blocks of this size.",
    )
    stability.add_argument(
        "--all-metrics",
        action="store_true",
        help="Include non-primary metrics (default behavior is primary-only).",
    )
    stability.add_argument(
        "--include-diagnostic-metrics",
        action="store_true",
        help="Include diagnostic-only metrics in stability runs (default excludes selected non-headline diagnostics).",
    )
    stability.add_argument("--dotenv", type=Path, default=Path(".env"), help="Optional .env file to load into env vars.")

    inference = sub.add_parser("inference-table", help="Build primary-metric side-by-side inference table (Permutation + HAC/Newey-West).")
    inference.add_argument("--term-metrics", type=Path, default=Path("reports/term_metrics_v1.csv"), help="Term metrics CSV.")
    inference.add_argument(
        "--permutation-party-term",
        type=Path,
        default=Path("reports/permutation_party_term_v1.csv"),
        help="Term-party permutation CSV (provides permutation p/q/tier columns).",
    )
    inference.add_argument(
        "--output-csv",
        type=Path,
        default=Path("reports/inference_table_primary_v1.csv"),
        help="Output CSV path.",
    )
    inference.add_argument(
        "--output-md",
        type=Path,
        default=Path("reports/inference_table_primary_v1.md"),
        help="Output markdown summary path.",
    )
    inference.add_argument(
        "--nw-lags",
        type=int,
        default=1,
        help="Newey-West lag length for HAC standard errors.",
    )
    inference.add_argument(
        "--wild-cluster-draws",
        type=int,
        default=1999,
        help="Rademacher wild-cluster bootstrap draws for president-cluster p-values (0 disables).",
    )
    inference.add_argument(
        "--wild-cluster-seed",
        type=int,
        default=42,
        help="RNG seed for wild-cluster bootstrap reproducibility.",
    )
    inference.add_argument("--dotenv", type=Path, default=Path(".env"), help="Optional .env file to load into env vars.")

    inference_stability = sub.add_parser("inference-stability", help="Run seed-stability diagnostics for wild-cluster p-values on primary metrics.")
    inference_stability.add_argument("--term-metrics", type=Path, default=Path("reports/term_metrics_v1.csv"), help="Term metrics CSV.")
    inference_stability.add_argument(
        "--output",
        type=Path,
        default=Path("reports/inference_wild_cluster_stability_v1.csv"),
        help="Output CSV with wild-cluster p-value ranges across seeds.",
    )
    inference_stability.add_argument(
        "--seeds",
        type=str,
        default="42,137,271",
        help="Comma-separated RNG seeds (e.g., 42,137,271).",
    )
    inference_stability.add_argument(
        "--wild-cluster-draws",
        type=int,
        default=1999,
        help="Rademacher wild-cluster bootstrap draws per seed (0 disables).",
    )
    inference_stability.add_argument(
        "--draws-grid",
        type=str,
        default="",
        help="Optional comma-separated draw counts (e.g., 499,999,1999). When set, runs all values and outputs one row per metric per draw count.",
    )
    inference_stability.add_argument("--dotenv", type=Path, default=Path(".env"), help="Optional .env file to load into env vars.")

    inference_stability_summary = sub.add_parser("inference-stability-summary", help="Build compact instability flags from `rb inference-stability` output.")
    inference_stability_summary.add_argument(
        "--stability-csv",
        type=Path,
        default=Path("reports/inference_wild_cluster_stability_v1.csv"),
        help="Input CSV from `rb inference-stability`.",
    )
    inference_stability_summary.add_argument(
        "--output",
        type=Path,
        default=Path("reports/inference_wild_cluster_stability_summary_v1.csv"),
        help="Output CSV with per-metric robust/non-robust significance status.",
    )
    inference_stability_summary.add_argument("--dotenv", type=Path, default=Path(".env"), help="Optional .env file to load into env vars.")

    compare_rand = sub.add_parser("randomization-compare", help="Compare evidence tiers between two randomization runs.")
    compare_rand.add_argument(
        "--base-party-term",
        type=Path,
        default=Path("reports/permutation_party_term_all_v1.csv"),
        help="Baseline term-level randomization CSV.",
    )
    compare_rand.add_argument(
        "--alt-party-term",
        type=Path,
        required=True,
        help="Alternative term-level randomization CSV to compare against baseline.",
    )
    compare_rand.add_argument(
        "--base-within",
        type=Path,
        default=Path("reports/permutation_unified_within_term_all_v1.csv"),
        help="Baseline within-president randomization CSV (optional).",
    )
    compare_rand.add_argument(
        "--alt-within",
        type=Path,
        default=None,
        help="Alternative within-president randomization CSV (optional).",
    )
    compare_rand.add_argument(
        "--output",
        type=Path,
        default=Path("reports/permutation_evidence_compare_v1.csv"),
        help="Output CSV comparing evidence tiers and q/p values.",
    )
    compare_rand.add_argument("--dotenv", type=Path, default=Path(".env"), help="Optional .env file to load into env vars.")

    claims = sub.add_parser("claims-table", help="Build machine-readable baseline-vs-strict claims table.")
    claims.add_argument(
        "--baseline-party-term",
        type=Path,
        default=Path("reports/permutation_party_term_all_v1.csv"),
        help="Baseline term-level randomization CSV.",
    )
    claims.add_argument(
        "--strict-party-term",
        type=Path,
        default=Path("reports/permutation_party_term_block20_all_v1.csv"),
        help="Strict-profile term-level randomization CSV.",
    )
    claims.add_argument(
        "--baseline-within",
        type=Path,
        default=Path("reports/permutation_unified_within_term_all_v1.csv"),
        help="Baseline within-president randomization CSV (optional).",
    )
    claims.add_argument(
        "--strict-within",
        type=Path,
        default=Path("reports/permutation_unified_within_term_min90_all_v1.csv"),
        help="Strict-profile within-president randomization CSV (optional).",
    )
    claims.add_argument(
        "--output",
        type=Path,
        default=Path("reports/claims_table_v1.csv"),
        help="Output machine-readable claims table CSV.",
    )
    claims.add_argument(
        "--inference-table",
        type=Path,
        default=Path("reports/inference_table_primary_v1.csv"),
        help="Primary-metric inference table CSV (optional; used by publication gating).",
    )
    claims.add_argument(
        "--inference-stability-summary",
        type=Path,
        default=Path("reports/inference_wild_cluster_stability_summary_v1.csv"),
        help="Inference stability summary CSV (optional; used by publication stability gate).",
    )
    claims.add_argument(
        "--publication-mode",
        action="store_true",
        help="Apply publication gating: confirmatory tiers require HAC/sign agreement (term-party rows only).",
    )
    claims.add_argument(
        "--publication-stability-gate",
        action="store_true",
        help="When --publication-mode is set, downgrade unstable rows using inference-stability summary.",
    )
    claims.add_argument(
        "--publication-hac-p-threshold",
        type=float,
        default=0.05,
        help="HAC p-value threshold used by --publication-mode gate.",
    )
    claims.add_argument("--dotenv", type=Path, default=Path(".env"), help="Optional .env file to load into env vars.")

    narrative = sub.add_parser("narrative-template", help="Build a publication-ready narrative template from claims + inference tables.")
    narrative.add_argument(
        "--claims-table",
        type=Path,
        default=Path("reports/claims_table_v1.csv"),
        help="Claims table CSV (ideally generated with --publication-mode).",
    )
    narrative.add_argument(
        "--inference-table",
        type=Path,
        default=Path("reports/inference_table_primary_v1.csv"),
        help="Primary inference table CSV.",
    )
    narrative.add_argument(
        "--inference-stability-summary",
        type=Path,
        default=Path("reports/inference_wild_cluster_stability_summary_v1.csv"),
        help="Inference stability summary CSV (optional).",
    )
    narrative.add_argument(
        "--output",
        type=Path,
        default=Path("reports/publication_narrative_template_v1.md"),
        help="Output markdown path.",
    )
    narrative.add_argument("--dotenv", type=Path, default=Path(".env"), help="Optional .env file to load into env vars.")

    pub = sub.add_parser("publication-bundle", help="Generate publication-facing claims/inference/narrative/scoreboard artifacts in one run.")
    pub.add_argument(
        "--profile",
        choices=("strict_vs_baseline", "baseline_only"),
        default="strict_vs_baseline",
        help=(
            "Preset path policy: strict_vs_baseline uses explicit strict inputs; "
            "baseline_only reuses baseline randomization CSVs for strict slots."
        ),
    )
    pub.add_argument("--spec", type=Path, default=Path("spec/metrics_v1.yaml"), help="Metric registry spec YAML.")
    pub.add_argument("--party-summary", type=Path, default=Path("reports/party_summary_v1.csv"), help="Party summary CSV.")
    pub.add_argument("--term-metrics", type=Path, default=Path("reports/term_metrics_v1.csv"), help="Term metrics CSV.")
    pub.add_argument(
        "--baseline-party-term",
        type=Path,
        default=Path("reports/permutation_party_term_all_v1.csv"),
        help="Baseline term-level randomization CSV.",
    )
    pub.add_argument(
        "--strict-party-term",
        type=Path,
        default=Path("reports/permutation_party_term_block20_all_v1.csv"),
        help="Strict-profile term-level randomization CSV.",
    )
    pub.add_argument(
        "--baseline-within",
        type=Path,
        default=Path("reports/permutation_unified_within_term_all_v1.csv"),
        help="Baseline within-president randomization CSV (optional).",
    )
    pub.add_argument(
        "--strict-within",
        type=Path,
        default=Path("reports/permutation_unified_within_term_min90_all_v1.csv"),
        help="Strict-profile within-president randomization CSV (optional).",
    )
    pub.add_argument(
        "--window-metrics",
        type=Path,
        default=Path("reports/regime_window_metrics_v1.csv"),
        help="Regime-window metrics CSV for scoreboard sections (optional).",
    )
    pub.add_argument(
        "--window-labels",
        type=Path,
        default=Path("data/derived/regimes/regime_windows_labels.csv"),
        help="Regime-window labels CSV for scoreboard sections (optional).",
    )
    pub.add_argument(
        "--all-metrics",
        action="store_true",
        help="Render scoreboard with all metrics (default is primary-only).",
    )
    pub.add_argument(
        "--within-president-min-window-days",
        type=int,
        default=0,
        help="Minimum window_days filter used in scoreboard within-president diagnostics.",
    )
    pub.add_argument(
        "--no-backfill-within-mde",
        action="store_true",
        help="Skip automatic backfill of within-president rough-MDE columns when input CSVs are stale.",
    )
    pub.add_argument("--nw-lags", type=int, default=1, help="Newey-West lag length for inference table.")
    pub.add_argument(
        "--wild-cluster-draws",
        type=int,
        default=1999,
        help="Rademacher wild-cluster bootstrap draws for president-cluster p-values (0 disables).",
    )
    pub.add_argument(
        "--wild-cluster-seed",
        type=int,
        default=42,
        help="RNG seed for wild-cluster bootstrap reproducibility.",
    )
    pub.add_argument(
        "--publication-hac-p-threshold",
        type=float,
        default=0.05,
        help="HAC p-value threshold used by claims publication gating.",
    )
    pub.add_argument(
        "--inference-stability-seeds",
        type=str,
        default="42,137,271",
        help="Comma-separated seeds for publication-bundle wild-cluster stability artifacts.",
    )
    pub.add_argument(
        "--inference-stability-draws-grid",
        type=str,
        default="499,999,1999",
        help="Comma-separated draw counts for publication-bundle wild-cluster stability artifacts.",
    )
    pub.add_argument(
        "--skip-inference-stability",
        action="store_true",
        help="Skip generating inference stability + summary artifacts inside publication-bundle.",
    )
    pub.add_argument(
        "--no-publication-stability-gate",
        action="store_true",
        help="Disable publication-tier downgrade for rows flagged unstable in inference-stability summary.",
    )
    pub.add_argument(
        "--output-inference-csv",
        type=Path,
        default=Path("reports/inference_table_primary_v1.csv"),
        help="Output CSV for dual-inference primary table.",
    )
    pub.add_argument(
        "--output-inference-md",
        type=Path,
        default=Path("reports/inference_table_primary_v1.md"),
        help="Output markdown for dual-inference primary table.",
    )
    pub.add_argument(
        "--output-inference-stability-csv",
        type=Path,
        default=Path("reports/inference_wild_cluster_stability_v1.csv"),
        help="Output CSV for wild-cluster seed/draw stability diagnostics.",
    )
    pub.add_argument(
        "--output-inference-stability-summary-csv",
        type=Path,
        default=Path("reports/inference_wild_cluster_stability_summary_v1.csv"),
        help="Output CSV for compact wild-cluster stability status summary.",
    )
    pub.add_argument(
        "--output-claims",
        type=Path,
        default=Path("reports/claims_table_v1.csv"),
        help="Output CSV for publication-gated claims table.",
    )
    pub.add_argument(
        "--output-narrative",
        type=Path,
        default=Path("reports/publication_narrative_template_v1.md"),
        help="Output markdown path for publication narrative template.",
    )
    pub.add_argument(
        "--output-scoreboard",
        type=Path,
        default=Path("reports/scoreboard.md"),
        help="Output markdown path for scoreboard.",
    )
    pub.add_argument(
        "--output-manifest",
        type=Path,
        default=Path("reports/publication_bundle_manifest_v1.json"),
        help="Output JSON manifest path for publication-bundle audit metadata.",
    )
    pub.add_argument(
        "--no-manifest",
        action="store_true",
        help="Skip writing publication-bundle manifest JSON.",
    )
    pub.add_argument("--dotenv", type=Path, default=Path(".env"), help="Optional .env file to load into env vars.")

    inversion = sub.add_parser("inversion-robustness", help="Build daily-vs-monthly T10Y2Y inversion definition comparison report.")
    inversion.add_argument(
        "--permutation-party-term",
        type=Path,
        default=Path("reports/permutation_party_term_v1.csv"),
        help="Permutation term-party CSV containing inversion metrics (typically from `rb randomization --all-metrics`).",
    )
    inversion.add_argument(
        "--output-csv",
        type=Path,
        default=Path("reports/inversion_definition_robustness_v1.csv"),
        help="Output CSV path.",
    )
    inversion.add_argument(
        "--output-md",
        type=Path,
        default=Path("reports/inversion_definition_robustness_v1.md"),
        help="Output markdown path.",
    )
    inversion.add_argument("--dotenv", type=Path, default=Path(".env"), help="Optional .env file to load into env vars.")

    cpi = sub.add_parser("cpi-robustness", help="Build SA-vs-NSA CPI paired-metric comparison report.")
    cpi.add_argument(
        "--permutation-party-term",
        type=Path,
        default=Path("reports/permutation_party_term_v1.csv"),
        help="Permutation term-party CSV containing CPI SA/NSA level metrics (typically from `rb randomization --all-metrics`).",
    )
    cpi.add_argument(
        "--output-csv",
        type=Path,
        default=Path("reports/cpi_sa_nsa_robustness_v1.csv"),
        help="Output CSV path.",
    )
    cpi.add_argument(
        "--output-md",
        type=Path,
        default=Path("reports/cpi_sa_nsa_robustness_v1.md"),
        help="Output markdown path.",
    )
    cpi.add_argument("--dotenv", type=Path, default=Path(".env"), help="Optional .env file to load into env vars.")

    return p.parse_args()


def main() -> int:
    args = _parse_args()
    load_dotenv(args.dotenv, override=False)

    if args.cmd == "ingest":
        ingest_from_spec(
            spec_path=args.spec,
            refresh=bool(args.refresh),
            only_sources=set(args.sources) if args.sources else None,
            only_series=set(args.series) if args.series else None,
        )
        return 0

    if args.cmd == "presidents":
        ensure_presidents(
            refresh=bool(args.refresh),
            source=str(args.source),
            output_csv=args.output,
            granularity=str(args.granularity),
        )
        return 0

    if args.cmd == "congress":
        out = ensure_congress_control(refresh=bool(args.refresh))
        if Path(args.output) != out:
            # Copy to requested output path.
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(out.read_text(encoding="utf-8"), encoding="utf-8")
        return 0

    if args.cmd == "regimes":
        ensure_regime_pipeline(
            refresh=bool(args.refresh),
            spec_path=args.spec,
            attribution_path=args.attribution,
            presidents_csv=args.presidents,
            president_source=str(args.president_source),
            president_granularity=str(args.president_granularity),
            congress_csv=args.congress_control,
            output_windows_labels_csv=args.output_windows_labels,
            output_windows_presidents_csv=args.output_windows_presidents,
            output_window_metrics_csv=args.output_window_metrics,
            output_regime_summary_csv=args.output_regime_summary,
            output_alignment_summary_csv=args.output_alignment_summary,
            output_party_summary_csv=args.output_party_summary,
        )
        return 0

    if args.cmd == "compute":
        if not args.presidents.exists():
            ensure_presidents(
                refresh=False,
                source=str(args.president_source),
                output_csv=args.presidents,
                granularity=str(args.president_granularity),
            )
        compute_term_metrics(
            spec_path=args.spec,
            attribution_path=args.attribution,
            presidents_csv=args.presidents,
            output_terms_csv=args.output_terms,
            output_party_csv=args.output_party,
        )
        return 0

    if args.cmd == "validate":
        status, out = validate_all(
            spec_path=args.spec,
            presidents_csv=args.presidents,
            congress_control_csv=args.congress_control if args.congress_control.exists() else None,
            term_metrics_csv=args.term_metrics if args.term_metrics.exists() else None,
            party_summary_csv=args.party_summary if args.party_summary.exists() else None,
        )
        print(out)
        return status

    if args.cmd == "scoreboard":
        if not args.party_summary.exists():
            raise FileNotFoundError(f"Missing {args.party_summary}; run `rb compute` first.")
        write_scoreboard_md(
            spec_path=args.spec,
            party_summary_csv=args.party_summary,
            out_path=args.output,
            primary_only=not bool(args.all_metrics),
            window_metrics_csv=args.window_metrics if args.window_metrics.exists() else None,
            window_labels_csv=args.window_labels if args.window_labels.exists() else None,
            inference_stability_summary_csv=(
                args.inference_stability_summary if args.inference_stability_summary.exists() else None
            ),
            claims_table_csv=args.claims_table if args.claims_table.exists() else None,
            output_within_president_deltas_csv=args.output_within_president_deltas,
            within_president_min_window_days=max(0, int(args.within_president_min_window_days)),
            show_robustness_links=not bool(args.no_robustness_links),
            show_publication_tiers=not bool(args.no_publication_tier_columns),
        )
        return 0

    if args.cmd == "randomization":
        run_randomization(
            term_metrics_csv=args.term_metrics,
            output_party_term_csv=args.output_party_term,
            permutations=max(0, int(args.permutations)),
            bootstrap_samples=max(0, int(args.bootstrap_samples)),
            seed=int(args.seed),
            term_block_years=max(0, int(args.term_block_years)),
            q_threshold=float(args.q_threshold),
            min_term_n_obs=max(0, int(args.min_term_n_obs)),
            min_within_n_both=max(0, int(args.min_within_n_both)),
            primary_only=not bool(args.all_metrics),
            window_metrics_csv=args.window_metrics if args.window_metrics.exists() else None,
            window_labels_csv=args.window_labels if args.window_labels.exists() else None,
            output_unified_within_term_csv=args.output_unified_within_term,
            output_evidence_summary_csv=args.output_evidence_summary,
            output_evidence_md=args.output_evidence_md,
            output_inversion_robustness_csv=(None if bool(args.skip_inversion_robustness) else args.output_inversion_robustness_csv),
            output_inversion_robustness_md=(None if bool(args.skip_inversion_robustness) else args.output_inversion_robustness_md),
            output_cpi_robustness_csv=(None if bool(args.skip_cpi_robustness) else args.output_cpi_robustness_csv),
            output_cpi_robustness_md=(None if bool(args.skip_cpi_robustness) else args.output_cpi_robustness_md),
            within_president_min_window_days=max(0, int(args.within_president_min_window_days)),
            include_diagnostic_metrics=bool(args.include_diagnostic_metrics),
        )
        return 0

    if args.cmd == "randomization-stability":
        seeds_raw = [s.strip() for s in str(args.seeds).split(",")]
        seeds: list[int] = []
        for s in seeds_raw:
            if not s:
                continue
            try:
                seeds.append(int(s))
            except ValueError as exc:
                raise ValueError(f"Invalid seed {s!r} in --seeds={args.seeds!r}") from exc
        if not seeds:
            raise ValueError("No valid seeds parsed from --seeds")
        run_randomization_seed_stability(
            term_metrics_csv=args.term_metrics,
            out_csv=args.output,
            seeds=seeds,
            permutations=max(0, int(args.permutations)),
            bootstrap_samples=max(0, int(args.bootstrap_samples)),
            term_block_years=max(0, int(args.term_block_years)),
            q_threshold=float(args.q_threshold),
            min_term_n_obs=max(0, int(args.min_term_n_obs)),
            primary_only=not bool(args.all_metrics),
            include_diagnostic_metrics=bool(args.include_diagnostic_metrics),
        )
        return 0

    if args.cmd == "inference-table":
        perm_path = args.permutation_party_term if args.permutation_party_term.exists() else None
        write_inference_table(
            term_metrics_csv=args.term_metrics,
            permutation_party_term_csv=perm_path,
            out_csv=args.output_csv,
            out_md=args.output_md,
            nw_lags=max(0, int(args.nw_lags)),
            wild_cluster_draws=max(0, int(args.wild_cluster_draws)),
            wild_cluster_seed=int(args.wild_cluster_seed),
        )
        return 0

    if args.cmd == "inference-stability":
        seeds = _parse_int_list_csv(str(args.seeds), arg_name="--seeds")
        if not seeds:
            raise ValueError("No valid seeds parsed from --seeds")
        draws_grid = _parse_int_list_csv(str(args.draws_grid), arg_name="--draws-grid")
        write_wild_cluster_stability_table(
            term_metrics_csv=args.term_metrics,
            out_csv=args.output,
            seeds=seeds,
            draws=draws_grid if draws_grid else max(0, int(args.wild_cluster_draws)),
        )
        return 0

    if args.cmd == "inference-stability-summary":
        write_wild_cluster_stability_summary(
            stability_csv=args.stability_csv,
            out_csv=args.output,
        )
        return 0

    if args.cmd == "randomization-compare":
        if not args.base_party_term.exists():
            raise FileNotFoundError(f"Missing base term CSV: {args.base_party_term}")
        if not args.alt_party_term.exists():
            raise FileNotFoundError(f"Missing alt term CSV: {args.alt_party_term}")
        alt_within = args.alt_within if args.alt_within is not None else None
        base_within = args.base_within if args.base_within.exists() else None
        if alt_within is not None and not alt_within.exists():
            raise FileNotFoundError(f"Missing alt within CSV: {alt_within}")
        compare_randomization_outputs(
            base_party_term_csv=args.base_party_term,
            alt_party_term_csv=args.alt_party_term,
            base_within_csv=base_within,
            alt_within_csv=alt_within,
            out_csv=args.output,
        )
        return 0

    if args.cmd == "claims-table":
        if not args.baseline_party_term.exists():
            raise FileNotFoundError(f"Missing baseline term CSV: {args.baseline_party_term}")
        if not args.strict_party_term.exists():
            raise FileNotFoundError(f"Missing strict term CSV: {args.strict_party_term}")
        base_within = args.baseline_within if args.baseline_within.exists() else None
        strict_within = args.strict_within if args.strict_within.exists() else None
        if (base_within is None) != (strict_within is None):
            raise FileNotFoundError(
                "Within-president claims require both baseline and strict within CSVs or neither."
            )
        write_claims_table(
            baseline_party_term_csv=args.baseline_party_term,
            strict_party_term_csv=args.strict_party_term,
            baseline_within_csv=base_within,
            strict_within_csv=strict_within,
            out_csv=args.output,
            inference_table_csv=args.inference_table if args.inference_table.exists() else None,
            inference_stability_summary_csv=(
                args.inference_stability_summary if args.inference_stability_summary.exists() else None
            ),
            publication_mode=bool(args.publication_mode),
            publication_hac_p_threshold=float(args.publication_hac_p_threshold),
            publication_downgrade_unstable=bool(args.publication_stability_gate),
        )
        return 0

    if args.cmd == "narrative-template":
        if not args.claims_table.exists():
            raise FileNotFoundError(f"Missing claims table CSV: {args.claims_table}")
        if not args.inference_table.exists():
            raise FileNotFoundError(f"Missing inference table CSV: {args.inference_table}")
        write_publication_narrative_template(
            claims_table_csv=args.claims_table,
            inference_table_csv=args.inference_table,
            inference_stability_summary_csv=(
                args.inference_stability_summary if args.inference_stability_summary.exists() else None
            ),
            out_md=args.output,
        )
        return 0

    if args.cmd == "publication-bundle":
        if not args.party_summary.exists():
            raise FileNotFoundError(f"Missing party summary CSV: {args.party_summary}")
        if not args.term_metrics.exists():
            raise FileNotFoundError(f"Missing term metrics CSV: {args.term_metrics}")
        if not args.baseline_party_term.exists():
            raise FileNotFoundError(f"Missing baseline term CSV: {args.baseline_party_term}")
        bundle_profile = str(args.profile)

        if bundle_profile == "baseline_only":
            strict_party_term = args.baseline_party_term
            base_within = args.baseline_within if args.baseline_within.exists() else None
            strict_within = base_within
        else:
            strict_party_term = args.strict_party_term
            if not strict_party_term.exists():
                raise FileNotFoundError(f"Missing strict term CSV: {strict_party_term}")
            base_within = args.baseline_within if args.baseline_within.exists() else None
            strict_within = args.strict_within if args.strict_within.exists() else None

        if (base_within is None) != (strict_within is None):
            raise FileNotFoundError(
                "Publication bundle requires both baseline/strict within CSVs or neither."
            )

        within_backfill: dict[str, dict[str, int]] = {}
        if not bool(args.no_backfill_within_mde):
            for name, path in (("baseline_within", base_within), ("strict_within", strict_within)):
                if path is None:
                    continue
                stats = ensure_within_mde_columns(
                    within_csv=path,
                    window_metrics_csv=args.window_metrics,
                    window_labels_csv=args.window_labels,
                )
                if int(stats.get("file_rewritten", 0)) == 1:
                    within_backfill[name] = stats

        write_inference_table(
            term_metrics_csv=args.term_metrics,
            permutation_party_term_csv=args.baseline_party_term,
            out_csv=args.output_inference_csv,
            out_md=args.output_inference_md,
            nw_lags=max(0, int(args.nw_lags)),
            wild_cluster_draws=max(0, int(args.wild_cluster_draws)),
            wild_cluster_seed=int(args.wild_cluster_seed),
        )
        if not bool(args.skip_inference_stability):
            stab_seeds = _parse_int_list_csv(
                str(args.inference_stability_seeds),
                arg_name="--inference-stability-seeds",
            )
            if not stab_seeds:
                raise ValueError("No valid seeds parsed from --inference-stability-seeds")
            stab_draws = _parse_int_list_csv(
                str(args.inference_stability_draws_grid),
                arg_name="--inference-stability-draws-grid",
            )
            write_wild_cluster_stability_table(
                term_metrics_csv=args.term_metrics,
                out_csv=args.output_inference_stability_csv,
                seeds=stab_seeds,
                draws=stab_draws if stab_draws else max(0, int(args.wild_cluster_draws)),
            )
            write_wild_cluster_stability_summary(
                stability_csv=args.output_inference_stability_csv,
                out_csv=args.output_inference_stability_summary_csv,
            )
        write_claims_table(
            baseline_party_term_csv=args.baseline_party_term,
            strict_party_term_csv=strict_party_term,
            baseline_within_csv=base_within,
            strict_within_csv=strict_within,
            out_csv=args.output_claims,
            inference_table_csv=args.output_inference_csv if args.output_inference_csv.exists() else None,
            inference_stability_summary_csv=(
                args.output_inference_stability_summary_csv if not bool(args.skip_inference_stability) else None
            ),
            publication_mode=True,
            publication_hac_p_threshold=float(args.publication_hac_p_threshold),
            publication_downgrade_unstable=not bool(args.no_publication_stability_gate),
        )
        write_publication_narrative_template(
            claims_table_csv=args.output_claims,
            inference_table_csv=args.output_inference_csv,
            inference_stability_summary_csv=(
                args.output_inference_stability_summary_csv if not bool(args.skip_inference_stability) else None
            ),
            out_md=args.output_narrative,
        )
        write_scoreboard_md(
            spec_path=args.spec,
            party_summary_csv=args.party_summary,
            out_path=args.output_scoreboard,
            primary_only=not bool(args.all_metrics),
            window_metrics_csv=args.window_metrics if args.window_metrics.exists() else None,
            window_labels_csv=args.window_labels if args.window_labels.exists() else None,
            term_randomization_csv=args.baseline_party_term,
            within_randomization_csv=base_within,
            inference_stability_summary_csv=(
                args.output_inference_stability_summary_csv if not bool(args.skip_inference_stability) else None
            ),
            claims_table_csv=args.output_claims,
            within_president_min_window_days=max(0, int(args.within_president_min_window_days)),
            show_robustness_links=True,
            show_publication_tiers=True,
        )

        if not bool(args.no_manifest):
            manifest = {
                "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"),
                "command": "rb publication-bundle",
                "profile": bundle_profile,
                "parameters": {
                    "all_metrics": bool(args.all_metrics),
                    "within_president_min_window_days": max(0, int(args.within_president_min_window_days)),
                    "backfill_within_mde": not bool(args.no_backfill_within_mde),
                    "nw_lags": max(0, int(args.nw_lags)),
                    "wild_cluster_draws": max(0, int(args.wild_cluster_draws)),
                    "wild_cluster_seed": int(args.wild_cluster_seed),
                    "publication_hac_p_threshold": float(args.publication_hac_p_threshold),
                    "skip_inference_stability": bool(args.skip_inference_stability),
                    "inference_stability_seeds": str(args.inference_stability_seeds),
                    "inference_stability_draws_grid": str(args.inference_stability_draws_grid),
                    "publication_stability_gate": not bool(args.no_publication_stability_gate),
                },
                "environment": {
                    "python_version": sys.version.split()[0],
                    "platform": platform.platform(),
                    "cwd": str(Path.cwd()),
                    "git_head": _git_head(Path.cwd()),
                },
                "inputs": {
                    "spec": _file_meta(args.spec),
                    "party_summary": _file_meta(args.party_summary),
                    "term_metrics": _file_meta(args.term_metrics),
                    "baseline_party_term": _file_meta(args.baseline_party_term),
                    "strict_party_term_used": _file_meta(strict_party_term),
                    "baseline_within": _file_meta(base_within),
                    "strict_within_used": _file_meta(strict_within),
                    "window_metrics": _file_meta(args.window_metrics if args.window_metrics.exists() else None),
                    "window_labels": _file_meta(args.window_labels if args.window_labels.exists() else None),
                    "pyproject_toml": _file_meta(Path("pyproject.toml") if Path("pyproject.toml").exists() else None),
                    "uv_lock": _file_meta(Path("uv.lock") if Path("uv.lock").exists() else None),
                },
                "upstream": {
                    "raw_source_latest_artifacts": _latest_raw_source_artifacts(Path("data/raw")),
                    "fred_vintage_summary": _fred_vintage_summary(Path("data/raw")),
                },
                "outputs": {
                    "inference_csv": _file_meta(args.output_inference_csv),
                    "inference_md": _file_meta(args.output_inference_md),
                    "inference_stability_csv": _file_meta(
                        args.output_inference_stability_csv if not bool(args.skip_inference_stability) else None
                    ),
                    "inference_stability_summary_csv": _file_meta(
                        args.output_inference_stability_summary_csv if not bool(args.skip_inference_stability) else None
                    ),
                    "claims_csv": _file_meta(args.output_claims),
                    "narrative_md": _file_meta(args.output_narrative),
                    "scoreboard_md": _file_meta(args.output_scoreboard),
                },
                "mutations": {
                    "within_mde_backfill": within_backfill,
                },
            }
            _write_json_atomic(args.output_manifest, manifest)
        return 0

    if args.cmd == "inversion-robustness":
        write_inversion_definition_robustness(
            permutation_party_term_csv=args.permutation_party_term,
            out_csv=args.output_csv,
            out_md=args.output_md,
        )
        return 0

    if args.cmd == "cpi-robustness":
        write_cpi_sa_nsa_level_robustness(
            permutation_party_term_csv=args.permutation_party_term,
            out_csv=args.output_csv,
            out_md=args.output_md,
        )
        return 0

    raise RuntimeError(f"unhandled cmd={args.cmd!r}")
