from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .constants import MAD_TO_SIGMA, MIN_STRATUM_SIZE


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    p = np.asarray(p_values, dtype=float)
    q = np.full(p.shape, np.nan)
    valid = ~np.isnan(p)
    n = valid.sum()
    if n == 0:
        return q
    order = np.argsort(p[valid])
    ranked = p[valid][order] * n / np.arange(1, n + 1)
    adjusted = np.minimum.accumulate(ranked[::-1])[::-1]
    result = np.empty(n)
    result[order] = np.clip(adjusted, 0, 1)
    q[valid] = result
    return q


def robust_z(values: pd.Series) -> pd.Series:
    median = values.median()
    mad = (values - median).abs().median() * MAD_TO_SIGMA
    if not np.isfinite(mad) or mad == 0:
        return pd.Series(np.nan, index=values.index)
    return (values - median) / mad


def empirical_two_sided_p(values: pd.Series) -> pd.Series:
    magnitude = values.abs()
    return magnitude.rank(method="min", ascending=False) / magnitude.notna().sum()


def effective_strata(frame: pd.DataFrame, fine_keys: list[str], coarse_keys: list[str]) -> pd.Series:
    fine = frame[fine_keys].astype(str).agg("|".join, axis=1)
    coarse = frame[coarse_keys].astype(str).agg("|".join, axis=1)
    sizes = fine.map(fine.value_counts())
    return fine.where(sizes >= MIN_STRATUM_SIZE, coarse)


def stratified_tests(values: pd.Series, strata: pd.Series) -> pd.DataFrame:
    grouped = values.groupby(strata)
    z = grouped.transform(robust_z)
    p_empirico = grouped.transform(empirical_two_sided_p)
    p_param = pd.Series(2 * stats.norm.sf(np.abs(z)), index=values.index)
    return pd.DataFrame({"estrato": strata, "z_mad": z, "p_empirico": p_empirico, "p_param": p_param})
