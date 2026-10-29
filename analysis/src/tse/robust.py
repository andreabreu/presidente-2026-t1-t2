from __future__ import annotations

import numpy as np
import pandas as pd

MAD_TO_SIGMA = 1.4826


def median_and_mad(values) -> tuple[float, float]:
    array = np.asarray(values, dtype=float)
    array = array[~np.isnan(array)]
    if array.size == 0:
        return np.nan, np.nan
    center = float(np.median(array))
    mad = float(np.median(np.abs(array - center))) * MAD_TO_SIGMA
    return center, mad


def z_mad(values, center: float, mad: float) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if not np.isfinite(mad) or mad == 0:
        return np.full(array.shape, np.nan)
    return (array - center) / mad


def empirical_percentile(values) -> np.ndarray:
    series = pd.Series(np.asarray(values, dtype=float))
    return series.rank(method="average", pct=True).to_numpy()


def add_stratified_robust_scores(frame: pd.DataFrame, value_column: str, strata: list[str], min_strata_size: int, prefix: str | None = None) -> pd.DataFrame:
    prefix = prefix or value_column
    result = frame.copy()
    reference_median = f"{prefix}_ref_mediana"
    reference_mad = f"{prefix}_ref_mad"
    result[reference_median] = np.nan
    result[reference_mad] = np.nan
    result[f"{prefix}_z_mad"] = np.nan
    result[f"{prefix}_p_empirico"] = np.nan
    result[f"{prefix}_n_estrato"] = 0
    for _, group in result.groupby(strata, dropna=False, sort=False):
        index = group.index
        values = group[value_column]
        valid = values.notna().sum()
        result.loc[index, f"{prefix}_n_estrato"] = int(valid)
        if valid < min_strata_size:
            continue
        center, mad = median_and_mad(values)
        result.loc[index, reference_median] = center
        result.loc[index, reference_mad] = mad
        result.loc[index, f"{prefix}_z_mad"] = z_mad(values, center, mad)
        result.loc[index, f"{prefix}_p_empirico"] = empirical_percentile(values)
    return result


def quantile_bins(values: pd.Series, quantiles: list[float], labels: list[str]) -> pd.Series:
    edges = [-np.inf, *values.quantile(quantiles).tolist(), np.inf]
    return pd.cut(values, bins=edges, labels=labels, include_lowest=True, duplicates="drop").astype(str)
