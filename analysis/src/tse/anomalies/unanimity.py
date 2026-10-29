from __future__ import annotations

import numpy as np
import pandas as pd

from tse.anomalies.stats import benjamini_hochberg, binomial_tail_at_least_share, poisson_excess_p

MUNICIPIO_KEYS = ["SG_UF", "CD_MUNICIPIO", "NR_TURNO", "CD_CARGO"]


def flag_near_unanimous(sections: pd.DataFrame, share_threshold: float, min_valid_votes: int) -> pd.DataFrame:
    frame = sections.copy()
    frame["share_top1"] = frame["votos_top1"] / frame["votos_nominais"].replace(0, np.nan)
    frame["quase_unanime"] = (frame["share_top1"] >= share_threshold) & (frame["votos_nominais"] >= min_valid_votes)
    return frame


def municipio_excess(flagged: pd.DataFrame, share_threshold: float, min_valid_votes: int) -> pd.DataFrame:
    eligible = flagged.loc[flagged["votos_nominais"] >= min_valid_votes].copy()
    leader = _municipio_leader(eligible)
    eligible = eligible.merge(leader, on=MUNICIPIO_KEYS, how="left")
    same_leader = eligible["nr_votavel_top1"] == eligible["nr_votavel_lider_mun"]
    eligible["prob_binomial"] = np.where(
        same_leader,
        binomial_tail_at_least_share(
            eligible["votos_nominais"].to_numpy(), eligible["share_lider_mun"].to_numpy(), share_threshold
        ),
        0.0,
    )
    grouped = eligible.groupby(MUNICIPIO_KEYS, observed=True)
    summary = grouped.agg(
        n_secoes_testadas=("quase_unanime", "size"),
        n_quase_unanimes=("quase_unanime", "sum"),
        esperado_binomial=("prob_binomial", "sum"),
        share_lider_mun=("share_lider_mun", "first"),
    ).reset_index()
    summary["n_quase_unanimes"] = summary["n_quase_unanimes"].astype(int)
    summary["p_poisson"] = poisson_excess_p(summary["n_quase_unanimes"].to_numpy(), summary["esperado_binomial"].to_numpy())
    summary["q_fdr"] = np.nan
    for _, index in summary.groupby("NR_TURNO").groups.items():
        summary.loc[index, "q_fdr"] = benjamini_hochberg(summary.loc[index, "p_poisson"].to_numpy())
    summary["excesso"] = summary["n_quase_unanimes"] - summary["esperado_binomial"]
    return summary


def _municipio_leader(eligible: pd.DataFrame) -> pd.DataFrame:
    totals = eligible.groupby(MUNICIPIO_KEYS, observed=True).agg(
        votos_nominais_mun=("votos_nominais", "sum")
    )
    by_candidate = (
        eligible.groupby(MUNICIPIO_KEYS + ["nr_votavel_top1"], observed=True)["votos_top1"].sum().reset_index()
    )
    leader = by_candidate.sort_values("votos_top1", ascending=False).drop_duplicates(MUNICIPIO_KEYS)
    leader = leader.merge(totals.reset_index(), on=MUNICIPIO_KEYS)
    leader["share_lider_mun"] = leader["votos_top1"] / leader["votos_nominais_mun"]
    return leader.rename(columns={"nr_votavel_top1": "nr_votavel_lider_mun"})[
        MUNICIPIO_KEYS + ["nr_votavel_lider_mun", "share_lider_mun"]
    ]
