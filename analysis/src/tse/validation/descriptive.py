from __future__ import annotations

import duckdb
import pandas as pd

from .checks import TIMESTAMP_FORMAT
from .identities import CD_CARGO_PRESIDENTE

RAW_DATASETS = (
    "detalhe_votacao_secao", "detalhe_votacao_munzona", "votacao_secao",
    "votacao_candidato_munzona", "votacao_partido_munzona", "consulta_cand",
)
APTOS_PERCENTILES = (0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99)


def generation_timestamps(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    parts = [
        f"""
        SELECT '{dataset}' AS dataset, scope, COUNT(*) AS n_rows,
               COUNT(DISTINCT (DT_GERACAO, HH_GERACAO)) AS n_distinct_geracao,
               MIN(DT_GERACAO || ' ' || HH_GERACAO) AS geracao_min,
               MAX(DT_GERACAO || ' ' || HH_GERACAO) AS geracao_max
        FROM raw_{dataset}
        GROUP BY ALL
        """
        for dataset in RAW_DATASETS
    ]
    totalizacao = f"""
        SELECT scope, MIN(DT_ULTIMA_TOTALIZACAO || ' ' || HH_ULTIMA_TOTALIZACAO) AS totalizacao_min,
               MAX(TRY_STRPTIME(DT_ULTIMA_TOTALIZACAO || ' ' || HH_ULTIMA_TOTALIZACAO, '{TIMESTAMP_FORMAT}')) AS totalizacao_max,
               COUNT(DISTINCT DT_ULTIMA_TOTALIZACAO) AS n_datas_totalizacao
        FROM raw_detalhe_votacao_munzona GROUP BY ALL
    """
    sql = f"""
        WITH g AS ({" UNION ALL ".join(parts)}), t AS ({totalizacao})
        SELECT g.*, t.totalizacao_min, strftime(t.totalizacao_max, '{TIMESTAMP_FORMAT}') AS totalizacao_max,
               t.n_datas_totalizacao
        FROM g LEFT JOIN t ON g.dataset = 'detalhe_votacao_munzona' AND g.scope = t.scope
        ORDER BY dataset, scope
    """
    return conn.execute(sql).df()


def totalization_dates(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return conn.execute(
        """
        SELECT NR_TURNO, DT_ULTIMA_TOTALIZACAO, COUNT(*) AS n_munzona_cargo,
               COUNT(DISTINCT SG_UF) AS n_uf, SUM(QT_COMPARECIMENTO) AS comparecimento
        FROM detalhe_munzona
        GROUP BY ALL
        ORDER BY NR_TURNO, MIN(TRY_STRPTIME(DT_ULTIMA_TOTALIZACAO, '%d/%m/%Y'))
        """
    ).df()


def section_size_distribution(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    quantiles = ", ".join(
        f"quantile_cont(QT_APTOS, {p}) AS p{int(p * 100):02d}" for p in APTOS_PERCENTILES
    )
    return conn.execute(
        f"""
        SELECT SG_UF, NR_TURNO, COUNT(*) AS n_secoes, MIN(QT_APTOS) AS aptos_min, {quantiles},
               MAX(QT_APTOS) AS aptos_max, SUM(QT_APTOS) AS aptos_total,
               SUM((QT_APTOS = 0)::INT) AS n_aptos_zero,
               SUM((QT_APTOS = 0 AND QT_COMPARECIMENTO > 0)::INT) AS n_aptos_zero_com_comparecimento,
               SUM((ST_SECAO_INSTALADA <> 'Sim')::INT) AS n_nao_instaladas,
               SUM((DS_ORIGEM_VOTO <> 'Urna Eletrônica')::INT) AS n_origem_nao_urna
        FROM detalhe_secao
        WHERE CD_CARGO = {CD_CARGO_PRESIDENTE}
        GROUP BY ALL
        ORDER BY SG_UF, NR_TURNO
        """
    ).df()
