from __future__ import annotations

import duckdb
import pandas as pd

from .constants import CARGO_SENADOR, SENADOR_VOTOS_POR_ELEITOR, UM_VOTO
from .loaders import OTHER_CARGOS_NATIONAL_FILTER, OTHER_CARGOS_UF_FILTER, PRESIDENT_FILTER, query, source

COUNT_COLUMNS_MUNZONA = [
    "QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES", "QT_VOTOS", "QT_TOTAL_VOTOS_VALIDOS", "QT_VOTOS_BRANCOS",
    "QT_TOTAL_VOTOS_NULOS", "QT_VOTOS_NULOS", "QT_VOTOS_NULOS_TECNICOS", "QT_TOTAL_SECOES",
]
COUNT_COLUMNS_SECAO = [
    "QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES", "QT_VOTOS_NOMINAIS", "QT_VOTOS_BRANCOS", "QT_VOTOS_NULOS",
    "QT_VOTOS_LEGENDA",
]
KEY_SECAO = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO"]
KEY_MUNZONA = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_TURNO"]


def votes_per_voter(cd_cargo: int) -> int:
    return SENADOR_VOTOS_POR_ELEITOR if cd_cargo == CARGO_SENADOR else UM_VOTO


def votes_per_voter_sql() -> str:
    return f"CASE WHEN CD_CARGO = {CARGO_SENADOR} THEN {SENADOR_VOTOS_POR_ELEITOR} ELSE {UM_VOTO} END"


def violation_share(n_violations: int, n_rows: int) -> float:
    return n_violations / n_rows if n_rows else float("nan")


def section_identity_counts(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    seats = votes_per_voter_sql()
    return query(
        conn,
        f"""
        WITH s AS (
            SELECT * FROM {source("detalhe_votacao_secao")}
            WHERE ({PRESIDENT_FILTER}) OR ({OTHER_CARGOS_UF_FILTER})
        )
        SELECT CD_CARGO, COUNT(*) AS n_rows,
               SUM((QT_APTOS <> QT_COMPARECIMENTO + QT_ABSTENCOES)::INT) AS v_aptos,
               SUM((QT_COMPARECIMENTO <> QT_VOTOS_NOMINAIS + QT_VOTOS_LEGENDA + QT_VOTOS_BRANCOS + QT_VOTOS_NULOS)::INT) AS v_comp_um_voto,
               SUM((QT_COMPARECIMENTO * ({seats}) <> QT_VOTOS_NOMINAIS + QT_VOTOS_LEGENDA + QT_VOTOS_BRANCOS + QT_VOTOS_NULOS + QT_VOTOS_ANULADOS_APU_SEP)::INT) AS v_comp_votos_por_eleitor,
               SUM((QT_COMPARECIMENTO > QT_APTOS)::INT) AS v_comp_maior_aptos,
               SUM((QT_APTOS <> QT_COMPARECIMENTO + QT_ABSTENCOES AND ST_SECAO_INSTALADA <> 'Sim')::INT) AS v_aptos_nao_instalada,
               SUM((QT_APTOS <> QT_COMPARECIMENTO + QT_ABSTENCOES AND SG_UF = 'ZZ')::INT) AS v_aptos_zz
        FROM s GROUP BY ALL ORDER BY ALL
        """,
    )


def munzona_identity_counts(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    seats = votes_per_voter_sql()
    return query(
        conn,
        f"""
        WITH m AS (
            SELECT * FROM {source("detalhe_votacao_munzona")}
            WHERE ({PRESIDENT_FILTER}) OR ({OTHER_CARGOS_NATIONAL_FILTER})
        )
        SELECT CD_CARGO, COUNT(*) AS n_rows,
               SUM((QT_APTOS <> QT_COMPARECIMENTO + QT_ABSTENCOES + QT_ELEITORES_SECOES_NAO_INSTALADAS)::INT) AS v_aptos_nao_instaladas,
               SUM((QT_COMPARECIMENTO * ({seats}) <> QT_VOTOS)::INT) AS v_comp_votos,
               SUM((QT_VOTOS <> QT_TOTAL_VOTOS_VALIDOS + QT_VOTOS_BRANCOS + QT_TOTAL_VOTOS_NULOS + QT_TOTAL_VOTOS_ANULADOS + QT_TOTAL_VOTOS_ANUL_SUBJUD + QT_VOTOS_ANULADOS_APU_SEP)::INT) AS v_votos_decomp,
               SUM((QT_TOTAL_VOTOS_NULOS <> QT_VOTOS_NULOS + QT_VOTOS_NULOS_TECNICOS)::INT) AS v_nulos_tecnicos,
               SUM(QT_VOTOS_NULOS_TECNICOS) AS nulos_tecnicos, SUM(QT_VOTOS) AS votos, SUM(QT_COMPARECIMENTO) AS comparecimento
        FROM m GROUP BY ALL ORDER BY ALL
        """,
    )


def technical_null_explanation(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Nulos técnicos (Presidente) = votos em votacao_secao de votável ausente em votacao_candidato_munzona."""
    return query(
        conn,
        f"""
        WITH sec AS (
            SELECT SG_UF, CD_MUNICIPIO, NR_ZONA, NR_TURNO, NR_VOTAVEL, SUM(QT_VOTOS) AS votos
            FROM {source("votacao_secao", "BR")} WHERE CD_CARGO = 1 AND NR_VOTAVEL NOT IN (95, 96) GROUP BY ALL
        ),
        cand AS (
            SELECT DISTINCT NR_TURNO, NR_CANDIDATO FROM {source("votacao_candidato_munzona", "BR")} WHERE CD_CARGO = 1
        ),
        ausentes AS (
            SELECT s.SG_UF, s.CD_MUNICIPIO, s.NR_ZONA, s.NR_TURNO, SUM(s.votos) AS votos_sem_candidato
            FROM sec s LEFT JOIN cand c ON c.NR_TURNO = s.NR_TURNO AND c.NR_CANDIDATO = s.NR_VOTAVEL
            WHERE c.NR_CANDIDATO IS NULL GROUP BY ALL
        ),
        det AS (
            SELECT SG_UF, CD_MUNICIPIO, NR_ZONA, NR_TURNO, QT_VOTOS_NULOS_TECNICOS
            FROM {source("detalhe_votacao_munzona", "BR")} WHERE CD_CARGO = 1
        )
        SELECT d.NR_TURNO, COUNT(*) AS n_zonas, SUM(d.QT_VOTOS_NULOS_TECNICOS) AS nulos_tecnicos,
               SUM(COALESCE(a.votos_sem_candidato, 0)) AS votos_votavel_sem_candidato,
               SUM((d.QT_VOTOS_NULOS_TECNICOS <> COALESCE(a.votos_sem_candidato, 0))::INT) AS n_zonas_divergentes
        FROM det d LEFT JOIN a USING (SG_UF, CD_MUNICIPIO, NR_ZONA, NR_TURNO)
        GROUP BY ALL ORDER BY ALL
        """.replace("LEFT JOIN a USING", "LEFT JOIN ausentes a USING"),
    )


def _row_equality_sql(dataset: str, key: list[str], columns: list[str], cargo_filter: str) -> str:
    key_sql = ", ".join(key)
    diff_sql = " OR ".join(f"l.{column} IS DISTINCT FROM r.{column}" for column in columns)
    return f"""
        WITH l AS (SELECT * FROM {source(dataset, "BR")} WHERE {cargo_filter}),
             r AS (SELECT * FROM {source(dataset, "BRASIL")} WHERE {cargo_filter})
        SELECT
            (SELECT COUNT(*) FROM l) AS n_br,
            (SELECT COUNT(*) FROM r) AS n_brasil,
            (SELECT COUNT(*) FROM l ANTI JOIN r USING ({key_sql})) AS so_br,
            (SELECT COUNT(*) FROM r ANTI JOIN l USING ({key_sql})) AS so_brasil,
            (SELECT COUNT(*) FROM l JOIN r USING ({key_sql}) WHERE {diff_sql}) AS n_linhas_divergentes
    """


def br_vs_brasil_row_equality(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    checks = {
        "detalhe_votacao_secao": (KEY_SECAO, COUNT_COLUMNS_SECAO, "CD_CARGO = 1"),
        "detalhe_votacao_munzona": (KEY_MUNZONA, COUNT_COLUMNS_MUNZONA, "CD_CARGO = 1"),
        "votacao_candidato_munzona": (KEY_MUNZONA + ["SQ_CANDIDATO"], ["QT_VOTOS_NOMINAIS", "QT_VOTOS_NOMINAIS_VALIDOS"], "CD_CARGO = 1"),
    }
    frames = []
    for dataset, (key, columns, cargo_filter) in checks.items():
        frame = query(conn, _row_equality_sql(dataset, key, columns, cargo_filter))
        frames.append(frame.assign(dataset=dataset, n_colunas_comparadas=len(columns)))
    return pd.concat(frames, ignore_index=True)


def secao_br_vs_brasil_other_cargos(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Para cargos não presidenciais, detalhe_votacao_secao em UF deve coincidir com BRASIL."""
    key_sql = ", ".join(KEY_SECAO + ["CD_CARGO"])
    diff_sql = " OR ".join(f"l.{column} IS DISTINCT FROM r.{column}" for column in COUNT_COLUMNS_SECAO)
    return query(
        conn,
        f"""
        WITH l AS (SELECT * FROM {source("detalhe_votacao_secao")} WHERE {OTHER_CARGOS_UF_FILTER}),
             r AS (SELECT * FROM {source("detalhe_votacao_secao", "BRASIL")} WHERE CD_CARGO <> 1)
        SELECT (SELECT COUNT(*) FROM l) AS n_uf, (SELECT COUNT(*) FROM r) AS n_brasil,
               (SELECT COUNT(*) FROM l ANTI JOIN r USING ({key_sql})) AS so_uf,
               (SELECT COUNT(*) FROM r ANTI JOIN l USING ({key_sql})) AS so_brasil,
               (SELECT COUNT(*) FROM l JOIN r USING ({key_sql}) WHERE {diff_sql}) AS n_linhas_divergentes
        """,
    )
