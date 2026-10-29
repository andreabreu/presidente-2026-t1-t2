from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

MAD_TO_SIGMA = 1.4826
SEVERITY_ISOLATED = 1
SEVERITY_SIGNIFICANT = 2
SEVERITY_MULTIPLE = 3
SEVERITY_DOCUMENTAL = 4
SEVERITY_FORENSIC = 5
MIN_UNIT_SIZE_FOR_SEVERITY_2 = 100


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    p = np.asarray(p_values, dtype=float)
    q = np.full(p.shape, np.nan)
    valid = ~np.isnan(p)
    n = int(valid.sum())
    if n == 0:
        return q
    order = np.argsort(p[valid])
    ranked = p[valid][order] * n / np.arange(1, n + 1)
    adjusted = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.clip(adjusted, 0.0, 1.0)
    q[valid] = out
    return q


def robust_z(values: np.ndarray) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    median = np.nanmedian(x)
    mad = np.nanmedian(np.abs(x - median)) * MAD_TO_SIGMA
    if not np.isfinite(mad) or mad == 0:
        return np.zeros_like(x)
    return (x - median) / mad


def normal_two_sided_p(z: np.ndarray) -> np.ndarray:
    return 2.0 * scipy_stats.norm.sf(np.abs(np.asarray(z, dtype=float)))


def two_sided_empirical_p(values: np.ndarray) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    n = len(x)
    if n == 0:
        return x
    order = np.argsort(x, kind="mergesort")
    sorted_x = x[order]
    n_le = np.searchsorted(sorted_x, x, side="right")
    n_ge = n - np.searchsorted(sorted_x, x, side="left")
    return np.minimum(1.0, 2.0 * np.minimum(n_le, n_ge) / n)


def grouped_reference_metrics(frame: pd.DataFrame, value: str, group_keys: Sequence[str]) -> pd.DataFrame:
    grouped = frame.groupby(list(group_keys), sort=False, observed=True)[value]
    return pd.DataFrame(
        {
            "z_mad": grouped.transform(lambda s: robust_z(s.to_numpy())),
            "p_empirico": grouped.transform(lambda s: two_sided_empirical_p(s.to_numpy())),
            "n_referencia": grouped.transform("size"),
        },
        index=frame.index,
    )


def aptos_bin_labels(aptos: np.ndarray, edges: Sequence[int]) -> np.ndarray:
    edges = list(edges)
    labels = [f"{edges[i]}-{edges[i + 1] - 1}" for i in range(len(edges) - 1)] + [f"{edges[-1]}+"]
    index = np.digitize(np.asarray(aptos), edges[1:], right=False)
    return np.asarray(labels, dtype=object)[index]


def binomial_tail_at_least_share(n: np.ndarray, p: np.ndarray, share: float) -> np.ndarray:
    n = np.asarray(n, dtype=int)
    p = np.clip(np.asarray(p, dtype=float), 1e-12, 1 - 1e-12)
    threshold = np.ceil(share * n).astype(int)
    return scipy_stats.binom.sf(threshold - 1, n, p)


def poisson_excess_p(observed: np.ndarray, expected: np.ndarray) -> np.ndarray:
    observed = np.asarray(observed, dtype=int)
    expected = np.asarray(expected, dtype=float)
    return scipy_stats.poisson.sf(observed - 1, np.maximum(expected, 1e-12))


def last_digit_chi_square(counts: np.ndarray) -> tuple[float, float, int]:
    digits = np.asarray(counts, dtype=int) % 10
    observed = np.bincount(digits, minlength=10)
    n = int(observed.sum())
    if n == 0:
        return np.nan, np.nan, 0
    statistic, p_value = scipy_stats.chisquare(observed)
    return float(statistic), float(p_value), n


def count_identical_row_pairs(matrix: np.ndarray) -> int:
    if len(matrix) < 2:
        return 0
    _, counts = np.unique(matrix, axis=0, return_counts=True)
    return int((counts * (counts - 1) // 2).sum())


def hash_rows(matrix: np.ndarray, weights: np.ndarray) -> np.ndarray:
    return (matrix.astype(np.int64) * weights).sum(axis=-1)


def count_identical_hash_pairs(hashes: np.ndarray) -> int:
    _, counts = np.unique(hashes, return_counts=True)
    return int((counts * (counts - 1) // 2).sum())


def permuted_identical_pairs(matrix: np.ndarray, n_permutations: int, rng: np.random.Generator) -> np.ndarray:
    rows, cols = matrix.shape
    weights = rng.integers(1, np.iinfo(np.int64).max // max(rows, 1), size=cols, dtype=np.int64)
    hashes = np.zeros((n_permutations, rows), dtype=np.int64)
    for j in range(cols):
        column = np.broadcast_to(matrix[:, j].astype(np.int64), (n_permutations, rows))
        hashes += rng.permuted(column, axis=1) * weights[j]
    return np.array([count_identical_hash_pairs(hashes[k]) for k in range(n_permutations)], dtype=int)


def permutation_p_value(observed: int, null_draws: np.ndarray) -> float:
    return float((1 + np.sum(null_draws >= observed)) / (1 + len(null_draws)))


def bimodality_coefficient(values: np.ndarray) -> float:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 4:
        return np.nan
    skew = scipy_stats.skew(x, bias=False)
    excess_kurtosis = scipy_stats.kurtosis(x, bias=False)
    return float((skew**2 + 1) / (excess_kurtosis + 3 * (n - 1) ** 2 / ((n - 2) * (n - 3))))


def severity_from_rubric(
    q_fdr_min: float, n_eleitores: int, has_exclusion_flag: bool, n_independent_findings: int, documental: bool
) -> int:
    if documental:
        return SEVERITY_DOCUMENTAL
    if n_independent_findings >= 2:
        return SEVERITY_MULTIPLE
    significant = np.isfinite(q_fdr_min) and q_fdr_min < 0.05
    if significant and n_eleitores >= MIN_UNIT_SIZE_FOR_SEVERITY_2 and not has_exclusion_flag:
        return SEVERITY_SIGNIFICANT
    return SEVERITY_ISOLATED


def component_from_q(q_fdr: np.ndarray, cutoff: float) -> np.ndarray:
    q = np.asarray(q_fdr, dtype=float)
    component = np.where(np.isfinite(q) & (q < cutoff), 1.0 - q, 0.0)
    return component


def weighted_risk_score(components: dict[str, np.ndarray], weights: dict[str, float], available: Sequence[str]) -> np.ndarray:
    total_weight = sum(weights[name] for name in available)
    if total_weight == 0:
        raise ValueError("nenhum componente disponível para o risk_score")
    score = sum(weights[name] * np.asarray(components[name], dtype=float) for name in available) / total_weight
    return np.clip(score, 0.0, 1.0)


def jaccard(a: Sequence, b: Sequence) -> float:
    set_a, set_b = set(a), set(b)
    if not set_a and not set_b:
        return 1.0
    return len(set_a & set_b) / len(set_a | set_b)
