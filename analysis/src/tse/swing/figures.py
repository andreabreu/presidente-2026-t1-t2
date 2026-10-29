from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

PERCENT = 100.0
FACET_COLUMNS = 6


def write_figure(figure: go.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_json(str(path))


def residual_histogram(flags: pd.DataFrame, title: str) -> go.Figure:
    figure = go.Figure(go.Histogram(x=flags["residuo_student"], nbinsx=120, name="resíduo studentizado"))
    figure.update_layout(title=title, xaxis_title="resíduo studentizado", yaxis_title="unidades", bargap=0.02)
    return figure


def scatter_by_uf(balances: pd.DataFrame, title: str) -> go.Figure:
    ufs = sorted(balances["uf"].dropna().unique())
    rows = int(np.ceil(len(ufs) / FACET_COLUMNS))
    figure = make_subplots(rows=rows, cols=FACET_COLUMNS, subplot_titles=ufs, shared_xaxes=True, shared_yaxes=True)
    for index, uf in enumerate(ufs):
        row, col = divmod(index, FACET_COLUMNS)
        subset = balances[balances["uf"] == uf].dropna(subset=["share_a_t1_dupla", "share_a_t2_valid"])
        x = subset["share_a_t1_dupla"] * PERCENT
        y = subset["share_a_t2_valid"] * PERCENT
        figure.add_trace(
            go.Scattergl(x=x, y=y, mode="markers", marker=dict(size=4, opacity=0.5), name=uf, showlegend=False,
                         text=subset.get("nm_municipio"), hovertemplate="%{text}<br>T1 %{x:.1f}% → T2 %{y:.1f}%"),
            row=row + 1, col=col + 1,
        )
        if len(subset) >= 2:
            slope, intercept = np.polyfit(x, y, 1, w=np.sqrt(subset["comp_t2"]))
            grid = np.linspace(x.min(), x.max(), 20)
            figure.add_trace(go.Scatter(x=grid, y=slope * grid + intercept, mode="lines", line=dict(color="black", width=1), showlegend=False), row=row + 1, col=col + 1)
    figure.update_layout(title=title, height=260 * rows, width=1400)
    return figure


def flow_sankey(flow: pd.DataFrame, title: str) -> go.Figure:
    origins = list(dict.fromkeys(flow["origem"]))
    destinations = list(dict.fromkeys(flow["destino"]))
    labels = origins + destinations
    index = {label: i for i, label in enumerate(labels)}
    hover = [
        f"{r.origem} → {r.destino}<br>estimativa {r.estimativa:.3f} [IC {r.ci_low:.3f}; {r.ci_high:.3f}]"
        f"<br>bounds [{r.bound_low:.3f}; {r.bound_high:.3f}]"
        for r in flow.itertuples()
    ]
    figure = go.Figure(
        go.Sankey(
            node=dict(label=labels, pad=15, thickness=16),
            link=dict(
                source=[index[o] for o in flow["origem"]],
                target=[index[d] for d in flow["destino"]],
                value=flow["votos_estimados"].clip(lower=0),
                customdata=hover,
                hovertemplate="%{customdata}<extra></extra>",
            ),
        )
    )
    figure.update_layout(title=title)
    return figure
