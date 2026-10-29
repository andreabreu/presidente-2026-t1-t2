from __future__ import annotations

import duckdb
import pandas as pd

from ..io import scan
from .metrics import concentration_by_group

NATIONAL_SCOPE = "BRASIL"
GOVERNOR_CARGO = 3
LEVEL = ["SG_UF"]


def register_sources(conn: duckdb.DuckDBPyConnection) -> None:
    conn.register("gov_votos", scan("votacao_candidato_munzona", NATIONAL_SCOPE, cargo=GOVERNOR_CARGO, conn=conn))


def scoreboard_uf(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    board = conn.sql(
        """
        select SG_UF, NR_TURNO, NR_CANDIDATO, any_value(NM_URNA_CANDIDATO) as NM_URNA_CANDIDATO,
               any_value(SG_PARTIDO) as SG_PARTIDO, any_value(DS_SIT_TOT_TURNO) as DS_SIT_TOT_TURNO,
               sum(QT_VOTOS_NOMINAIS_VALIDOS)::BIGINT as votos
        from gov_votos
        group by all
        """
    ).df()
    keys = LEVEL + ["NR_TURNO"]
    board["votos_validos_total"] = board.groupby(keys)["votos"].transform("sum")
    board["pct_validos"] = board["votos"] / board["votos_validos_total"] * 100
    board["rank"] = board.groupby(keys)["votos"].rank(method="first", ascending=False).astype(int)
    return board.sort_values(keys + ["rank"]).reset_index(drop=True)


def summary_uf(board: pd.DataFrame) -> pd.DataFrame:
    keys = LEVEL + ["NR_TURNO"]
    winner = board.loc[board["rank"] == 1, keys + ["NR_CANDIDATO", "NM_URNA_CANDIDATO", "SG_PARTIDO", "votos", "pct_validos", "DS_SIT_TOT_TURNO"]]
    winner = winner.rename(
        columns={
            "NR_CANDIDATO": "lider_nr",
            "NM_URNA_CANDIDATO": "lider_nome",
            "SG_PARTIDO": "lider_partido",
            "votos": "lider_votos",
            "pct_validos": "lider_pct_validos",
            "DS_SIT_TOT_TURNO": "lider_situacao",
        }
    )
    second = board.loc[board["rank"] == 2, keys + ["NM_URNA_CANDIDATO", "SG_PARTIDO", "pct_validos"]].rename(
        columns={"NM_URNA_CANDIDATO": "segundo_nome", "SG_PARTIDO": "segundo_partido", "pct_validos": "segundo_pct_validos"}
    )
    summary = winner.merge(second, on=keys, how="left").merge(concentration_by_group(board, keys, "votos"), on=keys, how="left")
    ufs_with_runoff = set(board.loc[board["NR_TURNO"] == 2, "SG_UF"])
    summary["teve_segundo_turno"] = summary["SG_UF"].isin(ufs_with_runoff)
    return summary.sort_values(keys).reset_index(drop=True)
