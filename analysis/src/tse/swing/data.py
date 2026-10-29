from __future__ import annotations

from dataclasses import dataclass, field

import duckdb
import pandas as pd

from tse.io import parquet_glob

from .constants import (
    LEVEL_MUNICIPIO,
    LEVEL_SECAO,
    LEVEL_ZONA,
    MIN_SHARE_INDIVIDUAL_CANDIDATE,
    NM_VOTAVEL_BRANCO,
    NM_VOTAVEL_NULO,
    ORIGEM_OUTROS_ELIMINADOS,
)

VOTE_T1_PREFIX = "v1_"
VOTE_T2_PREFIX = "v2_"

UNIT_SQL_KEYS = {
    LEVEL_MUNICIPIO: ["SG_UF AS uf", "CD_MUNICIPIO AS cd_municipio"],
    LEVEL_ZONA: ["SG_UF AS uf", "CD_MUNICIPIO AS cd_municipio", "NR_ZONA AS nr_zona"],
    LEVEL_SECAO: ["SG_UF AS uf", "CD_MUNICIPIO AS cd_municipio", "NR_ZONA AS nr_zona", "NR_SECAO AS nr_secao"],
}


@dataclass
class Contest:
    cargo: int
    scope: str
    candidates: dict[int, str]
    finalists: tuple[int, int]
    eliminated: list[int]
    major_eliminated: list[int] = field(default_factory=list)

    @property
    def finalist_a(self) -> int:
        return self.finalists[0]

    @property
    def finalist_b(self) -> int:
        return self.finalists[1]

    @property
    def minor_eliminated(self) -> list[int]:
        return [nr for nr in self.eliminated if nr not in self.major_eliminated]

    def origin_label(self, nr: int) -> str:
        return f"t1_{nr}_{_slug(self.candidates[nr])}"

    def destination_label(self, nr: int) -> str:
        return f"t2_{nr}_{_slug(self.candidates[nr])}"


def _slug(name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in name.lower()).strip("_")


def _key_aliases(level: str) -> list[str]:
    return [expr.split(" AS ")[1] for expr in UNIT_SQL_KEYS[level]]


def describe_contest(conn: duckdb.DuckDBPyConnection, cargo: int, scope: str) -> Contest:
    rows = conn.sql(
        f"""
        SELECT NR_TURNO, NR_CANDIDATO, any_value(NM_URNA_CANDIDATO) AS nome, SUM(QT_VOTOS_NOMINAIS_VALIDOS) AS votos
        FROM read_parquet('{parquet_glob("votacao_candidato_munzona", scope)}', hive_partitioning=true)
        WHERE CD_CARGO = {cargo}
        GROUP BY ALL
        """
    ).df()
    first = rows[rows.NR_TURNO == 1]
    second = rows[rows.NR_TURNO == 2].sort_values("votos", ascending=False)
    if len(second) != 2:
        raise ValueError(f"cargo={cargo} scope={scope}: esperado 2 finalistas, encontrado {len(second)}")
    finalists = tuple(int(nr) for nr in second.NR_CANDIDATO)
    candidates = {int(r.NR_CANDIDATO): str(r.nome) for r in first.itertuples()}
    total_valid = first.votos.sum()
    eliminated = [int(nr) for nr in first.sort_values("votos", ascending=False).NR_CANDIDATO if int(nr) not in finalists]
    major = [
        int(r.NR_CANDIDATO)
        for r in first.itertuples()
        if int(r.NR_CANDIDATO) in eliminated and r.votos / total_valid >= MIN_SHARE_INDIVIDUAL_CANDIDATE
    ]
    return Contest(cargo, scope, candidates, finalists, eliminated, sorted(major, key=eliminated.index))


def load_munzona_wide(conn: duckdb.DuckDBPyConnection, contest: Contest, level: str) -> pd.DataFrame:
    keys = ", ".join(UNIT_SQL_KEYS[level])
    aliases = _key_aliases(level)
    votes = conn.sql(
        f"""
        SELECT {keys}, NR_TURNO AS turno, NR_CANDIDATO AS nr, SUM(QT_VOTOS_NOMINAIS_VALIDOS) AS votos
        FROM read_parquet('{parquet_glob("votacao_candidato_munzona", contest.scope)}', hive_partitioning=true)
        WHERE CD_CARGO = {contest.cargo}
        GROUP BY ALL
        """
    ).df()
    totals = conn.sql(
        f"""
        SELECT {keys}, NR_TURNO AS turno, SUM(QT_APTOS) AS aptos, SUM(QT_COMPARECIMENTO) AS comp,
               SUM(QT_VOTOS_BRANCOS) AS brancos, SUM(QT_TOTAL_VOTOS_NULOS) AS nulos
        FROM read_parquet('{parquet_glob("detalhe_votacao_munzona", contest.scope)}', hive_partitioning=true)
        WHERE CD_CARGO = {contest.cargo}
        GROUP BY ALL
        """
    ).df()
    name_lookup = conn.sql(
        f"""
        SELECT {keys}, any_value(NM_MUNICIPIO) AS nm_municipio
        FROM read_parquet('{parquet_glob("detalhe_votacao_munzona", contest.scope)}', hive_partitioning=true)
        WHERE CD_CARGO = {contest.cargo}
        GROUP BY ALL
        """
    ).df()
    wide = _assemble_wide(votes, totals, aliases, contest)
    return wide.merge(name_lookup, on=aliases, how="left")


def load_secao_wide(conn: duckdb.DuckDBPyConnection, contest: Contest) -> pd.DataFrame:
    level = LEVEL_SECAO
    keys = ", ".join(UNIT_SQL_KEYS[level])
    aliases = _key_aliases(level)
    votes = conn.sql(
        f"""
        SELECT {keys}, NR_TURNO AS turno, NR_VOTAVEL AS nr, SUM(QT_VOTOS) AS votos
        FROM read_parquet('{parquet_glob("votacao_secao", contest.scope)}', hive_partitioning=true)
        WHERE CD_CARGO = {contest.cargo}
          AND NM_VOTAVEL NOT ILIKE '%{NM_VOTAVEL_BRANCO}%' AND NM_VOTAVEL NOT ILIKE '%{NM_VOTAVEL_NULO}%'
        GROUP BY ALL
        """
    ).df()
    totals = conn.sql(
        f"""
        SELECT {keys}, NR_TURNO AS turno, SUM(QT_APTOS) AS aptos, SUM(QT_COMPARECIMENTO) AS comp,
               SUM(QT_VOTOS_BRANCOS) AS brancos, SUM(QT_VOTOS_NULOS) AS nulos,
               any_value(NM_MUNICIPIO) AS nm_municipio, any_value(NR_LOCAL_VOTACAO) AS nr_local_votacao,
               any_value(ST_SECAO_INSTALADA) AS st_secao_instalada
        FROM read_parquet('{parquet_glob("detalhe_votacao_secao", contest.scope)}', hive_partitioning=true)
        WHERE CD_CARGO = {contest.cargo}
        GROUP BY ALL
        """
    ).df()
    extra = totals[totals.turno == 1][aliases + ["nm_municipio", "nr_local_votacao", "st_secao_instalada"]]
    totals = totals.drop(columns=["nm_municipio", "nr_local_votacao", "st_secao_instalada"])
    wide = _assemble_wide(votes, totals, aliases, contest)
    return wide.merge(extra, on=aliases, how="left")


def _assemble_wide(votes: pd.DataFrame, totals: pd.DataFrame, keys: list[str], contest: Contest) -> pd.DataFrame:
    turno1 = _pivot_votes(votes[votes.turno == 1], keys, VOTE_T1_PREFIX)
    turno2 = _pivot_votes(votes[votes.turno == 2], keys, VOTE_T2_PREFIX)
    totals1 = _rename_totals(totals[totals.turno == 1], keys, "_t1")
    totals2 = _rename_totals(totals[totals.turno == 2], keys, "_t2")
    both = totals1.merge(totals2, on=keys, how="outer", indicator="presenca")
    both["presenca"] = both["presenca"].map({"both": "ambos", "left_only": "so_t1", "right_only": "so_t2"})
    wide = both.merge(turno1, on=keys, how="left").merge(turno2, on=keys, how="left")
    vote_columns = [c for c in wide.columns if c.startswith((VOTE_T1_PREFIX, VOTE_T2_PREFIX))]
    wide[vote_columns] = wide[vote_columns].fillna(0)
    _register_unseen_candidates(wide, contest)
    minor_columns = [f"{VOTE_T1_PREFIX}{nr}" for nr in contest.minor_eliminated if f"{VOTE_T1_PREFIX}{nr}" in wide]
    wide[ORIGEM_OUTROS_ELIMINADOS] = wide[minor_columns].sum(axis=1)
    return wide


def _register_unseen_candidates(wide: pd.DataFrame, contest: Contest) -> None:
    for column in [c for c in wide.columns if c.startswith(VOTE_T1_PREFIX)]:
        nr = int(column.removeprefix(VOTE_T1_PREFIX))
        if nr not in contest.candidates:
            contest.candidates[nr] = f"votavel_{nr}"
            contest.eliminated.append(nr)
    expected = [f"{VOTE_T1_PREFIX}{nr}" for nr in contest.eliminated + list(contest.finalists)]
    expected += [f"{VOTE_T2_PREFIX}{nr}" for nr in contest.finalists]
    for column in expected:
        if column not in wide:
            wide[column] = 0.0


def _pivot_votes(votes: pd.DataFrame, keys: list[str], prefix: str) -> pd.DataFrame:
    pivot = votes.pivot_table(index=keys, columns="nr", values="votos", aggfunc="sum", fill_value=0)
    pivot.columns = [f"{prefix}{int(nr)}" for nr in pivot.columns]
    return pivot.reset_index()


def _rename_totals(totals: pd.DataFrame, keys: list[str], suffix: str) -> pd.DataFrame:
    return totals.drop(columns="turno").rename(
        columns={c: f"{c}{suffix}" for c in totals.columns if c not in keys and c != "turno"}
    )


def governor_runoff_scopes(conn: duckdb.DuckDBPyConnection) -> list[str]:
    rows = conn.sql(
        f"""
        SELECT scope FROM read_parquet('{parquet_glob("votacao_candidato_munzona")}', hive_partitioning=true)
        WHERE CD_CARGO = 3 AND NR_TURNO = 2 AND scope <> 'BRASIL' AND length(scope) = 2
        GROUP BY scope ORDER BY scope
        """
    ).fetchall()
    return [r[0] for r in rows]
