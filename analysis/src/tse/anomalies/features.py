from __future__ import annotations

import re

import duckdb
import pandas as pd

from tse.io import scan

CARGO_PRESIDENTE = 1
CARGO_DEPUTADO_FEDERAL = 6
SCOPE_PRESIDENTE = "BR"
PROPORTIONAL_SCOPES = ("SP", "MG", "RJ")
BLANK_CODE_NAME = "VOTO BRANCO"
NULL_CODE_NAME = "VOTO NULO"
SECTION_KEYS = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO"]


def discover_special_codes(conn: duckdb.DuckDBPyConnection, scope: str, cargo: int) -> dict[str, int]:
    votes = scan("votacao_secao", scope=scope, cargo=cargo, conn=conn)
    rows = conn.sql(
        f"SELECT DISTINCT NR_VOTAVEL, NM_VOTAVEL FROM votes "
        f"WHERE NM_VOTAVEL IN ('{BLANK_CODE_NAME}', '{NULL_CODE_NAME}')"
    ).fetchall()
    codes = {name: int(code) for code, name in rows}
    if set(codes) != {BLANK_CODE_NAME, NULL_CODE_NAME}:
        raise ValueError(f"códigos de branco/nulo não encontrados em {scope}/{cargo}: {codes}")
    return {"branco": codes[BLANK_CODE_NAME], "nulo": codes[NULL_CODE_NAME]}


def section_detail(conn: duckdb.DuckDBPyConnection, scope: str, cargo: int, turno: int | None = None) -> pd.DataFrame:
    detail = scan("detalhe_votacao_secao", scope=scope, cargo=cargo, turno=turno, conn=conn)
    return conn.sql(
        """
        SELECT SG_UF, CD_MUNICIPIO, NM_MUNICIPIO, NR_ZONA, NR_SECAO, NR_TURNO, CD_CARGO,
               QT_APTOS, QT_COMPARECIMENTO, QT_ABSTENCOES, QT_VOTOS_NOMINAIS, QT_VOTOS_BRANCOS,
               QT_VOTOS_NULOS, QT_VOTOS_LEGENDA, QT_VOTOS_ANULADOS_APU_SEP,
               NR_LOCAL_VOTACAO, NM_LOCAL_VOTACAO, ST_SECAO_INSTALADA, ST_SECAO_ANULADA,
               DS_ORIGEM_VOTO, CD_MODELO_URNA
        FROM detail
        """
    ).df()


def section_candidate_summary(
    conn: duckdb.DuckDBPyConnection, scope: str, cargo: int, codes: dict[str, int], turno: int | None = None
) -> pd.DataFrame:
    votes = scan("votacao_secao", scope=scope, cargo=cargo, turno=turno, conn=conn)
    special = f"({codes['branco']}, {codes['nulo']})"
    return conn.sql(
        f"""
        WITH nominal AS (
            SELECT SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO, NR_TURNO, NR_VOTAVEL, QT_VOTOS
            FROM votes WHERE NR_VOTAVEL NOT IN {special}
        ),
        ranked AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO, NR_TURNO
                ORDER BY QT_VOTOS DESC, NR_VOTAVEL) AS posicao
            FROM nominal
        )
        SELECT SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO, NR_TURNO,
               SUM(QT_VOTOS) AS votos_nominais,
               MAX(CASE WHEN posicao = 1 THEN QT_VOTOS END) AS votos_top1,
               MAX(CASE WHEN posicao = 1 THEN NR_VOTAVEL END) AS nr_votavel_top1,
               COALESCE(MAX(CASE WHEN posicao = 2 THEN QT_VOTOS END), 0) AS votos_top2
        FROM ranked
        GROUP BY ALL
        """
    ).df()


def candidate_votes_long(
    conn: duckdb.DuckDBPyConnection, scope: str, cargo: int, codes: dict[str, int], min_votes: int
) -> pd.DataFrame:
    votes = scan("votacao_secao", scope=scope, cargo=cargo, conn=conn)
    special = f"({codes['branco']}, {codes['nulo']})"
    return conn.sql(
        f"""
        SELECT SG_UF, NR_TURNO, NR_VOTAVEL, NM_VOTAVEL, QT_VOTOS
        FROM votes WHERE NR_VOTAVEL NOT IN {special} AND QT_VOTOS >= {int(min_votes)}
        """
    ).df()


def section_vote_vectors(
    conn: duckdb.DuckDBPyConnection, scope: str, cargo: int, turno: int, min_comparecimento: int
) -> pd.DataFrame:
    votes = scan("votacao_secao", scope=scope, cargo=cargo, turno=turno, conn=conn)
    detail = scan("detalhe_votacao_secao", scope=scope, cargo=cargo, turno=turno, conn=conn)
    return conn.sql(
        f"""
        WITH eligible AS (
            SELECT SG_UF, CD_MUNICIPIO, NM_MUNICIPIO, NR_ZONA, NR_SECAO, NR_TURNO, QT_COMPARECIMENTO
            FROM detail WHERE QT_COMPARECIMENTO >= {int(min_comparecimento)}
        ),
        vectors AS (
            SELECT CD_MUNICIPIO, NR_ZONA, NR_SECAO, NR_TURNO,
                   STRING_AGG(NR_VOTAVEL || ':' || QT_VOTOS, ';' ORDER BY NR_VOTAVEL) AS vetor
            FROM votes GROUP BY ALL
        )
        SELECT e.*, v.vetor
        FROM eligible e JOIN vectors v USING (CD_MUNICIPIO, NR_ZONA, NR_SECAO, NR_TURNO)
        """
    ).df()


def votes_wide_for_municipio(
    conn: duckdb.DuckDBPyConnection, scope: str, cargo: int, turno: int, min_comparecimento: int
) -> pd.DataFrame:
    votes = scan("votacao_secao", scope=scope, cargo=cargo, turno=turno, conn=conn)
    detail = scan("detalhe_votacao_secao", scope=scope, cargo=cargo, turno=turno, conn=conn)
    return conn.sql(
        f"""
        WITH eligible AS (
            SELECT CD_MUNICIPIO, NR_ZONA, NR_SECAO FROM detail
            WHERE QT_COMPARECIMENTO >= {int(min_comparecimento)}
        )
        SELECT v.CD_MUNICIPIO, v.NR_ZONA, v.NR_SECAO, v.NR_VOTAVEL, v.QT_VOTOS
        FROM votes v JOIN eligible USING (CD_MUNICIPIO, NR_ZONA, NR_SECAO)
        """
    ).df()


def zone_aggregated_sections(conn: duckdb.DuckDBPyConnection, scope: str, cargo: int) -> pd.DataFrame:
    munzona = scan("detalhe_votacao_munzona", scope=scope, cargo=cargo, conn=conn)
    return conn.sql(
        """
        SELECT CD_MUNICIPIO, NR_ZONA, NR_TURNO, QT_SECOES_AGREGADAS, QT_SECOES_NAO_INSTALADAS,
               ST_VOTO_EM_TRANSITO
        FROM munzona
        """
    ).df()


def special_place_mask(names: pd.Series, pattern: str) -> pd.Series:
    regex = re.compile(pattern, flags=re.IGNORECASE)
    return names.fillna("").map(lambda value: bool(regex.search(value)))


def candidate_votes_by_municipio(
    conn: duckdb.DuckDBPyConnection, scope: str, cargo: int, codes: dict[str, int]
) -> pd.DataFrame:
    votes = scan("votacao_secao", scope=scope, cargo=cargo, conn=conn)
    special = f"({codes['branco']}, {codes['nulo']})"
    return conn.sql(
        f"""
        SELECT SG_UF, CD_MUNICIPIO, NR_TURNO, NR_VOTAVEL, SUM(QT_VOTOS) AS votos
        FROM votes WHERE NR_VOTAVEL NOT IN {special}
        GROUP BY ALL
        """
    ).df()


def section_votes_for_candidate(
    conn: duckdb.DuckDBPyConnection, scope: str, cargo: int, turno: int, nr_votavel: int
) -> pd.DataFrame:
    votes = scan("votacao_secao", scope=scope, cargo=cargo, turno=turno, conn=conn)
    return conn.sql(
        f"""
        SELECT SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO, NR_TURNO, QT_VOTOS AS votos_vencedor
        FROM votes WHERE NR_VOTAVEL = {int(nr_votavel)}
        """
    ).df()
