from __future__ import annotations

import numpy as np
import pandas as pd

PERCENT = 100.0


def pair_share(wide: pd.DataFrame, finalist_a: int, finalist_b: int, turno: int) -> pd.Series:
    a, b = wide[f"c{finalist_a}_t{turno}"], wide[f"c{finalist_b}_t{turno}"]
    return a / (a + b).where((a + b) > 0)


def weighted_r2(y: np.ndarray, fitted: np.ndarray, w: np.ndarray) -> float:
    residual = y - fitted
    mean = np.average(y, weights=w)
    return float(1 - (w * residual**2).sum() / (w * (y - mean) ** 2).sum())


def wls_fit(X: np.ndarray, y: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    root = np.sqrt(w)
    beta, *_ = np.linalg.lstsq(X * root[:, None], y * root, rcond=None)
    fitted = X @ beta
    gram_inverse = np.linalg.pinv((X * root[:, None]).T @ (X * root[:, None]))
    leverage = np.einsum("ij,jk,ik->i", X * root[:, None], gram_inverse, X * root[:, None])
    return beta, fitted, leverage


def studentized(y: np.ndarray, fitted: np.ndarray, w: np.ndarray, leverage: np.ndarray, n_parameters: int) -> np.ndarray:
    residual_w = np.sqrt(w) * (y - fitted)
    sigma = np.sqrt((residual_w**2).sum() / max(len(y) - n_parameters, 1))
    return residual_w / (sigma * np.sqrt(np.clip(1 - leverage, 1e-12, None)))


def design_matrix(wide: pd.DataFrame, finalist_a: int, finalist_b: int, major: list[int], with_uf: bool) -> np.ndarray:
    comp = wide.comp_t1.where(wide.comp_t1 > 0)
    columns = [np.ones(len(wide)), (wide[f"c{finalist_a}_t1"] / comp).to_numpy()]
    for nr in major:
        columns.append((wide[f"c{nr}_t1"] / comp).to_numpy())
    columns.append((wide.brancos_nulos_t1 / comp).to_numpy())
    columns.append(np.log(wide.aptos_t1.where(wide.aptos_t1 > 0)).to_numpy())
    columns.append((wide.comp_t1 / wide.aptos_t1.where(wide.aptos_t1 > 0)).to_numpy())
    if with_uf:
        dummies = pd.get_dummies(wide.SG_UF, drop_first=True, dtype=float)
        columns.extend(dummies[c].to_numpy() for c in dummies.columns)
    return np.column_stack(columns)


def r2_ladder(wide: pd.DataFrame, finalist_a: int, finalist_b: int, major: list[int]) -> pd.DataFrame:
    """R² ponderado de share_A_T2 sob especificações aninhadas, para localizar de onde vem o R² ~ 1."""
    y = pair_share(wide, finalist_a, finalist_b, 2).to_numpy(float)
    w = wide.comp_t2.to_numpy(float)
    x_pair = pair_share(wide, finalist_a, finalist_b, 1).to_numpy(float)
    keep = np.isfinite(y) & np.isfinite(x_pair) & (w > 0)
    specs = {
        "so_intercepto": np.ones((keep.sum(), 1)),
        "so_share_dupla_t1": np.column_stack([np.ones(keep.sum()), x_pair[keep]]),
        "shares_t1_e_controles_sem_uf": design_matrix(wide[keep], finalist_a, finalist_b, major, with_uf=False),
        "shares_t1_e_controles_com_uf": design_matrix(wide[keep], finalist_a, finalist_b, major, with_uf=True),
    }
    rows = []
    for name, X in specs.items():
        valid = np.isfinite(X).all(axis=1)
        _, fitted, _ = wls_fit(X[valid], y[keep][valid], w[keep][valid])
        rows.append({"especificacao": name, "n_parametros": X.shape[1], "r2_ponderado": weighted_r2(y[keep][valid], fitted, w[keep][valid]), "n": int(valid.sum())})
    return pd.DataFrame(rows)


def residual_scores(wide: pd.DataFrame, finalist_a: int, finalist_b: int, major: list[int], weighted: bool) -> pd.DataFrame:
    y = pair_share(wide, finalist_a, finalist_b, 2).to_numpy(float)
    w = wide.comp_t2.to_numpy(float) if weighted else np.ones(len(wide))
    X = design_matrix(wide, finalist_a, finalist_b, major, with_uf=True)
    keep = np.isfinite(y) & np.isfinite(X).all(axis=1) & (wide.comp_t2.to_numpy() > 0)
    _, fitted, leverage = wls_fit(X[keep], y[keep], w[keep])
    out = wide.loc[keep, [c for c in ("SG_UF", "CD_MUNICIPIO", "NR_ZONA") if c in wide]].copy()
    out["comp_t2"] = wide.loc[keep, "comp_t2"].to_numpy()
    out["share_a_t2"] = y[keep]
    out["residuo_pp"] = (y[keep] - fitted) * PERCENT
    out["residuo_student"] = studentized(y[keep], fitted, w[keep], leverage, X.shape[1])
    return out.reset_index(drop=True)


def size_dependence(scores: pd.DataFrame, top_n: int) -> dict:
    """Quanto o ranking por |resíduo studentizado| é explicado pelo tamanho da unidade."""
    ranked = scores.assign(abs_student=scores.residuo_student.abs(), abs_pp=scores.residuo_pp.abs())
    top = ranked.nlargest(top_n, "abs_student")
    return {
        "spearman_abs_student_vs_comp": float(ranked[["abs_student", "comp_t2"]].corr(method="spearman").iloc[0, 1]),
        "spearman_abs_pp_vs_comp": float(ranked[["abs_pp", "comp_t2"]].corr(method="spearman").iloc[0, 1]),
        "mediana_comp_top": float(top.comp_t2.median()),
        "mediana_comp_todas": float(ranked.comp_t2.median()),
        "mediana_abs_pp_top": float(top.abs_pp.median()),
        "p90_abs_pp_todas": float(ranked.abs_pp.quantile(0.9)),
    }


def overdispersion_ratio(scores: pd.DataFrame) -> float:
    """Variância observada dos resíduos (em share) vs variância binomial p(1-p)/n: >>1 indica heterogeneidade política, não ruído amostral."""
    p = np.clip(scores.share_a_t2.to_numpy(), 1e-6, 1 - 1e-6)
    binomial = (p * (1 - p) / scores.comp_t2.to_numpy()).mean()
    observed = ((scores.residuo_pp / PERCENT) ** 2).mean()
    return float(observed / binomial)
