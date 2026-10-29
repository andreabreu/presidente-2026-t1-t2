import numpy as np
import pandas as pd
import pytest

from tse.robust import add_stratified_robust_scores, empirical_percentile, median_and_mad, quantile_bins, z_mad


def test_median_and_mad_scaled():
    center, mad = median_and_mad([1, 2, 3, 4, 100])
    assert center == 3
    assert mad == pytest.approx(1 * 1.4826)


def test_z_mad_zero_spread_gives_nan():
    assert np.isnan(z_mad([1, 2], 1.0, 0.0)).all()


def test_empirical_percentile_monotone():
    percentiles = empirical_percentile([10, 30, 20])
    assert percentiles.tolist() == pytest.approx([1 / 3, 1.0, 2 / 3])


def test_stratified_scores_skip_small_strata():
    frame = pd.DataFrame({"uf": ["A"] * 5 + ["B"] * 2, "x": [1, 2, 3, 4, 50, 1, 2]})
    scored = add_stratified_robust_scores(frame, "x", ["uf"], min_strata_size=3)
    assert scored.loc[scored["uf"] == "B", "x_z_mad"].isna().all()
    assert scored.loc[scored["uf"] == "A", "x_z_mad"].iloc[-1] > 3.5
    assert scored.loc[scored["uf"] == "A", "x_p_empirico"].iloc[-1] == pytest.approx(1.0)


def test_quantile_bins_labels():
    bins = quantile_bins(pd.Series([1, 2, 3, 4, 5, 6, 7, 8]), [0.5], ["baixo", "alto"])
    assert bins.tolist() == ["baixo"] * 4 + ["alto"] * 4
