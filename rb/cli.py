from __future__ import annotations

import argparse
from pathlib import Path

from rb.env import load_dotenv
from rb.ingest import ingest_from_spec


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

    raise RuntimeError(f"unhandled cmd={args.cmd!r}")

