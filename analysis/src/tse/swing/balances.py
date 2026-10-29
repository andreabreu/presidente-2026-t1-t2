from __future__ import annotations

import numpy as np
import pandas as pd

from .constants import (
    DESTINO_ABSTENCAO,
    DESTINO_BRANCOS_NULOS,
    KEY_COLUMNS,
    ORIGEM_ABSTENCAO,
    ORIGEM_BRANCOS_NULOS,
    ORIGEM_OUTROS_ELIMINADOS,
    PORTE_BINS,
    PORTE_LABELS,
)
from .data import VOTE_T1_PREFIX, VOTE_T2_PREFIX, Contest

PERCENT = 100.0


def assign_porte(aptos: pd.Series, level: str) -> pd.Series:
    return pd.cut(aptos.fillna(0), bins=PORTE_BINS[level], labels=PORTE_LABELS[level], include_lowest=True).astype(str)


def origin_counts(wide: pd.DataFrame, contest: Contest) -> pd.DataFrame:
    aptos_ref = reference_aptos(wide)
    counts = {
        contest.origin_label(contest.finalist_a): wide[f"{VOTE_T1_PREFIX}{contest.finalist_a}"],
        contest.origin_label(contest.finalist_b): wide[f"{VOTE_T1_PREFIX}{contest.finalist_b}"],
    }
    for nr in contest.major_eliminated:
        counts[contest.origin_label(nr)] = wide[f"{VOTE_T1_PREFIX}{nr}"]
    counts[ORIGEM_OUTROS_ELIMINADOS] = wide[ORIGEM_OUTROS_ELIMINADOS]
    counts[ORIGEM_BRANCOS_NULOS] = wide["brancos_t1"] + wide["nulos_t1"]
    counts[ORIGEM_ABSTENCAO] = aptos_ref - wide["comp_t1"]
    return pd.DataFrame(counts).astype(float)


def destination_counts(wide: pd.DataFrame, contest: Contest) -> pd.DataFrame:
    aptos_ref = reference_aptos(wide)
    counts = {
        contest.destination_label(contest.finalist_a): wide[f"{VOTE_T2_PREFIX}{contest.finalist_a}"],
        contest.destination_label(contest.finalist_b): wide[f"{VOTE_T2_PREFIX}{contest.finalist_b}"],
        DESTINO_BRANCOS_NULOS: wide["brancos_t2"] + wide["nulos_t2"],
        DESTINO_ABSTENCAO: aptos_ref - wide["comp_t2"],
    }
    return pd.DataFrame(counts).astype(float)


def reference_aptos(wide: pd.DataFrame) -> pd.Series:
    return np.maximum(wide["aptos_t1"].fillna(0), wide["aptos_t2"].fillna(0)).astype(float)


def eliminated_votes(wide: pd.DataFrame, contest: Contest) -> pd.Series:
    present = [f"{VOTE_T1_PREFIX}{nr}" for nr in contest.eliminated if f"{VOTE_T1_PREFIX}{nr}" in wide]
    return wide[present].sum(axis=1).astype(float)


def residual_pool(wide: pd.DataFrame, contest: Contest) -> pd.Series:
    blank_null_drop = (wide["brancos_t1"] + wide["nulos_t1"]) - (wide["brancos_t2"] + wide["nulos_t2"])
    turnout_change = wide["comp_t2"] - wide["comp_t1"]
    return eliminated_votes(wide, contest) + blank_null_drop + turnout_change


def finalist_gain(wide: pd.DataFrame, nr: int) -> pd.Series:
    return wide[f"{VOTE_T2_PREFIX}{nr}"] - wide[f"{VOTE_T1_PREFIX}{nr}"]


def safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.div(denominator.where(denominator != 0, np.nan))


def build_balances(wide: pd.DataFrame, contest: Contest, level: str) -> pd.DataFrame:
    a, b = contest.finalist_a, contest.finalist_b
    both = wide[wide["presenca"] == "ambos"].copy()
    out = both[KEY_COLUMNS[level] + [c for c in ("nm_municipio",) if c in both]].copy()
    out["porte"] = assign_porte(both["aptos_t1"], level)
    for column in ("aptos", "comp", "brancos", "nulos"):
        out[f"{column}_t1"] = both[f"{column}_t1"]
        out[f"{column}_t2"] = both[f"{column}_t2"]
    out["delta_aptos"] = both["aptos_t2"] - both["aptos_t1"]
    out["taxa_comp_t1"] = safe_ratio(both["comp_t1"], both["aptos_t1"])
    out["taxa_comp_t2"] = safe_ratio(both["comp_t2"], both["aptos_t2"])
    out["delta_comp"] = both["comp_t2"] - both["comp_t1"]
    out["delta_comp_pp"] = (out["taxa_comp_t2"] - out["taxa_comp_t1"]) * PERCENT
    for nr in contest.eliminated:
        if f"{VOTE_T1_PREFIX}{nr}" in both:
            out[f"votos_t1_{nr}"] = both[f"{VOTE_T1_PREFIX}{nr}"]
    for label, nr in (("a", a), ("b", b)):
        out[f"finalista_{label}"] = nr
        out[f"votos_t1_{label}"] = both[f"{VOTE_T1_PREFIX}{nr}"]
        out[f"votos_t2_{label}"] = both[f"{VOTE_T2_PREFIX}{nr}"]
        out[f"delta_abs_{label}"] = finalist_gain(both, nr)
        out[f"delta_pct_{label}"] = safe_ratio(out[f"delta_abs_{label}"], both[f"{VOTE_T1_PREFIX}{nr}"]) * PERCENT
    out["votos_eliminados_t1"] = eliminated_votes(both, contest)
    out["delta_brancos_nulos"] = (both["brancos_t1"] + both["nulos_t1"]) - (both["brancos_t2"] + both["nulos_t2"])
    out["pool_residual"] = residual_pool(both, contest)
    out["identidade_ok"] = np.isclose(out["delta_abs_a"] + out["delta_abs_b"], out["pool_residual"])
    valid_t1 = both[f"{VOTE_T1_PREFIX}{a}"] + both[f"{VOTE_T1_PREFIX}{b}"]
    valid_t2 = both[f"{VOTE_T2_PREFIX}{a}"] + both[f"{VOTE_T2_PREFIX}{b}"]
    out["share_a_t1_dupla"] = safe_ratio(both[f"{VOTE_T1_PREFIX}{a}"], valid_t1)
    out["share_a_t2_valid"] = safe_ratio(both[f"{VOTE_T2_PREFIX}{a}"], valid_t2)
    out["delta_share_a_pp"] = (out["share_a_t2_valid"] - out["share_a_t1_dupla"]) * PERCENT
    return out.reset_index(drop=True)


def key_stability_summary(wide: pd.DataFrame) -> pd.DataFrame:
    frame = wide.assign(
        aptos_diferente=(wide["presenca"] == "ambos") & (wide["aptos_t1"] != wide["aptos_t2"]),
        abs_delta_aptos=(wide["aptos_t2"] - wide["aptos_t1"]).abs(),
    )
    summary = (
        frame.groupby("uf")
        .agg(
            n_unidades=("presenca", "size"),
            n_ambos=("presenca", lambda s: (s == "ambos").sum()),
            n_so_t1=("presenca", lambda s: (s == "so_t1").sum()),
            n_so_t2=("presenca", lambda s: (s == "so_t2").sum()),
            n_aptos_diferente=("aptos_diferente", "sum"),
            soma_abs_delta_aptos=("abs_delta_aptos", "sum"),
            max_abs_delta_aptos=("abs_delta_aptos", "max"),
            aptos_t1=("aptos_t1", "sum"),
            aptos_t2=("aptos_t2", "sum"),
        )
        .reset_index()
    )
    summary["pct_aptos_diferente"] = summary["n_aptos_diferente"] / summary["n_ambos"] * PERCENT
    return summary
