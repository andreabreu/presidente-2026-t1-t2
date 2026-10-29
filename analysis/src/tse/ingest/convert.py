from __future__ import annotations
import json
import logging
import shutil
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from ..config import ANALYSIS_ROOT, load_config
from ..io import connect
from ..manifest import sha256_of
from .datasets import CsvSource, list_sources, ALL

log = logging.getLogger("tse.ingest")

SUCCESS_MARKER = "_SUCCESS.json"
STAGING_DIRNAME = "_staging"
EXTRACT_DIR = Path(
    "/private/tmp/claude-501/-Users-andreabreu-Developer-TSE/bcce9737-8bfb-499b-bce4-7348bbc0a38f/scratchpad/extract"
)
CSV_ENCODING = "latin-1"
PARTITION_COLUMNS = ("NR_TURNO", "CD_CARGO")
INTEGER_COLUMNS = frozenset(
    {"NR_TURNO", "NR_ZONA", "NR_SECAO", "CD_MUNICIPIO", "CD_CARGO", "NR_CANDIDATO", "NR_VOTAVEL", "NR_PARTIDO"}
)
VOTE_COUNT_PREFIX = "QT_"


def interim_dir() -> Path:
    return load_config()["interim_dir"]


def target_dir(source: CsvSource) -> Path:
    return interim_dir() / source.dataset / f"scope={source.scope}"


def staging_dir(source: CsvSource) -> Path:
    return interim_dir() / STAGING_DIRNAME / source.dataset / f"scope={source.scope}"


def is_done(source: CsvSource) -> bool:
    return (target_dir(source) / SUCCESS_MARKER).exists()


def extract_member(source: CsvSource) -> Path:
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    destination = EXTRACT_DIR / f"{source.dataset}__{Path(source.member_name).name}"
    with zipfile.ZipFile(source.zip_path) as archive, archive.open(source.member_name) as member:
        with open(destination, "wb") as out:
            shutil.copyfileobj(member, out, length=1 << 24)
    return destination


def read_csv_sql(csv_path: Path) -> str:
    return (
        f"read_csv('{csv_path}', delim=';', header=true, quote='\"', "
        f"encoding='{CSV_ENCODING}', all_varchar=true)"
    )


def cast_expression(column: str) -> str:
    quoted = f'"{column}"'
    if column.startswith(VOTE_COUNT_PREFIX):
        return f"CAST({quoted} AS BIGINT) AS {quoted}"
    if column in INTEGER_COLUMNS:
        return f"CAST({quoted} AS INTEGER) AS {quoted}"
    return quoted


def column_names(conn: duckdb.DuckDBPyConnection, csv_path: Path) -> list[str]:
    return [row[0] for row in conn.execute(f"DESCRIBE SELECT * FROM {read_csv_sql(csv_path)}").fetchall()]


def typed_select_sql(conn: duckdb.DuckDBPyConnection, csv_path: Path) -> str:
    projection = ", ".join(cast_expression(name) for name in column_names(conn, csv_path))
    return f"SELECT {projection} FROM {read_csv_sql(csv_path)}"


def write_partitioned_parquet(conn: duckdb.DuckDBPyConnection, csv_path: Path, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    partition_list = ", ".join(PARTITION_COLUMNS)
    result = conn.execute(
        f"COPY ({typed_select_sql(conn, csv_path)}) TO '{out_dir}' "
        f"(FORMAT PARQUET, PARTITION_BY ({partition_list}), COMPRESSION ZSTD, OVERWRITE_OR_IGNORE)"
    ).fetchone()
    return int(result[0]) if result else 0


def load_manifest_hashes() -> dict[str, str]:
    manifest_path = load_config()["outputs_dir"] / "run_manifest.json"
    if not manifest_path.exists():
        return {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {Path(entry["path"]).name: entry["sha256"] for entry in manifest.get("inputs", [])}


def zip_sha256(zip_path: Path, known_hashes: dict[str, str]) -> str:
    return known_hashes.get(zip_path.name) or sha256_of(zip_path)


def write_success_marker(out_dir: Path, source: CsvSource, rows: int, zip_hash: str, seconds: float) -> None:
    marker = {
        "dataset": source.dataset,
        "scope": source.scope,
        "rows": rows,
        "source_zip": str(source.zip_path.relative_to(ANALYSIS_ROOT.parent)),
        "source_csv": source.member_name,
        "zip_sha256": zip_hash,
        "partition_by": list(PARTITION_COLUMNS),
        "elapsed_seconds": round(seconds, 2),
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / SUCCESS_MARKER).write_text(json.dumps(marker, indent=2, ensure_ascii=False), encoding="utf-8")


def promote_staging(staging: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging.replace(target)
    remove_empty_parents(staging.parent, interim_dir() / STAGING_DIRNAME)


def remove_empty_parents(directory: Path, stop_at: Path) -> None:
    while directory != stop_at.parent and directory.exists() and not any(directory.iterdir()):
        directory.rmdir()
        directory = directory.parent


def ingest_source(source: CsvSource, conn: duckdb.DuckDBPyConnection, known_hashes: dict[str, str]) -> int:
    if is_done(source):
        log.info("skip %s (already ingested)", source.label)
        return -1
    started = time.perf_counter()
    staging = staging_dir(source)
    if staging.exists():
        shutil.rmtree(staging)
    csv_path = extract_member(source)
    try:
        log.info("convert %s from %s (%d MB csv)", source.label, source.zip_path.name, csv_path.stat().st_size >> 20)
        rows = write_partitioned_parquet(conn, csv_path, staging)
    finally:
        csv_path.unlink(missing_ok=True)
    elapsed = time.perf_counter() - started
    write_success_marker(staging, source, rows, zip_sha256(source.zip_path, known_hashes), elapsed)
    promote_staging(staging, target_dir(source))
    log.info("done %s rows=%d in %.1fs", source.label, rows, elapsed)
    return rows


def run_ingest(dataset: str = ALL, scope: str = ALL) -> dict[str, int]:
    sources = list_sources(dataset, scope)
    log.info("ingest start: %d csv sources (dataset=%s scope=%s)", len(sources), dataset, scope)
    known_hashes = load_manifest_hashes()
    conn = connect()
    results: dict[str, int] = {}
    for source in sources:
        try:
            results[source.label] = ingest_source(source, conn, known_hashes)
        except Exception:
            log.exception("FAILED %s", source.label)
            results[source.label] = -2
    log.info("ingest finished: %d ok/skipped, %d failed", sum(v >= -1 for v in results.values()), sum(v == -2 for v in results.values()))
    return results
