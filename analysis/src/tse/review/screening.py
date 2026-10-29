from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .unanimity import benjamini_hochberg

MAD_TO_SIGMA = 1.4826
NORMAL_TAIL_3_5 = 2 * stats.norm.sf(3.5)


def robust_z(values: np.ndarray) -> np.ndarray:
    median = np.median(values)
    mad = np.median(np.abs(values - median)) * MAD_TO_SIGMA
    return (values - median) / mad if mad > 0 else np.zeros_like(values)


def beta_binomial_moments(successes: np.ndarray, trials: np.ndarray) -> tuple[float, float]:
    """(media, rho) por método dos momentos ponderado para taxa = successes/trials dentro de um estrato."""
    p = successes / trials
    mean = successes.sum() / trials.sum()
    variance = mean * (1 - mean)
    if variance <= 0:
        return mean, 0.0
    excess = ((p - mean) ** 2 - variance / trials)
    scale = variance * (1 - 1 / trials)
    return float(mean), float(np.clip(excess.sum() / scale.sum(), 1e-6, 0.5))


def beta_binomial_two_sided_p(successes: np.ndarray, trials: np.ndarray, mean: float, rho: float) -> np.ndarray:
    concentration = (1 - rho) / rho
    alpha, beta = mean * concentration, (1 - mean) * concentration
    k, n = successes.astype(int), trials.astype(int)
    lower = stats.betabinom.cdf(k, n, alpha, beta)
    upper = stats.betabinom.sf(k - 1, n, alpha, beta)
    return np.minimum(1.0, 2 * np.minimum(lower, upper))


def stratum_comparison(stratum: pd.DataFrame, q_threshold: float) -> dict:
    rate = (stratum.QT_COMPARECIMENTO / stratum.QT_APTOS).to_numpy(float)
    z = robust_z(rate)
    p_normal = 2 * stats.norm.sf(np.abs(z))
    mean, rho = beta_binomial_moments(stratum.QT_COMPARECIMENTO.to_numpy(float), stratum.QT_APTOS.to_numpy(float))
    p_bb = beta_binomial_two_sided_p(stratum.QT_COMPARECIMENTO.to_numpy(float), stratum.QT_APTOS.to_numpy(float), mean, rho)
    q_normal, q_bb = benjamini_hochberg(p_normal), benjamini_hochberg(p_bb)
    return {
        "n": len(stratum), "rho_beta_binomial": rho, "media": mean,
        "share_abs_z_gt_3_5": float((np.abs(z) > 3.5).mean()), "esperado_normal_abs_z_gt_3_5": NORMAL_TAIL_3_5,
        "assimetria": float(stats.skew(rate)), "curtose_excesso": float(stats.kurtosis(rate)),
        "flags_z_normal_bh": int((q_normal < q_threshold).sum()), "flags_beta_binomial_bh": int((q_bb < q_threshold).sum()),
        "flags_ambos": int(((q_normal < q_threshold) & (q_bb < q_threshold)).sum()),
        "flags_z_normal_cauda_baixa": int(((q_normal < q_threshold) & (z < 0)).sum()),
    }


def compare_nulls_by_stratum(sections: pd.DataFrame, strata: pd.Series, q_threshold: float, min_size: int) -> pd.DataFrame:
    rows = []
    for label, block in sections.groupby(strata):
        if len(block) < min_size:
            continue
        rows.append({"estrato": label, **stratum_comparison(block, q_threshold)})
    return pd.DataFrame(rows)


def identical_pair_count(matrix: np.ndarray) -> int:
    _, counts = np.unique(matrix, axis=0, return_counts=True)
    return int((counts * (counts - 1) // 2).sum())


def multinomial_null_pairs(matrix: np.ndarray, replicates: int, rng: np.random.Generator) -> np.ndarray:
    """Nulo que preserva o comparecimento de cada seção e as proporções do município (multinomial)."""
    totals = matrix.sum(axis=1)
    probabilities = matrix.sum(axis=0) / matrix.sum()
    draws = np.empty(replicates, dtype=int)
    for r in range(replicates):
        simulated = rng.multinomial(totals, probabilities)
        draws[r] = identical_pair_count(simulated)
    return draws


def twins_global_test(matrices: dict[int, np.ndarray], replicates: int, seed: int) -> dict:
    observed, expected, variance = 0, 0.0, 0.0
    for municipality, matrix in matrices.items():
        if len(matrix) < 2:
            continue
        rng = np.random.default_rng([seed, municipality])
        observed += identical_pair_count(matrix)
        null = multinomial_null_pairs(matrix, replicates, rng)
        expected += null.mean()
        variance += null.var(ddof=1)
    z = (observed - expected) / np.sqrt(variance) if variance > 0 else np.nan
    return {"pares_observados": observed, "pares_esperados_multinomial": expected, "z_global": float(z), "p_global_normal": float(2 * stats.norm.sf(abs(z))) if np.isfinite(z) else np.nan, "n_municipios": len(matrices)}
