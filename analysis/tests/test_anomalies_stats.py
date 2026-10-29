import numpy as np
import pytest

from tse.anomalies.stats import (
    aptos_bin_labels,
    benjamini_hochberg,
    binomial_tail_at_least_share,
    count_identical_row_pairs,
    jaccard,
    permuted_identical_pairs,
    robust_z,
    severity_from_rubric,
    two_sided_empirical_p,
    weighted_risk_score,
)


def test_benjamini_hochberg_matches_known_values():
    p = np.array([0.01, 0.04, 0.03, 0.20])

    q = benjamini_hochberg(p)

    assert np.allclose(q, [0.04, 0.04 * 4 / 3, 0.04 * 4 / 3, 0.20])


def test_benjamini_hochberg_keeps_nan_and_is_monotone():
    p = np.array([0.001, np.nan, 0.5, 0.02])

    q = benjamini_hochberg(p)

    assert np.isnan(q[1])
    assert q[0] <= q[3] <= q[2] <= 1.0


def test_robust_z_is_zero_at_median_and_scaled_by_mad():
    values = np.array([1.0, 2.0, 3.0, 4.0, 100.0])

    z = robust_z(values)

    assert z[2] == 0.0
    assert z[4] > 3.5
    assert np.all(robust_z(np.full(5, 7.0)) == 0.0)


def test_two_sided_empirical_p_bounds_and_symmetry():
    values = np.arange(1, 101, dtype=float)

    p = two_sided_empirical_p(values)

    assert p.min() == pytest.approx(2 / 100)
    assert p[0] == p[-1]
    assert p.max() <= 1.0


def test_aptos_bins_follow_edges():
    labels = aptos_bin_labels(np.array([50, 199, 200, 350, 400, 900]), [50, 200, 300, 400])

    assert list(labels) == ["50-199", "50-199", "200-299", "300-399", "400+", "400+"]


def test_binomial_tail_is_bounded_and_monotone_in_p():
    n = np.array([100, 100])
    tails = binomial_tail_at_least_share(n, np.array([0.5, 0.95]), 0.98)

    assert 0.0 <= tails[0] < tails[1] <= 1.0
    assert binomial_tail_at_least_share(np.array([100]), np.array([1 - 1e-12]), 0.98)[0] == pytest.approx(1.0)


def test_identical_pairs_count_and_permutation_preserves_marginals():
    matrix = np.array([[1, 2], [1, 2], [1, 2], [3, 4]])

    assert count_identical_row_pairs(matrix) == 3
    null = permuted_identical_pairs(matrix, 20, np.random.default_rng(0))
    assert null.shape == (20,)
    assert null.max() <= 3


def test_severity_rubric_never_reaches_forensic():
    assert severity_from_rubric(0.5, 300, False, 1, False) == 1
    assert severity_from_rubric(0.01, 300, False, 1, False) == 2
    assert severity_from_rubric(0.01, 40, False, 1, False) == 1
    assert severity_from_rubric(0.01, 300, True, 1, False) == 1
    assert severity_from_rubric(0.01, 300, False, 2, False) == 3
    assert severity_from_rubric(np.nan, 300, False, 0, True) == 4


def test_weighted_risk_score_renormalises_available_components():
    components = {"a": np.array([1.0]), "b": np.array([0.0]), "c": np.array([1.0])}
    weights = {"a": 0.5, "b": 0.3, "c": 0.2}

    assert weighted_risk_score(components, weights, ["a", "c"])[0] == pytest.approx(1.0)
    assert weighted_risk_score(components, weights, ["a", "b"])[0] == pytest.approx(0.625)


def test_jaccard():
    assert jaccard([1, 2, 3], [2, 3, 4]) == pytest.approx(0.5)
    assert jaccard([], []) == 1.0
