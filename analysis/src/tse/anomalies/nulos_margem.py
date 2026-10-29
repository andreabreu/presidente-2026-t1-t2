from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats as scipy_stats

MIN_SECTIONS_PER_UF_SPEARMAN = 20
MIN_SECTIONS_PER_MUNICIPIO = 2


def municipio_frame(sections: pd.DataFrame) -> pd.DataFrame:
    grouped = sections.groupby(["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_TURNO"], observed=True)
    frame = grouped.agg(
        aptos=("QT_APTOS", "sum"),
        comparecimento=("QT_COMPARECIMENTO", "sum"),
        nulos=("QT_VOTOS_NULOS", "sum"),
        brancos=("QT_VOTOS_BRANCOS", "sum"),
        n_secoes=("NR_SECAO", "size"),
    ).reset_index()
    frame["taxa_nulos"] = frame["nulos"] / frame["comparecimento"]
    return frame


def municipio_margin(candidate_summary: pd.DataFrame, votes_by_candidate: pd.DataFrame) -> pd.DataFrame:
    keys = ["SG_UF", "CD_MUNICIPIO", "NR_TURNO"]
    ranked = votes_by_candidate.sort_values("votos", ascending=False)
    top1 = ranked.drop_duplicates(keys)[keys + ["votos"]].rename(columns={"votos": "votos_lider"})
    rest = ranked[~ranked.index.isin(top1.index)]
    top2 = rest.drop_duplicates(keys)[keys + ["votos"]].rename(columns={"votos": "votos_segundo"})
    totals = votes_by_candidate.groupby(keys)["votos"].sum().rename("votos_nominais").reset_index()
    frame = totals.merge(top1, on=keys).merge(top2, on=keys, how="left")
    frame["votos_segundo"] = frame["votos_segundo"].fillna(0)
    frame["margem_lider"] = (frame["votos_lider"] - frame["votos_segundo"]) / frame["votos_nominais"]
    return frame[keys + ["margem_lider", "votos_nominais"]]


def fixed_effects_regression(frame: pd.DataFrame, turno: int) -> dict:
    data = frame[frame["NR_TURNO"] == turno].dropna(subset=["taxa_nulos", "margem_lider"]).copy()
    full = smf.ols("margem_lider ~ taxa_nulos + C(SG_UF) + C(faixa_aptos)", data=data).fit(cov_type="HC1")
    restricted = smf.ols("margem_lider ~ C(SG_UF) + C(faixa_aptos)", data=data).fit()
    ci_low, ci_high = full.conf_int().loc["taxa_nulos"]
    partial_r2 = (restricted.ssr - full.ssr) / restricted.ssr
    return {
        "NR_TURNO": turno,
        "nivel": "municipio",
        "n": int(full.nobs),
        "coeficiente_taxa_nulos": float(full.params["taxa_nulos"]),
        "erro_padrao_hc1": float(full.bse["taxa_nulos"]),
        "ic95_inferior": float(ci_low),
        "ic95_superior": float(ci_high),
        "p_valor": float(full.pvalues["taxa_nulos"]),
        "r2_parcial": float(partial_r2),
        "r2_modelo": float(full.rsquared),
        "controles": "efeitos fixos de UF + faixa de aptos; erros-padrão HC1",
    }


def within_municipio_regression(sections: pd.DataFrame, turno: int) -> dict:
    data = sections[(sections["NR_TURNO"] == turno)].dropna(subset=["taxa_nulos", "margem_lider_secao"]).copy()
    counts = data.groupby("CD_MUNICIPIO")["NR_SECAO"].transform("size")
    data = data[counts >= MIN_SECTIONS_PER_MUNICIPIO]
    for column in ("taxa_nulos", "margem_lider_secao"):
        data[f"{column}_dm"] = data[column] - data.groupby("CD_MUNICIPIO")[column].transform("mean")
    model = smf.ols("margem_lider_secao_dm ~ taxa_nulos_dm", data=data).fit(
        cov_type="cluster", cov_kwds={"groups": data["CD_MUNICIPIO"]}
    )
    ci_low, ci_high = model.conf_int().loc["taxa_nulos_dm"]
    return {
        "NR_TURNO": turno,
        "nivel": "secao_dentro_municipio",
        "n": int(model.nobs),
        "coeficiente_taxa_nulos": float(model.params["taxa_nulos_dm"]),
        "erro_padrao_hc1": float(model.bse["taxa_nulos_dm"]),
        "ic95_inferior": float(ci_low),
        "ic95_superior": float(ci_high),
        "p_valor": float(model.pvalues["taxa_nulos_dm"]),
        "r2_parcial": float(model.rsquared),
        "r2_modelo": float(model.rsquared),
        "controles": "variáveis centradas por município (efeitos fixos); erros-padrão agrupados por município",
    }


def spearman_by_uf(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (uf, turno), group in frame.groupby(["SG_UF", "NR_TURNO"], observed=True):
        data = group.dropna(subset=["taxa_nulos", "margem_lider"])
        if len(data) < MIN_SECTIONS_PER_UF_SPEARMAN:
            continue
        rho = scipy_stats.spearmanr(data["taxa_nulos"], data["margem_lider"])
        low, high = _fisher_interval(rho.statistic, len(data))
        rows.append(
            {
                "SG_UF": uf,
                "NR_TURNO": turno,
                "n_municipios": len(data),
                "spearman_rho": float(rho.statistic),
                "ic95_inferior": low,
                "ic95_superior": high,
                "p_valor": float(rho.pvalue),
            }
        )
    return pd.DataFrame(rows)


def _fisher_interval(rho: float, n: int) -> tuple[float, float]:
    z = np.arctanh(np.clip(rho, -0.999999, 0.999999))
    half_width = scipy_stats.norm.ppf(0.975) / np.sqrt(max(n - 3, 1))
    return float(np.tanh(z - half_width)), float(np.tanh(z + half_width))
