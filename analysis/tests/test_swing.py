import numpy as np
import pandas as pd

from tse.swing.bounds import aggregate_bound_shares, compute_bound_sets, duncan_davis_bounds, full_retention_bounds
from tse.swing.constants import METHOD_BOUNDS_DUNCAN_DAVIS, METHOD_GOODMAN_SIMPLEX
from tse.swing.ecological import fit_goodman, goodman_bounded, goodman_simplex, goodman_wls
from tse.swing.fdr import benjamini_hochberg


def test_duncan_davis_bounds_contain_true_cell_and_respect_marginals():
    true_table = np.array([[[30.0, 10.0], [5.0, 55.0]]])
    origins = true_table.sum(axis=2)
    destinations = true_table.sum(axis=1)
    total = origins.sum(axis=1)

    low, high = duncan_davis_bounds(origins, destinations, total)

    assert np.all(low <= true_table) and np.all(true_table <= high)
    assert np.all(high <= origins[:, :, None]) and np.all(high <= destinations[:, None, :])
    assert low[0, 1, 1] == 55.0 - 5.0 + 0.0 or low[0, 1, 1] == max(0.0, 60.0 + 65.0 - 100.0)


def test_full_retention_bounds_are_tighter_and_flag_infeasible_units():
    origins = np.array([[40.0, 30.0, 20.0, 10.0], [40.0, 30.0, 20.0, 10.0]])
    destinations = np.array([[50.0, 35.0, 15.0], [35.0, 50.0, 15.0]])
    total = origins.sum(axis=1)

    low, high, feasible = full_retention_bounds(origins, destinations, total, (0, 1), (0, 1))
    plain_low, plain_high = duncan_davis_bounds(origins, destinations, total)

    assert feasible.tolist() == [True, False]
    assert high[0, 2, 0] == 10.0 and low[0, 2, 0] == 0.0
    assert np.all(high[0] <= plain_high[0] + 1e-9) and np.all(low[0] >= plain_low[0] - 1e-9)
    assert low[0, 0, 0] == 40.0 and high[0, 0, 1] == 0.0


def test_aggregated_bounds_are_fractions_in_unit_interval():
    origins = pd.DataFrame({"a1": [40.0, 20.0], "b1": [30.0, 40.0], "e1": [20.0, 30.0], "abs1": [10.0, 10.0]})
    destinations = pd.DataFrame({"a2": [55.0, 30.0], "b2": [35.0, 60.0], "abs2": [10.0, 10.0]})
    total = origins.sum(axis=1).to_numpy()

    sets = compute_bound_sets(origins, destinations, total, ("a1", "b1"), ("a2", "b2"))
    table = aggregate_bound_shares(sets[0], origins.to_numpy(), pd.Series(["BR", "BR"]))

    assert set(table["metodo"]) == {METHOD_BOUNDS_DUNCAN_DAVIS}
    assert ((table["bound_low"] >= 0) & (table["bound_high"] <= 1) & (table["bound_low"] <= table["bound_high"])).all()


def _toy_transfer_data(seed=0, n=400):
    rng = np.random.default_rng(seed)
    beta = np.array([[0.9, 0.05, 0.05], [0.05, 0.9, 0.05], [0.6, 0.3, 0.1], [0.2, 0.2, 0.6]])
    X = rng.dirichlet(np.ones(4), size=n)
    Y = X @ beta + rng.normal(0, 0.01, size=(n, 3))
    return X, Y, beta


def test_goodman_recovers_transfer_matrix_on_toy_data():
    X, Y, beta = _toy_transfer_data()
    weights = np.ones(len(X))

    wls = goodman_wls(X, Y, weights)
    bounded = goodman_bounded(X, Y, weights)

    assert np.allclose(wls, beta, atol=0.03)
    assert np.allclose(bounded, beta, atol=0.03)
    assert bounded.min() >= 0.0 and bounded.max() <= 1.0
    simplex = goodman_simplex(X, Y, weights)
    assert np.allclose(simplex, beta, atol=0.03)
    assert np.allclose(simplex.sum(axis=1), 1.0, atol=1e-6)


def test_simplex_goodman_enforces_row_sums_when_destinations_are_incomplete():
    rng = np.random.default_rng(4)
    X = rng.dirichlet(np.ones(3), size=300)
    beta = np.array([[0.7, 0.3], [0.2, 0.8], [0.5, 0.5]])
    Y = X @ beta + rng.normal(0, 0.02, size=(300, 2))

    simplex = goodman_simplex(X, Y, np.ones(300))

    assert np.allclose(simplex.sum(axis=1), 1.0, atol=1e-6)
    assert simplex.min() >= -1e-9 and simplex.max() <= 1 + 1e-9


def test_bounded_goodman_clips_to_unit_interval_when_wls_does_not():
    rng = np.random.default_rng(1)
    X = rng.dirichlet(np.ones(2), size=200)
    Y = (X @ np.array([[1.3], [-0.3]])) + rng.normal(0, 0.01, size=(200, 1))

    wls = goodman_wls(X, Y, np.ones(200))
    bounded = goodman_bounded(X, Y, np.ones(200))

    assert wls.max() > 1.0 and wls.min() < 0.0
    assert bounded.min() >= 0.0 and bounded.max() <= 1.0


def test_fit_goodman_bootstrap_ci_contains_truth():
    X, Y, beta = _toy_transfer_data(seed=2)
    total = np.full(len(X), 1000.0)
    origins = pd.DataFrame(X * 1000, columns=["a1", "b1", "e1", "abs1"])
    destinations = pd.DataFrame(Y * 1000, columns=["a2", "b2", "abs2"])

    result = fit_goodman(origins, destinations, total, np.ones(len(X)), METHOD_GOODMAN_SIMPLEX, np.random.default_rng(3), replicates=100)

    assert result.method == METHOD_GOODMAN_SIMPLEX
    coverage = (result.ci_low - 0.02 <= beta) & (beta <= result.ci_high + 0.02)
    assert coverage.mean() >= 0.9


def test_benjamini_hochberg_monotone_and_bounded():
    p = np.array([0.001, 0.01, 0.04, 0.2, 0.5, np.nan])

    q = benjamini_hochberg(p)

    assert np.isnan(q[-1])
    assert np.all(np.diff(q[:-1]) >= 0)
    assert q[0] == 0.005 and q[-2] == 0.5
