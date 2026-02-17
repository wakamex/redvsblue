"""Integration tests for rb.validate against the CI fixture."""

from __future__ import annotations

from pathlib import Path

import pytest

from rb.validate import validate_presidents_csv

FIXTURE_DIR = Path(__file__).parent / "fixtures"
PRESIDENTS_MIN = FIXTURE_DIR / "presidents_min.csv"


class TestPresidentsFixture:
    def test_fixture_exists(self):
        assert PRESIDENTS_MIN.exists(), (
            f"{PRESIDENTS_MIN} missing — CI workflow depends on this fixture"
        )

    def test_validates_without_errors(self):
        issues = validate_presidents_csv(PRESIDENTS_MIN)
        errors = [i for i in issues if i.level == "ERROR"]
        assert errors == [], f"Validation errors: {errors}"

    def test_has_d_and_r_terms(self):
        import csv

        with PRESIDENTS_MIN.open("r", newline="") as f:
            parties = {r["party_abbrev"] for r in csv.DictReader(f)}
        assert "D" in parties
        assert "R" in parties
