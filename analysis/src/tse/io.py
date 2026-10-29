from __future__ import annotations
from pathlib import Path

import duckdb
import polars as pl

from .config import ANALYSIS_ROOT, load_config

MEMORY_LIMIT = "8GB"
DUCKDB_TEMP_DIR = ANALYSIS_ROOT / "data" / ".duckdb_tmp"
PARQUET_GLOB = "scope=*/NR_TURNO=*/CD_CARGO=*/*.parquet"


def connect(memory_limit: str = MEMORY_LIMIT) -> duckdb.DuckDBPyConnection:
    DUCKDB_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect()
    conn.execute(f"SET memory_limit='{memory_limit}'")
    conn.execute(f"SET temp_directory='{DUCKDB_TEMP_DIR}'")
    conn.execute("SET preserve_insertion_order=false")
    return conn


def dataset_dir(dataset: str) -> Path:
    return load_config()["interim_dir"] / dataset


def parquet_glob(dataset: str, scope: str | None = None) -> str:
    pattern = PARQUET_GLOB if scope is None else PARQUET_GLOB.replace("scope=*", f"scope={scope}", 1)
    return str(dataset_dir(dataset) / pattern)


def scan(
    dataset: str,
    scope: str | None = None,
    turno: int | None = None,
    cargo: int | None = None,
    conn: duckdb.DuckDBPyConnection | None = None,
    engine: str = "duckdb",
) -> duckdb.DuckDBPyRelation | pl.LazyFrame:
    if engine == "polars":
        return _scan_polars(dataset, scope, turno, cargo)
    return _scan_duckdb(dataset, scope, turno, cargo, conn or connect())


def _scan_duckdb(dataset, scope, turno, cargo, conn) -> duckdb.DuckDBPyRelation:
    relation = conn.read_parquet(parquet_glob(dataset, scope), hive_partitioning=True)
    if turno is not None:
        relation = relation.filter(f"NR_TURNO = {int(turno)}")
    if cargo is not None:
        relation = relation.filter(f"CD_CARGO = {int(cargo)}")
    return relation


def _scan_polars(dataset, scope, turno, cargo) -> pl.LazyFrame:
    frame = pl.scan_parquet(parquet_glob(dataset, scope), hive_partitioning=True)
    if turno is not None:
        frame = frame.filter(pl.col("NR_TURNO") == int(turno))
    if cargo is not None:
        frame = frame.filter(pl.col("CD_CARGO") == int(cargo))
    return frame
