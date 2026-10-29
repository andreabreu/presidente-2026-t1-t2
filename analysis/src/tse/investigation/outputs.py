from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from ..config import ANALYSIS_ROOT
from ..tables import write_figure, write_table
from .analysis import EVENT_PRIM_TOT, EVENT_RECEBIMENTO, LEVEL_NACIONAL, LEVEL_UF, NATIONAL_LABEL
from .constants import ELECTION_DATES, HYPOTHESIS_IDS, SCRIPT, TABLE_PREFIX, TURNOS

FLOW_PATH = ANALYSIS_ROOT / "investigation" / "data" / "flow_bu.json"
FIGURE_WINDOW = ("17:00", "23:59")
COMMON_CAVEATS = [
    "DT_RECEBIMENTO_BU_HOR_TSE é o carimbo de recepção do BU no TSE (hora de Brasília, conforme leiame); não é o horário de encerramento da urna nem o horário de votação.",
    "DT_PRIM_TOT_PARCIAL_HOR_TSE é a primeira totalização parcial do BU; retotalizações posteriores não aparecem por seção.",
    "Linhas com DS_ORIGEM_VOTO = Totalização (seções não instaladas, ZZ) têm carimbo mas comparecimento zero; excluídas dos cálculos de janela.",
    "Comparações entre turnos são entre fotografias distintas de arquivos (ver val_timestamps_geracao).",
]


def table_id(name: str) -> str:
    return f"{TABLE_PREFIX}{name}"


def save_table(name: str, frame: pd.DataFrame, title: str, description: str, unit: str, columns: dict[str, str],
               method: str, caveats: list[str] | None = None) -> Path:
    return write_table(frame, table_id(name), title_pt=title, description_pt=description, script=SCRIPT,
                       hypothesis_ids=HYPOTHESIS_IDS, unit=unit, columns=columns, method=method,
                       caveats_pt=[*COMMON_CAVEATS, *(caveats or [])])


def _minute_series(minutes: pd.DataFrame, event: str, turno: int) -> pd.DataFrame:
    date = ELECTION_DATES[turno]
    start, end = (pd.Timestamp(f"{date} {clock}") for clock in FIGURE_WINDOW)
    part = minutes[(minutes["evento"] == event) & (minutes["nivel"] == LEVEL_NACIONAL) & (minutes["NR_TURNO"] == turno)]
    part = part[(part["minuto"] >= start) & (part["minuto"] <= end)]
    grid = pd.DataFrame({"minuto": pd.date_range(start, end, freq="min")})
    series = grid.merge(part[["minuto", "n_secoes"]], on="minuto", how="left").fillna({"n_secoes": 0})
    series["hora"] = series["minuto"].dt.strftime("%H:%M")
    return series


def minute_figure(minutes: pd.DataFrame, event: str, title: str) -> go.Figure:
    figure = go.Figure()
    for turno in TURNOS:
        series = _minute_series(minutes, event, turno)
        figure.add_trace(go.Scatter(x=series["hora"], y=series["n_secoes"], mode="lines",
                                    name=f"Turno {turno} ({ELECTION_DATES[turno]})"))
    figure.update_layout(title=title, xaxis_title="Hora de Brasília (minuto)", yaxis_title="Seções por minuto",
                         legend_title="Turno", hovermode="x unified")
    return figure


def lag_histogram(merged_lags: pd.DataFrame) -> go.Figure:
    figure = go.Figure()
    for turno in TURNOS:
        part = merged_lags[merged_lags["NR_TURNO"] == turno]["lag_s"].dropna()
        figure.add_trace(go.Histogram(x=part.clip(upper=1800), name=f"Turno {turno}", opacity=0.6, xbins={"size": 15}))
    figure.update_layout(title="Lag primeira totalização parcial − recepção do BU (segundos, truncado em 1800)",
                         xaxis_title="segundos", yaxis_title="seções", barmode="overlay")
    return figure


def post17_by_uf_figure(post17: pd.DataFrame) -> go.Figure:
    part = post17[(post17["nivel"] == LEVEL_UF)]
    figure = go.Figure()
    for turno in TURNOS:
        subset = part[part["NR_TURNO"] == turno].pivot_table(index="SG_UF", columns="banda", values="n_secoes", aggfunc="sum").fillna(0)
        share_after_19 = (subset.get("19h00_20h00", 0) + subset.get("apos_20h", 0)) / subset.sum(axis=1)
        figure.add_trace(go.Bar(x=share_after_19.index, y=share_after_19.values, name=f"Turno {turno}"))
    figure.update_layout(title="Participação de seções com BU recebido após 19h00 (hora TSE), por UF",
                         xaxis_title="UF", yaxis_title="share de seções", barmode="group")
    return figure


def write_figures(minutes: pd.DataFrame, merged_lags: pd.DataFrame, post17: pd.DataFrame) -> list[Path]:
    return [
        write_figure(minute_figure(minutes, EVENT_RECEBIMENTO, "BUs recebidos por minuto (hora TSE), 1º vs 2º turno"),
                     "inv_recebimento_por_minuto_t1_vs_t2"),
        write_figure(minute_figure(minutes, EVENT_PRIM_TOT, "Primeira totalização parcial por minuto (hora TSE), 1º vs 2º turno"),
                     "inv_totalizacao_por_minuto"),
        write_figure(lag_histogram(merged_lags), "inv_lag_hist"),
        write_figure(post17_by_uf_figure(post17), "inv_pos17h_por_uf"),
    ]


def write_flow_spec(empirical: dict) -> Path:
    FLOW_PATH.parent.mkdir(parents=True, exist_ok=True)
    spec = {"generated_at": datetime.now(timezone.utc).isoformat(), "script": SCRIPT, "status_legend": {
        "confirmado": "documentado publicamente (leiame/resolução/página TSE) e/ou observado nos dados",
        "inferido": "inferido a partir dos dados abertos ou de descrições gerais",
        "nao_confirmado": "sem documentação técnica pública acessível nesta análise"},
        "nodes": flow_nodes(empirical), "edges": flow_edges()}
    FLOW_PATH.write_text(json.dumps(spec, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return FLOW_PATH


def flow_nodes(empirical: dict) -> list[dict]:
    return [
        {"id": "urna_encerramento", "label": "Urna: encerramento da votação e emissão do BU", "status": "confirmado",
         "timestamp_available": "não nos CSVs (está no BU/log da urna: bweb_*, logjez)", "source": "Res. TSE 23.603/2019; leiame"},
        {"id": "midia_resultado", "label": "Mídia de resultado (assinada/cifrada) retirada da urna", "status": "confirmado",
         "timestamp_available": "não", "source": "Res. TSE 23.603/2019; Folhapress 07/10/2026"},
        {"id": "transportador", "label": "Transportador de Arquivos / JE-Connect (transmissão pela rede privada da JE)", "status": "confirmado",
         "timestamp_available": "não público (log do Transportador)", "source": "Res. TSE 23.603/2019"},
        {"id": "recepcao_tse", "label": "Receptor de Arquivos (RecArquivos) no TSE: DT_RECEBIMENTO_BU_HOR_TSE", "status": "confirmado",
         "timestamp_available": "sim, por seção", "empirical": empirical.get("recepcao")},
        {"id": "validacao", "label": "Validação de assinatura digital e correspondência urna×seção", "status": "inferido",
         "timestamp_available": "não", "source": "descrições gerais; correspondências esperadas/efetivadas (dataset público)"},
        {"id": "armazenamento", "label": "Armazenamento do BU no banco de totalização (SisTot/Gerenciador de Dados)", "status": "nao_confirmado",
         "timestamp_available": "não"},
        {"id": "totalizacao", "label": "Totalização parcial: DT_PRIM_TOT_PARCIAL_HOR_TSE (seção) e DT/HH_ULTIMA_TOTALIZACAO (mun/zona)", "status": "confirmado",
         "timestamp_available": "sim", "empirical": empirical.get("totalizacao")},
        {"id": "divulgacao", "label": "Divulgação (Divulga / resultados.tse.jus.br)", "status": "inferido",
         "timestamp_available": "não nos CSVs (snapshots do painel)"},
        {"id": "dados_abertos", "label": "Exportação para dados abertos (DT/HH_GERACAO)", "status": "confirmado",
         "timestamp_available": "sim, por arquivo"},
    ]


def flow_edges() -> list[dict]:
    chain = ["urna_encerramento", "midia_resultado", "transportador", "recepcao_tse", "validacao", "armazenamento",
             "totalizacao", "divulgacao", "dados_abertos"]
    statuses = ["confirmado", "confirmado", "confirmado", "inferido", "inferido", "inferido", "inferido", "confirmado"]
    return [{"from": a, "to": b, "status": s} for a, b, s in zip(chain[:-1], chain[1:], statuses)]
