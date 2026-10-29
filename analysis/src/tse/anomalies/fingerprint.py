from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats as scipy_stats

from tse.anomalies.stats import bimodality_coefficient

SUBPLOT_COLUMNS = 6


def national_winner(sections: pd.DataFrame) -> dict[int, int]:
    winners = {}
    for turno, group in sections.groupby("NR_TURNO"):
        totals = group.groupby("nr_votavel_top1")["votos_top1"].sum()
        winners[int(turno)] = int(totals.idxmax())
    return winners


def fingerprint_stats(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (uf, turno), group in frame.groupby(["SG_UF", "NR_TURNO"], observed=True):
        turnout = group["taxa_comparecimento"].to_numpy()
        share = group["share_vencedor"].to_numpy()
        rows.append(
            {
                "SG_UF": uf,
                "NR_TURNO": turno,
                "n_secoes": len(group),
                "comparecimento_media": float(np.nanmean(turnout)),
                "comparecimento_curtose_excesso": float(scipy_stats.kurtosis(turnout, nan_policy="omit")),
                "comparecimento_bimodalidade": bimodality_coefficient(turnout),
                "share_vencedor_media": float(np.nanmean(share)),
                "share_vencedor_curtose_excesso": float(scipy_stats.kurtosis(share, nan_policy="omit")),
                "share_vencedor_bimodalidade": bimodality_coefficient(share),
                "correlacao_spearman": float(scipy_stats.spearmanr(turnout, share, nan_policy="omit").statistic),
                "frac_canto_superior": float(np.nanmean((turnout > 0.95) & (share > 0.95))),
            }
        )
    return pd.DataFrame(rows)


def write_fingerprint_figure(frame: pd.DataFrame, turno: int, bins: int, path: Path) -> None:
    ufs = sorted(frame["SG_UF"].unique())
    rows = int(np.ceil(len(ufs) / SUBPLOT_COLUMNS))
    figure = make_subplots(rows=rows, cols=SUBPLOT_COLUMNS, subplot_titles=ufs)
    edges = np.linspace(0, 1, bins + 1)
    for position, uf in enumerate(ufs):
        group = frame[frame["SG_UF"] == uf]
        histogram, _, _ = np.histogram2d(
            group["taxa_comparecimento"].clip(0, 1), group["share_vencedor"].clip(0, 1), bins=[edges, edges]
        )
        figure.add_trace(
            go.Heatmap(z=np.log1p(histogram.T), x=edges, y=edges, showscale=False, colorscale="Viridis"),
            row=position // SUBPLOT_COLUMNS + 1,
            col=position % SUBPLOT_COLUMNS + 1,
        )
    figure.update_layout(
        title=f"Impressão digital comparecimento × share do vencedor por UF — turno {turno} (log1p contagem de seções)",
        height=260 * rows,
    )
    path.write_text(json.dumps(figure.to_plotly_json(), default=_json_default), encoding="utf-8")


def _json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    raise TypeError(type(value))
