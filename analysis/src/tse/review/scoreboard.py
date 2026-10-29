from __future__ import annotations

import duckdb
import pandas as pd

from .constants import CARGO_PRESIDENTE, NR_VOTAVEL_BRANCO, NR_VOTAVEL_NULO, SCOPE_PRESIDENTE
from .loaders import query, source

PERCENT = 100.0


def scoreboard_from_votes(votes: pd.DataFrame, candidate_column: str, votes_column: str) -> pd.DataFrame:
    """votes: uma linha por (NR_TURNO, candidato) com total de votos nominais; devolve share e rank."""
    frame = votes.groupby(["NR_TURNO", candidate_column], as_index=False)[votes_column].sum()
    frame["validos"] = frame.groupby("NR_TURNO")[votes_column].transform("sum")
    frame["pct_validos"] = frame[votes_column] / frame["validos"] * PERCENT
    frame["rank"] = frame.groupby("NR_TURNO")[votes_column].rank(ascending=False, method="first").astype(int)
    return frame.sort_values(["NR_TURNO", "rank"]).reset_index(drop=True)


def margin_pp(scoreboard: pd.DataFrame, turno: int) -> float:
    top = scoreboard[(scoreboard.NR_TURNO == turno)].sort_values("rank").head(2)
    return float(top.pct_validos.iloc[0] - top.pct_validos.iloc[1])


def margin_votes(scoreboard: pd.DataFrame, turno: int, votes_column: str) -> int:
    top = scoreboard[(scoreboard.NR_TURNO == turno)].sort_values("rank").head(2)
    return int(top[votes_column].iloc[0] - top[votes_column].iloc[1])


def scoreboard_from_secao(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    votes = query(
        conn,
        f"""
        SELECT NR_TURNO, NR_VOTAVEL, SUM(QT_VOTOS) AS votos
        FROM {source("votacao_secao", SCOPE_PRESIDENTE)}
        WHERE CD_CARGO = {CARGO_PRESIDENTE} AND NR_VOTAVEL NOT IN ({NR_VOTAVEL_BRANCO}, {NR_VOTAVEL_NULO})
        GROUP BY ALL
        """,
    )
    return scoreboard_from_votes(votes, "NR_VOTAVEL", "votos")


def scoreboard_from_munzona(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    votes = query(
        conn,
        f"""
        SELECT NR_TURNO, NR_CANDIDATO, SUM(QT_VOTOS_NOMINAIS_VALIDOS) AS votos
        FROM {source("votacao_candidato_munzona", SCOPE_PRESIDENTE)}
        WHERE CD_CARGO = {CARGO_PRESIDENTE}
        GROUP BY ALL
        """,
    )
    return scoreboard_from_votes(votes, "NR_CANDIDATO", "votos")


def rate(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.where(denominator > 0) * PERCENT


def turnout_by_uf(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    frame = query(
        conn,
        f"""
        SELECT SG_UF, NR_TURNO, SUM(QT_APTOS) AS aptos, SUM(QT_COMPARECIMENTO) AS comparecimento,
               SUM(QT_ABSTENCOES) AS abstencoes, SUM(QT_VOTOS_BRANCOS) AS brancos, SUM(QT_TOTAL_VOTOS_NULOS) AS nulos
        FROM {source("detalhe_votacao_munzona", SCOPE_PRESIDENTE)}
        WHERE CD_CARGO = {CARGO_PRESIDENTE}
        GROUP BY ALL ORDER BY ALL
        """,
    )
    frame["taxa_comparecimento"] = rate(frame.comparecimento, frame.aptos)
    frame["taxa_abstencao"] = rate(frame.abstencoes, frame.aptos)
    return frame


def turnout_by_uf_from_sections(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    frame = query(
        conn,
        f"""
        SELECT SG_UF, NR_TURNO, SUM(QT_APTOS) AS aptos, SUM(QT_COMPARECIMENTO) AS comparecimento
        FROM {source("detalhe_votacao_secao", SCOPE_PRESIDENTE)}
        WHERE CD_CARGO = {CARGO_PRESIDENTE}
        GROUP BY ALL ORDER BY ALL
        """,
    )
    frame["taxa_comparecimento"] = rate(frame.comparecimento, frame.aptos)
    return frame


def national_turnout(frame: pd.DataFrame, exclude_uf: str | None = None) -> pd.DataFrame:
    subset = frame if exclude_uf is None else frame[frame.SG_UF != exclude_uf]
    totals = subset.groupby("NR_TURNO", as_index=False)[["aptos", "comparecimento"]].sum()
    totals["taxa_comparecimento"] = rate(totals.comparecimento, totals.aptos)
    return totals
