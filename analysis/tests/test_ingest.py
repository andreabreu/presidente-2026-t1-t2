from __future__ import annotations
import json
import shutil
import zipfile

import pytest

from tse.ingest import list_sources
from tse.ingest.convert import SUCCESS_MARKER, ingest_source, is_done, target_dir
from tse.io import connect, scan

DATASET = "detalhe_votacao_munzona"
SCOPE = "AC"


def csv_data_rows(source) -> int:
    with zipfile.ZipFile(source.zip_path) as archive, archive.open(source.member_name) as member:
        return sum(1 for _ in member) - 1


@pytest.fixture
def source():
    (only,) = list_sources(DATASET, SCOPE)
    return only


def test_ingest_row_count_matches_csv(source):
    conn = connect("2GB")
    shutil.rmtree(target_dir(source), ignore_errors=True)

    rows = ingest_source(source, conn, known_hashes={})

    assert rows == csv_data_rows(source)
    assert is_done(source)
    marker = json.loads((target_dir(source) / SUCCESS_MARKER).read_text())
    assert marker["rows"] == rows
    assert scan(DATASET, SCOPE, conn=conn).count("*").fetchall()[0][0] == rows


def test_ingest_is_idempotent(source):
    conn = connect("2GB")
    if not is_done(source):
        ingest_source(source, conn, known_hashes={})

    assert ingest_source(source, conn, known_hashes={}) == -1


def test_scan_filters_and_types(source):
    conn = connect("2GB")
    if not is_done(source):
        ingest_source(source, conn, known_hashes={})

    relation = scan(DATASET, SCOPE, turno=1, conn=conn)
    types = dict(zip(relation.columns, [str(t) for t in relation.types]))

    assert types["CD_MUNICIPIO"] == "INTEGER"
    assert types["QT_APTOS"] == "BIGINT"
    assert relation.aggregate("min(CD_MUNICIPIO)").fetchall()[0][0] == 1007
    assert relation.aggregate("count(distinct NR_TURNO)").fetchall()[0][0] == 1
