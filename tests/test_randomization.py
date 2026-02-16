"""Unit tests for core math in rb.randomization."""

from __future__ import annotations

import random

import pytest

from rb.randomization import (
    _add_bh_q_values,
    _bootstrap_diff_d_minus_r,
    _diff_d_minus_r,
    _p_two_sided,
    _percentile,
    _std_population,
)


# ── _std_population ──────────────────────────────────────────────────


class TestStdPopulation:
    def test_empty_returns_none(self):
        assert _std_population([]) is None

    def test_single_element_returns_zero(self):
        assert _std_population([42.0]) == 0.0

    def test_known_dataset(self):
        # Population std of [2, 4, 4, 4, 5, 5, 7, 9] = 2.0
        result = _std_population([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        assert result == pytest.approx(2.0)

    def test_identical_values(self):
        assert _std_population([5.0, 5.0, 5.0]) == 0.0


# ── _percentile ──────────────────────────────────────────────────────


class TestPercentile:
    def test_empty_returns_none(self):
        assert _percentile([], 0.5) is None

    def test_single_element(self):
        assert _percentile([7.0], 0.5) == 7.0

    def test_median_odd(self):
        # Sorted: [1, 3, 5]. q=0.5 → p=1.0 → ys[1] = 3
        assert _percentile([5.0, 1.0, 3.0], 0.5) == 3.0

    def test_median_even_interpolation(self):
        # Sorted: [1, 2, 3, 4]. q=0.5 → p=1.5 → (2+3)/2 = 2.5
        assert _percentile([1.0, 2.0, 3.0, 4.0], 0.5) == pytest.approx(2.5)

    def test_lower_bound(self):
        # q=0.0 → first element
        assert _percentile([10.0, 20.0, 30.0], 0.0) == 10.0

    def test_upper_bound(self):
        # q=1.0 → last element
        assert _percentile([10.0, 20.0, 30.0], 1.0) == 30.0

    def test_quarter(self):
        # Sorted: [1, 2, 3, 4, 5]. q=0.25 → p=1.0 → ys[1] = 2
        assert _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 0.25) == 2.0

    def test_interpolation(self):
        # Sorted: [10, 20]. q=0.3 → p=0.3 → lo=0, hi=1, w=0.3
        # result = 10*0.7 + 20*0.3 = 13.0
        assert _percentile([10.0, 20.0], 0.3) == pytest.approx(13.0)


# ── _diff_d_minus_r ──────────────────────────────────────────────────


class TestDiffDMinusR:
    def test_basic(self):
        # D mean=3, R mean=1 → diff=2
        values = [2.0, 4.0, 1.0, 1.0]
        labels = ["D", "D", "R", "R"]
        assert _diff_d_minus_r(values, labels) == pytest.approx(2.0)

    def test_no_d_returns_none(self):
        assert _diff_d_minus_r([1.0, 2.0], ["R", "R"]) is None

    def test_no_r_returns_none(self):
        assert _diff_d_minus_r([1.0, 2.0], ["D", "D"]) is None

    def test_empty(self):
        assert _diff_d_minus_r([], []) is None

    def test_single_each(self):
        assert _diff_d_minus_r([10.0, 3.0], ["D", "R"]) == pytest.approx(7.0)


# ── _bootstrap_diff_d_minus_r ────────────────────────────────────────


class TestBootstrapDiffDMinusR:
    def test_empty_d(self):
        assert _bootstrap_diff_d_minus_r(
            d_vals=[], r_vals=[1.0], n_samples=100, rng=random.Random(0)
        ) == (None, None)

    def test_empty_r(self):
        assert _bootstrap_diff_d_minus_r(
            d_vals=[1.0], r_vals=[], n_samples=100, rng=random.Random(0)
        ) == (None, None)

    def test_zero_samples(self):
        assert _bootstrap_diff_d_minus_r(
            d_vals=[1.0], r_vals=[2.0], n_samples=0, rng=random.Random(0)
        ) == (None, None)

    def test_identical_groups_ci_near_zero(self):
        # If D and R are the same values, bootstrap diff ≈ 0
        vals = [5.0, 5.0, 5.0, 5.0, 5.0]
        lo, hi = _bootstrap_diff_d_minus_r(
            d_vals=vals, r_vals=vals, n_samples=1000, rng=random.Random(42)
        )
        assert lo == pytest.approx(0.0)
        assert hi == pytest.approx(0.0)

    def test_seeded_reproducibility(self):
        d = [1.0, 2.0, 3.0]
        r = [4.0, 5.0, 6.0]
        result1 = _bootstrap_diff_d_minus_r(
            d_vals=d, r_vals=r, n_samples=500, rng=random.Random(99)
        )
        result2 = _bootstrap_diff_d_minus_r(
            d_vals=d, r_vals=r, n_samples=500, rng=random.Random(99)
        )
        assert result1 == result2

    def test_ci_contains_expected_diff(self):
        # D ≈ 10, R ≈ 0 → CI should be entirely positive
        d = [9.0, 10.0, 11.0]
        r = [0.0, 0.0, 0.0]
        lo, hi = _bootstrap_diff_d_minus_r(
            d_vals=d, r_vals=r, n_samples=2000, rng=random.Random(7)
        )
        assert lo is not None and hi is not None
        assert lo > 0.0
        assert hi > lo


# ── _add_bh_q_values ────────────────────────────────────────────────


class TestAddBhQValues:
    def test_empty_rows(self):
        rows: list[dict[str, str]] = []
        _add_bh_q_values(rows, p_col="p", q_col="q")
        assert rows == []

    def test_single_p(self):
        # With m=1, q = p * 1 / 1 = p
        rows = [{"p": "0.040000"}]
        _add_bh_q_values(rows, p_col="p", q_col="q")
        assert float(rows[0]["q"]) == pytest.approx(0.04)

    def test_three_p_values(self):
        # p-values: 0.01, 0.04, 0.03, m=3
        # Sorted by p: (0.01, rank1), (0.03, rank2), (0.04, rank3)
        # BH step-up from bottom:
        #   rank3: min(1.0, 0.04*3/3) = 0.04
        #   rank2: min(0.04, 0.03*3/2) = min(0.04, 0.045) = 0.04
        #   rank1: min(0.04, 0.01*3/1) = min(0.04, 0.03) = 0.03
        rows = [
            {"id": "a", "p": "0.010000"},
            {"id": "b", "p": "0.040000"},
            {"id": "c", "p": "0.030000"},
        ]
        _add_bh_q_values(rows, p_col="p", q_col="q")
        assert float(rows[0]["q"]) == pytest.approx(0.03)   # p=0.01
        assert float(rows[1]["q"]) == pytest.approx(0.04)   # p=0.04
        assert float(rows[2]["q"]) == pytest.approx(0.04)   # p=0.03

    def test_missing_p_gets_empty_q(self):
        rows = [{"p": "0.050000"}, {"p": ""}]
        _add_bh_q_values(rows, p_col="p", q_col="q")
        assert float(rows[0]["q"]) == pytest.approx(0.05)
        assert rows[1]["q"] == ""

    def test_monotonicity(self):
        # q-values should be non-decreasing when sorted by p-value
        rows = [
            {"p": "0.001000"},
            {"p": "0.010000"},
            {"p": "0.050000"},
            {"p": "0.100000"},
            {"p": "0.500000"},
        ]
        _add_bh_q_values(rows, p_col="p", q_col="q")
        qs = [float(r["q"]) for r in rows]
        # Rows are already sorted by p so q should be non-decreasing
        for i in range(len(qs) - 1):
            assert qs[i] <= qs[i + 1] + 1e-12


# ── _p_two_sided ─────────────────────────────────────────────────────


class TestPTwoSided:
    def test_empty_perm_diffs_returns_none(self):
        assert _p_two_sided(1.0, []) is None

    def test_all_extreme(self):
        # All perm diffs have |d| >= |observed|
        # extreme=4, p = (1+4)/(1+4) = 1.0
        assert _p_two_sided(1.0, [1.0, -2.0, 3.0, -1.5]) == pytest.approx(1.0)

    def test_none_extreme(self):
        # observed=10, perm_diffs all < 10 in absolute value
        # extreme=0, p = 1/(1+5) = 1/6
        result = _p_two_sided(10.0, [1.0, -1.0, 2.0, -2.0, 0.5])
        assert result == pytest.approx(1.0 / 6.0)

    def test_known_count(self):
        # observed=3.0, perm_diffs: |5|>=3 yes, |1|>=3 no, |-3|>=3 yes, |2|>=3 no
        # extreme=2, p = (1+2)/(1+4) = 3/5 = 0.6
        result = _p_two_sided(3.0, [5.0, 1.0, -3.0, 2.0])
        assert result == pytest.approx(0.6)

    def test_observed_zero(self):
        # observed=0 → |d| >= 0 is always true for all perm_diffs
        # extreme = N, p = (1+N)/(1+N) = 1.0
        assert _p_two_sided(0.0, [0.0, 1.0, -1.0]) == pytest.approx(1.0)
