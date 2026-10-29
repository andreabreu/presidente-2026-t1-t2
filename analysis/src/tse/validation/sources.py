from __future__ import annotations

import duckdb

from ..io import scan
from .identities import CD_CARGO_PRESIDENTE

SCOPE_PRESIDENTE = "BR"
SCOPE_NACIONAL = "BRASIL"
SCOPE_EXTERIOR = "ZZ"
NATIONAL_SCOPES = (SCOPE_PRESIDENTE, SCOPE_NACIONAL)

BRANCO_PATTERN = "%BRANCO%"
NULO_PATTERN = "%NULO%"

CARGOS_COM_VOTO = (1, 3, 5, 6, 7, 8)


def register_sources(conn: duckdb.DuckDBPyConnection) -> None:
    for dataset in ("detalhe_votacao_secao", "detalhe_votacao_munzona", "votacao_secao",
                    "votacao_candidato_munzona", "votacao_partido_munzona", "consulta_cand"):
        conn.register(f"raw_{dataset}", scan(dataset, conn=conn))
    for name, sql in CANONICAL_VIEWS.items():
        conn.execute(f"CREATE OR REPLACE VIEW {name} AS {sql}")


def canonical_secao_filter() -> str:
    uf_scopes = ", ".join(f"'{scope}'" for scope in (*NATIONAL_SCOPES, SCOPE_EXTERIOR))
    return (
        f"(scope = '{SCOPE_PRESIDENTE}' AND CD_CARGO = {CD_CARGO_PRESIDENTE}) "
        f"OR (scope NOT IN ({uf_scopes}) AND CD_CARGO <> {CD_CARGO_PRESIDENTE})"
    )


CANONICAL_VIEWS = {
    "detalhe_secao": f"SELECT * FROM raw_detalhe_votacao_secao WHERE {canonical_secao_filter()}",
    "detalhe_munzona": f"SELECT * FROM raw_detalhe_votacao_munzona WHERE scope = '{SCOPE_NACIONAL}'",
    "votacao_secao": (
        f"SELECT * FROM raw_votacao_secao WHERE (scope = '{SCOPE_PRESIDENTE}') = (CD_CARGO = {CD_CARGO_PRESIDENTE})"
    ),
    "candidato_munzona": f"SELECT * FROM raw_votacao_candidato_munzona WHERE scope = '{SCOPE_NACIONAL}'",
    "partido_munzona": f"SELECT * FROM raw_votacao_partido_munzona WHERE scope = '{SCOPE_NACIONAL}'",
    "consulta_cand": f"SELECT * FROM raw_consulta_cand WHERE scope = '{SCOPE_NACIONAL}'",
}


def discover_votavel_codes(conn: duckdb.DuckDBPyConnection) -> dict[str, list[int]]:
    """Códigos de NR_VOTAVEL para branco, nulo e legenda, inferidos de NM_VOTAVEL/SQ_CANDIDATO."""
    rows = conn.execute(
        f"""
        SELECT
            CASE
                WHEN upper(NM_VOTAVEL) LIKE '{BRANCO_PATTERN}' THEN 'branco'
                WHEN upper(NM_VOTAVEL) LIKE '{NULO_PATTERN}' THEN 'nulo'
                ELSE 'legenda'
            END AS classe,
            list(DISTINCT NR_VOTAVEL ORDER BY NR_VOTAVEL)
        FROM votacao_secao
        WHERE TRY_CAST(SQ_CANDIDATO AS BIGINT) < 0
        GROUP BY 1
        """
    ).fetchall()
    return {classe: list(codes) for classe, codes in rows}


def sql_list(values: list[int]) -> str:
    return ", ".join(str(int(value)) for value in values) or "NULL"
