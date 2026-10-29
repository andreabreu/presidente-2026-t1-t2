from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .constants import KEY_COLUMNS, LEVEL_SECAO, ORIGEM_BRANCOS_NULOS, ORIGEM_OUTROS_ELIMINADOS
from .data import Contest
from .fdr import benjamini_hochberg, effective_strata, stratified_tests

PERCENT = 100.0
TARGET_COLUMN = "share_a_t2_valid"
WEIGHT_COLUMN = "comp_t2"
CONTROL_COLUMNS = ["log_aptos_t1", "taxa_comp_t1", "delta_comp_pp"]


@dataclass
class ResidualFit:
    frame: pd.DataFrame
    n_parameters: int
    columns: list[str]
    r_squared: float


def t1_share_columns(balances: pd.DataFrame, contest: Contest) -> pd.DataFrame:
    comp = balances["comp_t1"].where(balances["comp_t1"] > 0, np.nan)
    columns = {"share_t1_a": balances["votos_t1_a"] / comp}
    for nr in contest.major_eliminated:
        columns[f"share_t1_{nr}"] = balances[f"votos_t1_{nr}"] / comp
    minor = sum((balances[f"votos_t1_{nr}"] for nr in contest.minor_eliminated if f"votos_t1_{nr}" in balances), 0.0)
    columns[f"share_{ORIGEM_OUTROS_ELIMINADOS}"] = minor / comp
    columns[f"share_{ORIGEM_BRANCOS_NULOS}"] = (balances["brancos_t1"] + balances["nulos_t1"]) / comp
    return pd.DataFrame(columns)


def control_columns(balances: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "log_aptos_t1": np.log(balances["aptos_t1"].where(balances["aptos_t1"] > 0, np.nan)),
            "taxa_comp_t1": balances["taxa_comp_t1"],
            "delta_comp_pp": balances["delta_comp_pp"],
        }
    )


def dummies(series: pd.Series, prefix: str) -> pd.DataFrame:
    frame = pd.get_dummies(series.astype(str), prefix=prefix, dtype=float)
    return frame.iloc[:, 1:] if frame.shape[1] > 1 else frame.iloc[:, :0]


def build_design(balances: pd.DataFrame, contest: Contest, level: str, with_controls: bool) -> pd.DataFrame:
    parts = [t1_share_columns(balances, contest)]
    if with_controls:
        parts.append(control_columns(balances))
        parts.append(dummies(balances["porte"], "porte"))
        if level != LEVEL_SECAO:
            parts.append(dummies(balances["uf"], "uf"))
    design = pd.concat(parts, axis=1)
    design.insert(0, "intercepto", 1.0)
    return design


def demean_within(frame: pd.DataFrame, groups: pd.Series) -> pd.DataFrame:
    return frame - frame.groupby(groups.values).transform("mean")


def weighted_studentized_residuals(X: np.ndarray, y: np.ndarray, w: np.ndarray, extra_dof: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    root = np.sqrt(w)
    Xw, yw = X * root[:, None], y * root
    beta, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
    fitted = X @ beta
    raw = y - fitted
    residual_w = yw - Xw @ beta
    gram_inverse = np.linalg.pinv(Xw.T @ Xw)
    leverage = np.einsum("ij,jk,ik->i", Xw, gram_inverse, Xw)
    n, p = X.shape
    dof = max(n - p - extra_dof, 1)
    sigma = np.sqrt((residual_w**2).sum() / dof)
    studentized = residual_w / (sigma * np.sqrt(np.clip(1 - leverage, 1e-12, None)))
    r_squared = 1 - (residual_w**2).sum() / ((yw - np.average(yw)) ** 2).sum()
    return raw, studentized, fitted, float(r_squared)


def fit_residual_model(balances: pd.DataFrame, contest: Contest, level: str, with_controls: bool) -> ResidualFit:
    design = build_design(balances, contest, level, with_controls)
    y = balances[TARGET_COLUMN]
    w = balances[WEIGHT_COLUMN]
    keep = design.notna().all(axis=1) & y.notna() & (w > 0)
    design, y, w = design[keep], y[keep], w[keep]
    extra_dof = 0
    if level == LEVEL_SECAO:
        municipality = balances.loc[keep, "cd_municipio"]
        design = demean_within(design, municipality).drop(columns="intercepto")
        y = demean_within(y.to_frame(), municipality)[TARGET_COLUMN]
        extra_dof = municipality.nunique()
    raw, studentized, fitted, r_squared = weighted_studentized_residuals(
        design.to_numpy(float), y.to_numpy(float), w.to_numpy(float), extra_dof
    )
    out = balances.loc[keep, KEY_COLUMNS[level] + [c for c in ("nm_municipio",) if c in balances] + ["porte", "aptos_t1", "comp_t2", "share_a_t1_dupla", TARGET_COLUMN]].copy()
    out["predito"] = balances.loc[keep, TARGET_COLUMN] - raw
    out["residuo_pp"] = raw * PERCENT
    out["residuo_student"] = studentized
    return ResidualFit(out.reset_index(drop=True), design.shape[1], list(design.columns), r_squared)


def flag_residuals(fit: ResidualFit, q_threshold: float) -> pd.DataFrame:
    frame = fit.frame.copy()
    strata = effective_strata(frame, ["uf", "porte"], ["porte"])
    tests = stratified_tests(frame["residuo_student"], strata)
    frame = pd.concat([frame, tests], axis=1)
    frame["q_fdr"] = benjamini_hochberg(frame["p_param"].to_numpy())
    frame["flag"] = frame["q_fdr"] < q_threshold
    frame["effect_size"] = frame["residuo_pp"]
    return frame


def summarize_by_uf(flags: pd.DataFrame, q_threshold: float) -> pd.DataFrame:
    summary = (
        flags.groupby("uf")
        .agg(n_unidades=("flag", "size"), n_flag=("flag", "sum"), residuo_pp_mediano=("residuo_pp", "median"),
             residuo_pp_abs_p99=("residuo_pp", lambda s: s.abs().quantile(0.99)))
        .reset_index()
    )
    summary["falsos_positivos_esperados"] = summary["n_flag"] * q_threshold
    summary["q_threshold"] = q_threshold
    return summary


def jaccard(left: pd.Index, right: pd.Index) -> float:
    union = len(left.union(right))
    return float(len(left.intersection(right)) / union) if union else float("nan")


def flagged_ids(flags: pd.DataFrame, level: str) -> pd.Index:
    keyed = flags.loc[flags["flag"], KEY_COLUMNS[level]].astype(str).agg("|".join, axis=1)
    return pd.Index(keyed)
