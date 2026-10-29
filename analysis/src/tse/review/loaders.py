from __future__ import annotations

import duckdb
import pandas as pd

from tse.io import parquet_glob

from .constants import CARGO_PRESIDENTE, NR_VOTAVEL_BRANCO, NR_VOTAVEL_NULO, SCOPE_PRESIDENTE

PRESIDENT_FILTER = f"scope = '{SCOPE_PRESIDENTE}' AND CD_CARGO = {CARGO_PRESIDENTE}"
OTHER_CARGOS_UF_FILTER = f"scope NOT IN ('BR', 'BRASIL') AND CD_CARGO <> {CARGO_PRESIDENTE}"
OTHER_CARGOS_NATIONAL_FILTER = f"scope = 'BRASIL' AND CD_CARGO <> {CARGO_PRESIDENTE}"


def source(dataset: str, scope: str | None = None) -> str:
    return f"read_parquet('{parquet_glob(dataset, scope)}', hive_partitioning = true)"


def query(conn: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return conn.sql(sql).df()


def presidential_sections(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return query(
        conn,
        f"""
        SELECT SG_UF, CD_MUNICIPIO, NM_MUNICIPIO, NR_ZONA, NR_SECAO, NR_TURNO, QT_APTOS, QT_COMPARECIMENTO,
               QT_VOTOS_NOMINAIS, QT_VOTOS_BRANCOS, QT_VOTOS_NULOS, NM_LOCAL_VOTACAO, ST_SECAO_INSTALADA,
               DS_ORIGEM_VOTO
        FROM {source("detalhe_votacao_secao", SCOPE_PRESIDENTE)}
        WHERE CD_CARGO = {CARGO_PRESIDENTE}
        """,
    )


def presidential_section_votes(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return query(
        conn,
        f"""
        SELECT SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO, NR_TURNO, NR_VOTAVEL, SUM(QT_VOTOS) AS votos
        FROM {source("votacao_secao", SCOPE_PRESIDENTE)}
        WHERE CD_CARGO = {CARGO_PRESIDENTE}
        GROUP BY ALL
        """,
    )


def presidential_section_leader(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return query(
        conn,
        f"""
        WITH nominal AS (
            SELECT SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO, NR_TURNO, NR_VOTAVEL, QT_VOTOS
            FROM {source("votacao_secao", SCOPE_PRESIDENTE)}
            WHERE CD_CARGO = {CARGO_PRESIDENTE} AND NR_VOTAVEL NOT IN ({NR_VOTAVEL_BRANCO}, {NR_VOTAVEL_NULO})
        )
        SELECT SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO, NR_TURNO,
               SUM(QT_VOTOS) AS votos_nominais, MAX(QT_VOTOS) AS votos_top1,
               arg_max(NR_VOTAVEL, QT_VOTOS) AS nr_votavel_top1
        FROM nominal GROUP BY ALL
        """,
    )


def presidential_unit_wide(conn: duckdb.DuckDBPyConnection, keys: list[str]) -> pd.DataFrame:
    key_sql = ", ".join(keys)
    votes = query(
        conn,
        f"""
        SELECT {key_sql}, NR_TURNO, NR_CANDIDATO, SUM(QT_VOTOS_NOMINAIS_VALIDOS) AS votos
        FROM {source("votacao_candidato_munzona", SCOPE_PRESIDENTE)}
        WHERE CD_CARGO = {CARGO_PRESIDENTE}
        GROUP BY ALL
        """,
    )
    totals = query(
        conn,
        f"""
        SELECT {key_sql}, NR_TURNO, SUM(QT_APTOS) AS aptos, SUM(QT_COMPARECIMENTO) AS comp,
               SUM(QT_VOTOS_BRANCOS) + SUM(QT_TOTAL_VOTOS_NULOS) AS brancos_nulos
        FROM {source("detalhe_votacao_munzona", SCOPE_PRESIDENTE)}
        WHERE CD_CARGO = {CARGO_PRESIDENTE}
        GROUP BY ALL
        """,
    )
    pivot = votes.pivot_table(index=keys + ["NR_TURNO"], columns="NR_CANDIDATO", values="votos", aggfunc="sum", fill_value=0)
    pivot.columns = [f"c{int(column)}" for column in pivot.columns]
    merged = totals.merge(pivot.reset_index(), on=keys + ["NR_TURNO"], how="left").fillna(0)
    first = merged[merged.NR_TURNO == 1].drop(columns="NR_TURNO").set_index(keys).add_suffix("_t1")
    second = merged[merged.NR_TURNO == 2].drop(columns="NR_TURNO").set_index(keys).add_suffix("_t2")
    return first.join(second, how="inner").reset_index()


def presidential_candidates(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return query(
        conn,
        f"""
        SELECT NR_TURNO, NR_CANDIDATO, any_value(NM_URNA_CANDIDATO) AS nome, SUM(QT_VOTOS_NOMINAIS_VALIDOS) AS votos
        FROM {source("votacao_candidato_munzona", SCOPE_PRESIDENTE)}
        WHERE CD_CARGO = {CARGO_PRESIDENTE}
        GROUP BY ALL ORDER BY NR_TURNO, votos DESC
        """,
    )
