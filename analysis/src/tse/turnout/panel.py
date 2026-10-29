from __future__ import annotations

import duckdb
import pandas as pd

from ..io import scan
from ..robust import add_stratified_robust_scores, quantile_bins
from .rates import add_rates

PRESIDENT_SCOPE = "BR"
NATIONAL_SCOPE = "BRASIL"
PRESIDENT_CARGO = 1
FEDERAL_DEPUTY_CARGO = 6
FIRST_ROUND = 1
EXTERIOR_UF = "ZZ"
APTOS_BIN_QUANTILES = [0.2, 0.4, 0.6, 0.8]
APTOS_BIN_LABELS = ["Q1_menor", "Q2", "Q3", "Q4", "Q5_maior"]
SUM_COLUMNS = """
    sum(QT_APTOS)::BIGINT as QT_APTOS,
    sum(QT_COMPARECIMENTO)::BIGINT as QT_COMPARECIMENTO,
    sum(QT_ABSTENCOES)::BIGINT as QT_ABSTENCOES,
    sum(QT_VOTOS_BRANCOS)::BIGINT as QT_VOTOS_BRANCOS,
    sum(QT_TOTAL_VOTOS_NULOS)::BIGINT as QT_VOTOS_NULOS,
    sum(QT_VOTOS_NULOS_TECNICOS)::BIGINT as QT_VOTOS_NULOS_TECNICOS,
    sum(QT_TOTAL_VOTOS_VALIDOS)::BIGINT as QT_VOTOS_VALIDOS,
    sum(QT_TOTAL_SECOES)::BIGINT as QT_TOTAL_SECOES,
    sum(QT_SECOES_NAO_INSTALADAS)::BIGINT as QT_SECOES_NAO_INSTALADAS,
    sum(QT_ELEITORES_SECOES_NAO_INSTALADAS)::BIGINT as QT_ELEITORES_SECOES_NAO_INSTALADAS
"""


def register_sources(conn: duckdb.DuckDBPyConnection) -> None:
    conn.register("det_pres", scan("detalhe_votacao_munzona", PRESIDENT_SCOPE, cargo=PRESIDENT_CARGO, conn=conn))
    conn.register("det_depfed", scan("detalhe_votacao_munzona", NATIONAL_SCOPE, turno=FIRST_ROUND, cargo=FEDERAL_DEPUTY_CARGO, conn=conn))
    conn.register("sec_pres", scan("detalhe_votacao_secao", PRESIDENT_SCOPE, cargo=PRESIDENT_CARGO, conn=conn))


def transit_votes_summary(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return conn.sql(
        f"""
        select 'detalhe_votacao_munzona/BR' as fonte, NR_TURNO, ST_VOTO_EM_TRANSITO, count(*) as n_linhas, {SUM_COLUMNS}
        from det_pres group by all
        union all
        select 'detalhe_votacao_munzona/BRASIL cargo 6', NR_TURNO, ST_VOTO_EM_TRANSITO, count(*), {SUM_COLUMNS}
        from det_depfed group by all
        order by 1, 2, 3
        """
    ).df()


def _aggregate(conn: duckdb.DuckDBPyConnection, source: str, level_columns: list[str], exclude_transit: bool) -> pd.DataFrame:
    level = ", ".join(level_columns + ["NR_TURNO"])
    where = "where ST_VOTO_EM_TRANSITO <> 'S'" if exclude_transit else ""
    frame = conn.sql(f"select {level}, {SUM_COLUMNS} from {source} {where} group by all order by all").df()
    return add_rates(frame)


def by_uf(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _aggregate(conn, "det_pres", ["SG_UF"], exclude_transit=False)


def by_municipio(conn: duckdb.DuckDBPyConnection, min_strata_size: int) -> pd.DataFrame:
    frame = _aggregate(conn, "det_pres", ["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO"], exclude_transit=True)
    frame["exterior"] = frame["SG_UF"] == EXTERIOR_UF
    frame["faixa_aptos"] = frame.groupby("NR_TURNO")["QT_APTOS"].transform(lambda s: quantile_bins(s, APTOS_BIN_QUANTILES, APTOS_BIN_LABELS))
    strata = ["SG_UF", "faixa_aptos", "NR_TURNO"]
    for metric in ("taxa_abstencao", "taxa_nulos_comp", "taxa_brancos_comp"):
        frame = add_stratified_robust_scores(frame, metric, strata, min_strata_size)
    return frame


def by_zona(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _aggregate(conn, "det_pres", ["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA"], exclude_transit=True)


def depfed_by_uf(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _aggregate(conn, "det_depfed", ["SG_UF"], exclude_transit=False)


def section_size_by_uf(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return conn.sql(
        """
        select SG_UF, NR_TURNO, count(*) as n_secoes,
               sum(case when ST_SECAO_INSTALADA = 'Sim' then 1 else 0 end) as n_instaladas,
               sum(case when QT_APTOS = 0 then 1 else 0 end) as n_aptos_zero,
               sum(case when QT_APTOS = 0 and QT_COMPARECIMENTO > 0 then 1 else 0 end) as n_aptos_zero_com_votos,
               sum(case when QT_COMPARECIMENTO > QT_APTOS then 1 else 0 end) as n_comparecimento_maior_aptos,
               avg(QT_APTOS) as aptos_media, median(QT_APTOS) as aptos_mediana, stddev_samp(QT_APTOS) as aptos_desvio,
               min(QT_APTOS) as aptos_min,
               quantile_cont(QT_APTOS, 0.01) as aptos_p01, quantile_cont(QT_APTOS, 0.05) as aptos_p05,
               quantile_cont(QT_APTOS, 0.25) as aptos_p25, quantile_cont(QT_APTOS, 0.75) as aptos_p75,
               quantile_cont(QT_APTOS, 0.95) as aptos_p95, quantile_cont(QT_APTOS, 0.99) as aptos_p99,
               max(QT_APTOS) as aptos_max,
               sum(QT_APTOS)::BIGINT as aptos_total
        from sec_pres
        group by all order by all
        """
    ).df()


def urn_model_by_uf(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    frame = conn.sql(
        """
        select SG_UF, NR_TURNO, CD_MODELO_URNA, DS_MODELO_URNA,
               count(*) as n_secoes,
               sum(QT_APTOS)::BIGINT as QT_APTOS, sum(QT_COMPARECIMENTO)::BIGINT as QT_COMPARECIMENTO,
               sum(QT_ABSTENCOES)::BIGINT as QT_ABSTENCOES,
               sum(QT_VOTOS_BRANCOS)::BIGINT as QT_VOTOS_BRANCOS, sum(QT_VOTOS_NULOS)::BIGINT as QT_VOTOS_NULOS,
               avg(case when QT_APTOS > 0 then QT_COMPARECIMENTO * 100.0 / QT_APTOS end) as media_taxa_comparecimento_secao,
               avg(case when QT_COMPARECIMENTO > 0 then QT_VOTOS_NULOS * 100.0 / QT_COMPARECIMENTO end) as media_taxa_nulos_secao,
               avg(case when QT_COMPARECIMENTO > 0 then QT_VOTOS_BRANCOS * 100.0 / QT_COMPARECIMENTO end) as media_taxa_brancos_secao,
               avg(QT_APTOS) as aptos_medio_secao
        from sec_pres
        where ST_SECAO_INSTALADA = 'Sim'
        group by all order by all
        """
    ).df()
    frame["share_secoes_na_uf"] = frame["n_secoes"] / frame.groupby(["SG_UF", "NR_TURNO"])["n_secoes"].transform("sum") * 100
    return add_rates(frame)
