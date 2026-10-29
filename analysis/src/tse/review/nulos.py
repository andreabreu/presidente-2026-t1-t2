from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from .constants import NR_VOTAVEL_BRANCO, NR_VOTAVEL_NULO


def unit_frame(sections: pd.DataFrame, votes: pd.DataFrame, keys: list[str], finalist_a: int) -> pd.DataFrame:
    """Agrega seções em unidades (município ou zona) com taxa de nulos, margem do líder e sinal partidário."""
    nominal = votes[~votes.NR_VOTAVEL.isin([NR_VOTAVEL_BRANCO, NR_VOTAVEL_NULO])]
    by_candidate = nominal.groupby(keys + ["NR_TURNO", "NR_VOTAVEL"])["votos"].sum().reset_index()
    ranked = by_candidate.sort_values("votos", ascending=False)
    top1 = ranked.drop_duplicates(keys + ["NR_TURNO"]).rename(columns={"votos": "votos_lider", "NR_VOTAVEL": "lider"})
    top2 = ranked[~ranked.index.isin(top1.index)].drop_duplicates(keys + ["NR_TURNO"]).rename(columns={"votos": "votos_segundo"}).drop(columns="NR_VOTAVEL")
    totals = by_candidate.groupby(keys + ["NR_TURNO"])["votos"].sum().rename("nominais").reset_index()
    margin = totals.merge(top1, on=keys + ["NR_TURNO"]).merge(top2, on=keys + ["NR_TURNO"], how="left")
    margin["margem_lider"] = (margin.votos_lider - margin.votos_segundo.fillna(0)) / margin.nominais
    margin["margem_assinada_a"] = np.where(margin.lider == finalist_a, margin.margem_lider, -margin.margem_lider)
    counts = sections.groupby(keys + ["NR_TURNO"]).agg(aptos=("QT_APTOS", "sum"), comparecimento=("QT_COMPARECIMENTO", "sum"), nulos=("QT_VOTOS_NULOS", "sum")).reset_index()
    counts["taxa_nulos"] = counts.nulos / counts.comparecimento.where(counts.comparecimento > 0)
    return counts.merge(margin, on=keys + ["NR_TURNO"])


def regression_row(frame: pd.DataFrame, turno: int, regressor: str, weighted: bool, cluster: str, label: str) -> dict:
    data = frame[(frame.NR_TURNO == turno)].dropna(subset=["taxa_nulos", regressor]).copy()
    data["log_aptos"] = np.log(data.aptos)
    formula = f"taxa_nulos ~ {regressor} + log_aptos + C(SG_UF)"
    weights = data.comparecimento if weighted else np.ones(len(data))
    model = smf.wls(formula, data=data, weights=weights).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(data[cluster])[0]})
    low, high = model.conf_int().loc[regressor]
    return {
        "NR_TURNO": turno, "especificacao": label, "regressor": regressor, "n": int(model.nobs), "ponderado": weighted, "cluster": cluster,
        "coeficiente": float(model.params[regressor]), "ic95_inferior": float(low), "ic95_superior": float(high), "p_valor": float(model.pvalues[regressor]),
    }


def regression_battery(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    rows = []
    for turno in (1, 2):
        for regressor in ("margem_lider", "margem_assinada_a"):
            for weighted in (False, True):
                rows.append(regression_row(frame, turno, regressor, weighted, "SG_UF", label))
    return pd.DataFrame(rows)


def reverse_regression_row(frame: pd.DataFrame, turno: int) -> dict:
    """Reproduz a direção do autor: margem_lider ~ taxa_nulos + FE UF + quintil de aptos, HC1."""
    data = frame[frame.NR_TURNO == turno].dropna(subset=["taxa_nulos", "margem_lider"]).copy()
    data["faixa_aptos"] = pd.qcut(data.aptos, 5, labels=False)
    model = smf.ols("margem_lider ~ taxa_nulos + C(SG_UF) + C(faixa_aptos)", data=data).fit(cov_type="HC1")
    low, high = model.conf_int().loc["taxa_nulos"]
    return {"NR_TURNO": turno, "n": int(model.nobs), "coeficiente": float(model.params["taxa_nulos"]), "ic95_inferior": float(low), "ic95_superior": float(high), "p_valor": float(model.pvalues["taxa_nulos"])}
