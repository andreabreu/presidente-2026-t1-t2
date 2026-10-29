from __future__ import annotations

import re

import numpy as np
import pandas as pd
from scipy import stats

MIN_APTOS_TESTED = 50
PLACE_CATEGORIES = {
    "indigena_aldeia": r"IND[IÍ]GENA|ALDEIA|TRIBO|MALOCA|TUXAUA|CACIQUE",
    "quilombola_assentamento": r"QUILOMB|ASSENTAMENTO|ACAMPAMENTO",
    "prisional_socioeducativo": r"PRES[IÍ]DIO|PENITENCI|CADEIA|DETEN|PRISIONAL|SOCIOEDUC",
    "saude_asilo": r"HOSPITAL|ASILO|SANAT|CASA DE SA[UÚ]DE|POSTO DE SA[UÚ]DE",
    "exterior": r"^$",
}
OTHER_CATEGORY = "outro"


def near_unanimous_sections(sections: pd.DataFrame, leaders: pd.DataFrame, share_threshold: float, min_votes: int) -> pd.DataFrame:
    keys = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO"]
    frame = sections.merge(leaders, on=keys, how="inner")
    testable = (frame.QT_APTOS >= MIN_APTOS_TESTED) & (frame.ST_SECAO_INSTALADA == "Sim") & (frame.QT_COMPARECIMENTO > 0)
    frame = frame[testable].copy()
    frame["share_top1"] = frame.votos_top1 / frame.votos_nominais.where(frame.votos_nominais > 0)
    frame["quase_unanime"] = (frame.share_top1 >= share_threshold) & (frame.votos_nominais >= min_votes)
    return frame


def classify_place(names: pd.Series, uf: pd.Series) -> pd.Series:
    categories = pd.Series(OTHER_CATEGORY, index=names.index, dtype=object)
    for category, pattern in reversed(list(PLACE_CATEGORIES.items())):
        if category == "exterior":
            continue
        mask = names.fillna("").str.contains(pattern, flags=re.IGNORECASE, regex=True)
        categories[mask] = category
    categories[uf == "ZZ"] = "exterior"
    return categories


def municipal_leader_share(frame: pd.DataFrame) -> pd.DataFrame:
    keys = ["SG_UF", "CD_MUNICIPIO", "NR_TURNO"]
    by_candidate = frame.groupby(keys + ["nr_votavel_top1"])["votos_top1"].sum().reset_index()
    leader = by_candidate.sort_values("votos_top1", ascending=False).drop_duplicates(keys)
    totals = frame.groupby(keys)["votos_nominais"].sum().reset_index()
    leader = leader.merge(totals, on=keys)
    leader["share_lider_mun"] = leader.votos_top1 / leader.votos_nominais
    return leader.rename(columns={"nr_votavel_top1": "lider_mun"})[keys + ["lider_mun", "share_lider_mun"]]


def intraclass_rho_by_group(frame: pd.DataFrame, group: str) -> pd.Series:
    """rho de sobredispersão (beta-binomial) por método dos momentos: Var(p_i) = m(1-m)[rho + (1-rho)/n_i]."""
    def estimate(block: pd.DataFrame) -> float:
        m = block.share_lider_mun.to_numpy()
        n = block.votos_nominais.to_numpy(float)
        p = block.share_lider_secao.to_numpy()
        variance = m * (1 - m)
        valid = variance > 0
        excess = ((p - m) ** 2 - variance / n)[valid]
        scale = (variance * (1 - 1 / n))[valid]
        return float(np.clip(excess.sum() / scale.sum(), 0.0, 0.5))

    return frame.groupby(group).apply(estimate, include_groups=False)


def beta_binomial_tail(n: np.ndarray, mean: np.ndarray, rho: np.ndarray, share_threshold: float) -> np.ndarray:
    mean = np.clip(mean, 1e-9, 1 - 1e-9)
    rho = np.clip(rho, 1e-9, 1 - 1e-9)
    concentration = (1 - rho) / rho
    alpha, beta = mean * concentration, (1 - mean) * concentration
    threshold = np.ceil(share_threshold * n).astype(int)
    return stats.betabinom.sf(threshold - 1, n.astype(int), alpha, beta)


def binomial_tail(n: np.ndarray, mean: np.ndarray, share_threshold: float) -> np.ndarray:
    threshold = np.ceil(share_threshold * n).astype(int)
    return stats.binom.sf(threshold - 1, n.astype(int), np.clip(mean, 1e-12, 1 - 1e-12))


def municipal_excess_tests(frame: pd.DataFrame, share_threshold: float, min_votes: int, rho_group: str) -> pd.DataFrame:
    keys = ["SG_UF", "CD_MUNICIPIO", "NR_TURNO"]
    eligible = frame[frame.votos_nominais >= min_votes].merge(municipal_leader_share(frame[frame.votos_nominais >= min_votes]), on=keys)
    eligible["share_lider_secao"] = np.where(eligible.nr_votavel_top1 == eligible.lider_mun, eligible.share_top1, 1 - eligible.share_top1)
    rho = intraclass_rho_by_group(eligible, rho_group).rename("rho")
    eligible = eligible.merge(rho, left_on=rho_group, right_index=True)
    same_leader = (eligible.nr_votavel_top1 == eligible.lider_mun).to_numpy()
    n = eligible.votos_nominais.to_numpy(float)
    eligible["p_binomial"] = np.where(same_leader, binomial_tail(n, eligible.share_lider_mun.to_numpy(), share_threshold), 0.0)
    eligible["p_beta_binomial"] = np.where(same_leader, beta_binomial_tail(n, eligible.share_lider_mun.to_numpy(), eligible.rho.to_numpy(), share_threshold), 0.0)
    summary = eligible.groupby(keys).agg(
        n_secoes=("quase_unanime", "size"), observado=("quase_unanime", "sum"),
        esperado_binomial=("p_binomial", "sum"), esperado_beta_binomial=("p_beta_binomial", "sum"), rho=("rho", "first"),
    ).reset_index()
    for label in ("binomial", "beta_binomial"):
        summary[f"p_{label}"] = stats.poisson.sf(summary.observado - 1, np.maximum(summary[f"esperado_{label}"], 1e-12))
        summary[f"q_{label}"] = np.nan
        for _, index in summary.groupby("NR_TURNO").groups.items():
            summary.loc[index, f"q_{label}"] = benjamini_hochberg(summary.loc[index, f"p_{label}"].to_numpy())
    return summary


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    p = np.asarray(p_values, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order] * n / np.arange(1, n + 1)
    adjusted = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.clip(adjusted, 0, 1)
    return out
