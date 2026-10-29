from __future__ import annotations

import duckdb
import pandas as pd

from ..io import scan
from .constants import CD_CARGO_PRESIDENTE, SCOPE_NACIONAL, SCOPE_PRESIDENTE
from .timestamps import parse_tse_timestamp

SECTION_KEYS = ["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO"]
SECTION_COLUMNS = [
    *SECTION_KEYS, "NR_LOCAL_VOTACAO", "QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES",
    "QT_VOTOS_NOMINAIS", "QT_VOTOS_BRANCOS", "QT_VOTOS_NULOS", "DT_RECEBIMENTO_BU_HOR_TSE",
    "DT_PRIM_TOT_PARCIAL_HOR_TSE", "DS_ORIGEM_VOTO", "ST_SECAO_INSTALADA", "ST_SECAO_ANULADA",
    "CD_MODELO_URNA", "DS_MODELO_URNA", "DT_GERACAO", "HH_GERACAO",
]
VOTAVEL_BRANCO_NULO_SQ = (-1, -3)


def load_sections(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    relation = scan("detalhe_votacao_secao", scope=SCOPE_PRESIDENTE, cargo=CD_CARGO_PRESIDENTE, conn=conn)
    frame = relation.project(", ".join(SECTION_COLUMNS)).df()
    frame["recebimento"] = parse_tse_timestamp(frame["DT_RECEBIMENTO_BU_HOR_TSE"])
    frame["prim_tot_parcial"] = parse_tse_timestamp(frame["DT_PRIM_TOT_PARCIAL_HOR_TSE"])
    return frame


def discover_finalists(conn: duckdb.DuckDBPyConnection, turno: int) -> pd.DataFrame:
    relation = scan("votacao_secao", scope=SCOPE_PRESIDENTE, turno=turno, cargo=CD_CARGO_PRESIDENTE, conn=conn)
    conn.register("inv_votacao_secao_finalistas", relation)
    return conn.execute(
        """
        SELECT NR_VOTAVEL, NM_VOTAVEL, SQ_CANDIDATO, SUM(QT_VOTOS) AS votos
        FROM inv_votacao_secao_finalistas
        WHERE TRY_CAST(SQ_CANDIDATO AS BIGINT) > 0
        GROUP BY ALL ORDER BY votos DESC
        """
    ).df()


def load_section_votes(conn: duckdb.DuckDBPyConnection, turno: int, finalists: list[int]) -> pd.DataFrame:
    relation = scan("votacao_secao", scope=SCOPE_PRESIDENTE, turno=turno, cargo=CD_CARGO_PRESIDENTE, conn=conn)
    conn.register("inv_votacao_secao", relation)
    pivot = ", ".join(f"SUM(CASE WHEN NR_VOTAVEL = {n} THEN QT_VOTOS ELSE 0 END) AS votos_{n}" for n in finalists)
    return conn.execute(
        f"""
        SELECT SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO, {pivot},
               SUM(QT_VOTOS) AS votos_total_secao, COUNT(*) AS n_linhas
        FROM inv_votacao_secao GROUP BY ALL
        """
    ).df()


def load_votacao_secao_keys(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    relation = scan("votacao_secao", scope=SCOPE_PRESIDENTE, cargo=CD_CARGO_PRESIDENTE, conn=conn)
    conn.register("inv_votacao_secao_keys", relation)
    return conn.execute(
        """
        SELECT NR_TURNO, SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO, COUNT(*) AS n_linhas,
               COUNT(*) - COUNT(DISTINCT NR_VOTAVEL) AS n_votaveis_repetidos
        FROM inv_votacao_secao_keys GROUP BY ALL
        """
    ).df()


def load_munzona_totals(conn: duckdb.DuckDBPyConnection, turno: int) -> pd.DataFrame:
    relation = scan("detalhe_votacao_munzona", scope=SCOPE_NACIONAL, turno=turno, cargo=CD_CARGO_PRESIDENTE, conn=conn)
    conn.register("inv_munzona", relation)
    return conn.execute(
        """
        SELECT SUM(QT_SECOES_PRINCIPAIS) AS secoes_principais, SUM(QT_SECOES_AGREGADAS) AS secoes_agregadas,
               SUM(QT_SECOES_NAO_INSTALADAS) AS secoes_nao_instaladas, SUM(QT_TOTAL_SECOES) AS total_secoes,
               SUM(QT_APTOS) AS aptos, SUM(QT_COMPARECIMENTO) AS comparecimento,
               SUM(QT_VOTOS_NOMINAIS_VALIDOS) AS nominais_validos, SUM(QT_VOTOS_BRANCOS) AS brancos,
               SUM(QT_TOTAL_VOTOS_NULOS) AS total_nulos,
               MIN(STRPTIME(DT_ULTIMA_TOTALIZACAO || ' ' || HH_ULTIMA_TOTALIZACAO, '%d/%m/%Y %H:%M:%S')) AS ultima_tot_min,
               MAX(STRPTIME(DT_ULTIMA_TOTALIZACAO || ' ' || HH_ULTIMA_TOTALIZACAO, '%d/%m/%Y %H:%M:%S')) AS ultima_tot_max
        FROM inv_munzona
        """
    ).df()


def load_munzona_last_totalization(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    relation = scan("detalhe_votacao_munzona", scope=SCOPE_NACIONAL, cargo=CD_CARGO_PRESIDENTE, conn=conn)
    conn.register("inv_munzona_all", relation)
    return conn.execute(
        """
        SELECT NR_TURNO, SG_UF, CD_MUNICIPIO, NR_ZONA,
               STRPTIME(DT_ULTIMA_TOTALIZACAO || ' ' || HH_ULTIMA_TOTALIZACAO, '%d/%m/%Y %H:%M:%S') AS ultima_totalizacao
        FROM inv_munzona_all
        """
    ).df()


def load_candidate_munzona_totals(conn: duckdb.DuckDBPyConnection, turno: int) -> pd.DataFrame:
    relation = scan("votacao_candidato_munzona", scope=SCOPE_PRESIDENTE, turno=turno, cargo=CD_CARGO_PRESIDENTE, conn=conn)
    conn.register("inv_cand_munzona", relation)
    return conn.execute(
        "SELECT NR_CANDIDATO, SUM(QT_VOTOS_NOMINAIS) AS votos_nominais, SUM(QT_VOTOS_NOMINAIS_VALIDOS) AS votos_validos "
        "FROM inv_cand_munzona GROUP BY 1 ORDER BY votos_validos DESC"
    ).df()
