from __future__ import annotations

import duckdb
import pandas as pd

from ..io import scan

NATIONAL_SCOPE = "BRASIL"
FEDERAL_DEPUTY_CARGO = 6
FIRST_ROUND = 1


def register_sources(conn: duckdb.DuckDBPyConnection) -> None:
    conn.register("dep_votos", scan("votacao_candidato_munzona", NATIONAL_SCOPE, turno=FIRST_ROUND, cargo=FEDERAL_DEPUTY_CARGO, conn=conn))
    conn.register("dep_partido", scan("votacao_partido_munzona", NATIONAL_SCOPE, turno=FIRST_ROUND, cargo=FEDERAL_DEPUTY_CARGO, conn=conn))


def votes_by_party(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    frame = conn.sql(
        """
        with por_uf as (
            select SG_UF, NR_PARTIDO, any_value(SG_PARTIDO) as SG_PARTIDO, any_value(SG_FEDERACAO) as SG_FEDERACAO,
                   sum(QT_VOTOS_NOMINAIS_VALIDOS)::BIGINT as votos_nominais,
                   sum(QT_VOTOS_LEGENDA_VALIDOS)::BIGINT as votos_legenda,
                   sum(QT_VOTOS_NOMINAIS_ANUL_SUBJUD + QT_VOTOS_LEGENDA_ANUL_SUBJUD)::BIGINT as votos_anulados_subjudice
            from dep_partido
            group by SG_UF, NR_PARTIDO
        )
        select 'BRASIL' as nivel, 'BR' as SG_UF, NR_PARTIDO, any_value(SG_PARTIDO) as SG_PARTIDO, any_value(SG_FEDERACAO) as SG_FEDERACAO,
               sum(votos_nominais) as votos_nominais, sum(votos_legenda) as votos_legenda, sum(votos_anulados_subjudice) as votos_anulados_subjudice
        from por_uf group by NR_PARTIDO
        union all
        select 'UF', SG_UF, NR_PARTIDO, SG_PARTIDO, SG_FEDERACAO, votos_nominais, votos_legenda, votos_anulados_subjudice from por_uf
        """
    ).df()
    frame["votos_validos"] = frame["votos_nominais"] + frame["votos_legenda"]
    frame["votos_validos_total"] = frame.groupby(["nivel", "SG_UF"])["votos_validos"].transform("sum")
    frame["pct_validos"] = frame["votos_validos"] / frame["votos_validos_total"] * 100
    frame["pct_legenda_no_partido"] = frame["votos_legenda"] / frame["votos_validos"].where(frame["votos_validos"] > 0) * 100
    frame["rank"] = frame.groupby(["nivel", "SG_UF"])["votos_validos"].rank(method="first", ascending=False).astype(int)
    return frame.sort_values(["nivel", "SG_UF", "rank"]).reset_index(drop=True)


def top_candidates(conn: duckdb.DuckDBPyConnection, top_n_national: int, top_n_uf: int, detail_ufs: list[str]) -> pd.DataFrame:
    by_candidate = conn.sql(
        """
        select SG_UF, SQ_CANDIDATO, NR_CANDIDATO, any_value(NM_URNA_CANDIDATO) as NM_URNA_CANDIDATO,
               any_value(SG_PARTIDO) as SG_PARTIDO, any_value(DS_SIT_TOT_TURNO) as DS_SIT_TOT_TURNO,
               sum(QT_VOTOS_NOMINAIS_VALIDOS)::BIGINT as votos
        from dep_votos
        group by all
        """
    ).df()
    by_candidate["votos_validos_uf"] = by_candidate.groupby("SG_UF")["votos"].transform("sum")
    by_candidate["pct_validos_uf"] = by_candidate["votos"] / by_candidate["votos_validos_uf"] * 100
    national = by_candidate.sort_values("votos", ascending=False).head(top_n_national).assign(recorte="BRASIL")
    national["rank"] = range(1, len(national) + 1)
    pieces = [national]
    for uf in detail_ufs:
        uf_top = by_candidate.loc[by_candidate["SG_UF"] == uf].sort_values("votos", ascending=False).head(top_n_uf).assign(recorte=uf)
        uf_top["rank"] = range(1, len(uf_top) + 1)
        pieces.append(uf_top)
    return pd.concat(pieces, ignore_index=True)
