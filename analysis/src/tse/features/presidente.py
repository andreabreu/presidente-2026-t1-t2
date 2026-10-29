from __future__ import annotations

import duckdb
import pandas as pd

from ..io import scan
from .metrics import concentration_by_group

PRESIDENT_SCOPE = "BR"
PRESIDENT_CARGO = 1
TITULAR_CARGO_PRESIDENT = 1
EXTERIOR_UF = "ZZ"
CANDIDATE_COLUMNS = ["NR_TURNO", "NR_CANDIDATO", "NM_URNA_CANDIDATO", "SG_PARTIDO", "NM_PARTIDO"]


def register_sources(conn: duckdb.DuckDBPyConnection) -> None:
    conn.register("pres_votos", scan("votacao_candidato_munzona", PRESIDENT_SCOPE, cargo=PRESIDENT_CARGO, conn=conn))
    conn.register("pres_cand", scan("consulta_cand", PRESIDENT_SCOPE, cargo=TITULAR_CARGO_PRESIDENT, conn=conn))


def candidates(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return conn.sql(
        """
        select distinct NR_TURNO, NR_CANDIDATO, NM_URNA_CANDIDATO, NM_CANDIDATO, SG_PARTIDO, NM_PARTIDO,
               DS_COMPOSICAO_COLIGACAO, DS_SIT_TOT_TURNO
        from pres_cand
        order by NR_TURNO, NR_CANDIDATO
        """
    ).df()


def _votes_by(conn: duckdb.DuckDBPyConnection, level_columns: list[str]) -> pd.DataFrame:
    level = "".join(f"{column}, " for column in level_columns)
    return conn.sql(
        f"""
        select {level}NR_TURNO, NR_CANDIDATO,
               sum(QT_VOTOS_NOMINAIS_VALIDOS)::BIGINT as votos
        from pres_votos
        group by all
        """
    ).df()


def _attach_scoreboard(votes: pd.DataFrame, cands: pd.DataFrame, level_columns: list[str]) -> pd.DataFrame:
    keys = level_columns + ["NR_TURNO"]
    merged = votes.merge(cands[CANDIDATE_COLUMNS].drop_duplicates(), on=["NR_TURNO", "NR_CANDIDATO"], how="left")
    merged["votos_validos_total"] = merged.groupby(keys)["votos"].transform("sum")
    merged["pct_validos"] = merged["votos"] / merged["votos_validos_total"] * 100
    merged["rank"] = merged.groupby(keys)["votos"].rank(method="first", ascending=False).astype(int)
    return merged.sort_values(keys + ["rank"]).reset_index(drop=True)


def national_scoreboard(conn: duckdb.DuckDBPyConnection, cands: pd.DataFrame) -> pd.DataFrame:
    board = _attach_scoreboard(_votes_by(conn, []), cands, [])
    board["rank_turno1"] = board["NR_CANDIDATO"].map(
        board.loc[board["NR_TURNO"] == 1].set_index("NR_CANDIDATO")["rank"]
    )
    return board


def scoreboard_uf(conn: duckdb.DuckDBPyConnection, cands: pd.DataFrame) -> pd.DataFrame:
    return _attach_scoreboard(_votes_by(conn, ["SG_UF"]), cands, ["SG_UF"])


def scoreboard_mun(conn: duckdb.DuckDBPyConnection, cands: pd.DataFrame) -> pd.DataFrame:
    return _attach_scoreboard(_votes_by(conn, ["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO"]), cands, ["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO"])


def concentration(board: pd.DataFrame, level_columns: list[str]) -> pd.DataFrame:
    return concentration_by_group(board, level_columns + ["NR_TURNO"], "votos")


def winners(board: pd.DataFrame, level_columns: list[str]) -> pd.DataFrame:
    keys = level_columns + ["NR_TURNO"]
    top = board.loc[board["rank"] == 1, keys + ["NR_CANDIDATO", "NM_URNA_CANDIDATO", "SG_PARTIDO", "votos", "pct_validos"]]
    top = top.rename(
        columns={
            "NR_CANDIDATO": "vencedor_nr",
            "NM_URNA_CANDIDATO": "vencedor_nome",
            "SG_PARTIDO": "vencedor_partido",
            "votos": "vencedor_votos",
            "pct_validos": "vencedor_pct_validos",
        }
    )
    second = board.loc[board["rank"] == 2, keys + ["NR_CANDIDATO", "NM_URNA_CANDIDATO", "pct_validos"]].rename(
        columns={"NR_CANDIDATO": "segundo_nr", "NM_URNA_CANDIDATO": "segundo_nome", "pct_validos": "segundo_pct_validos"}
    )
    return top.merge(second, on=keys, how="left").merge(concentration(board, level_columns), on=keys, how="left")


def rank_changes(board: pd.DataFrame, level_columns: list[str]) -> pd.DataFrame:
    keys = level_columns + ["NR_CANDIDATO"]
    first = board.loc[board["NR_TURNO"] == 1, keys + ["NM_URNA_CANDIDATO", "SG_PARTIDO", "rank", "pct_validos", "votos"]]
    second = board.loc[board["NR_TURNO"] == 2, keys + ["rank", "pct_validos", "votos"]]
    merged = first.merge(second, on=keys, suffixes=("_t1", "_t2"), how="inner")
    merged["mudou_lider"] = merged["rank_t1"] != merged["rank_t2"]
    merged["delta_pct_validos"] = merged["pct_validos_t2"] - merged["pct_validos_t1"]
    merged["delta_votos"] = merged["votos_t2"] - merged["votos_t1"]
    return merged.sort_values(level_columns + ["rank_t2"]).reset_index(drop=True)
