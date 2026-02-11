from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from rb.cli import (
    _assert_randomization_scope_matches_mode,
    _assert_randomization_scopes_compatible,
    _canonical_randomization_scope,
    _csv_inference_scope,
)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


class ScopeGuardTests(unittest.TestCase):
    def test_csv_inference_scope_reads_primary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "term_primary.csv"
            _write_csv(
                path,
                ["metric_id", "metric_primary", "inference_scope"],
                [
                    {"metric_id": "m1", "metric_primary": "1", "inference_scope": "primary"},
                    {"metric_id": "m2", "metric_primary": "0", "inference_scope": "primary"},
                ],
            )
            self.assertEqual(_csv_inference_scope(path), "primary")

    def test_csv_inference_scope_raises_on_inconsistent_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "term_inconsistent.csv"
            _write_csv(
                path,
                ["metric_id", "metric_primary", "inference_scope"],
                [
                    {"metric_id": "m1", "metric_primary": "1", "inference_scope": "primary"},
                    {"metric_id": "m2", "metric_primary": "0", "inference_scope": "all"},
                ],
            )
            with self.assertRaisesRegex(ValueError, "Inconsistent inference_scope"):
                _csv_inference_scope(path)

    def test_mode_check_prefers_inference_scope_over_metric_primary(self) -> None:
        # Even though metric_primary values look primary-only, explicit scope=all should govern.
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "term_metadata_preferred.csv"
            _write_csv(
                path,
                ["metric_id", "metric_primary", "inference_scope"],
                [
                    {"metric_id": "m1", "metric_primary": "1", "inference_scope": "all"},
                    {"metric_id": "m2", "metric_primary": "1", "inference_scope": "all"},
                ],
            )
            with self.assertRaisesRegex(ValueError, "inference_scope='all'.*primary mode"):
                _assert_randomization_scope_matches_mode(
                    path=path,
                    all_metrics_mode=False,
                    label="baseline",
                )

    def test_mode_check_falls_back_to_metric_primary_for_legacy_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            legacy_primary = Path(tmpdir) / "legacy_primary.csv"
            _write_csv(
                legacy_primary,
                ["metric_id", "metric_primary"],
                [
                    {"metric_id": "m1", "metric_primary": "1"},
                    {"metric_id": "m2", "metric_primary": "1"},
                ],
            )
            legacy_all = Path(tmpdir) / "legacy_all.csv"
            _write_csv(
                legacy_all,
                ["metric_id", "metric_primary"],
                [
                    {"metric_id": "m1", "metric_primary": "1"},
                    {"metric_id": "m2", "metric_primary": "0"},
                ],
            )

            # Primary mode accepts primary-only legacy files.
            _assert_randomization_scope_matches_mode(
                path=legacy_primary,
                all_metrics_mode=False,
                label="primary_legacy",
            )
            # All-metrics mode rejects primary-only legacy files.
            with self.assertRaisesRegex(ValueError, "appears primary-only"):
                _assert_randomization_scope_matches_mode(
                    path=legacy_primary,
                    all_metrics_mode=True,
                    label="primary_legacy",
                )
            # Primary mode rejects mixed legacy files.
            with self.assertRaisesRegex(ValueError, "includes non-primary rows"):
                _assert_randomization_scope_matches_mode(
                    path=legacy_all,
                    all_metrics_mode=False,
                    label="all_legacy",
                )

    def test_scope_compatibility_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = Path(tmpdir) / "primary_1.csv"
            p2 = Path(tmpdir) / "primary_2.csv"
            a1 = Path(tmpdir) / "all_1.csv"
            _write_csv(
                p1,
                ["metric_id", "metric_primary", "inference_scope"],
                [{"metric_id": "m1", "metric_primary": "1", "inference_scope": "primary"}],
            )
            _write_csv(
                p2,
                ["metric_id", "metric_primary"],
                [{"metric_id": "m2", "metric_primary": "1"}],  # legacy, should infer primary
            )
            _write_csv(
                a1,
                ["metric_id", "metric_primary", "inference_scope"],
                [{"metric_id": "m3", "metric_primary": "0", "inference_scope": "all"}],
            )

            self.assertEqual(_canonical_randomization_scope(p1), "primary")
            self.assertEqual(_canonical_randomization_scope(p2), "primary")
            self.assertEqual(_canonical_randomization_scope(a1), "all")

            # Compatible scopes pass.
            _assert_randomization_scopes_compatible(paths=[(p1, "base"), (p2, "alt")])
            # Mixed scopes fail.
            with self.assertRaisesRegex(ValueError, "Incompatible randomization scopes"):
                _assert_randomization_scopes_compatible(paths=[(p1, "base"), (a1, "alt")])


if __name__ == "__main__":
    unittest.main()
