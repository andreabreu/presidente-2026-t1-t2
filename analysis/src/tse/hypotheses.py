from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from tse.config import ANALYSIS_ROOT

HYPOTHESES_PATH = ANALYSIS_ROOT / "hypotheses.yaml"

ALLOWED_CLASSES = frozenset({"documental", "estatistico", "forense"})
ALLOWED_UNITS = frozenset({"secao", "zona", "municipio", "uf"})
ALLOWED_STATUSES = frozenset({"proposed", "computed", "reviewed", "published"})
ALLOWED_VERDICTS = frozenset({"SUSTENTADO", "FRÁGIL", "REFUTADO", "INCONCLUSIVO"})

REQUIRED_KEYS = frozenset(
    {
        "id",
        "title",
        "class",
        "unit",
        "null_hypothesis",
        "test",
        "data",
        "expected_output_table",
        "status",
        "refutation_attempts",
    }
)
OPTIONAL_KEYS = frozenset({"script", "table", "verdict", "reviewed_by", "notes"})
ALLOWED_KEYS = REQUIRED_KEYS | OPTIONAL_KEYS
TEST_KEYS = frozenset({"method", "controls", "correction"})
DATA_KEYS = frozenset({"dataset", "columns"})
REQUIRED_FIELDS_BY_STATUS = {
    "computed": ("script", "table"),
    "reviewed": ("script", "table", "verdict", "reviewed_by", "refutation_attempts"),
    "published": ("script", "table", "verdict", "reviewed_by", "refutation_attempts"),
}


class HypothesisSchemaError(ValueError):
    pass


def load_hypotheses(path: Path = HYPOTHESES_PATH) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    hypotheses = document.get("hypotheses") if isinstance(document, dict) else None
    if not isinstance(hypotheses, list):
        raise HypothesisSchemaError("arquivo deve conter a chave 'hypotheses' com uma lista")
    for item in hypotheses:
        validate_hypothesis(item)
    _ensure_unique_ids(hypotheses)
    return hypotheses


def validate_hypothesis(item: dict[str, Any]) -> None:
    if not isinstance(item, dict):
        raise HypothesisSchemaError(f"hipótese deve ser um mapeamento, recebido {type(item).__name__}")
    keys = set(item)
    unknown = keys - ALLOWED_KEYS
    if unknown:
        raise HypothesisSchemaError(f"{item.get('id', '?')}: chaves desconhecidas {sorted(unknown)}")
    missing = REQUIRED_KEYS - keys
    if missing:
        raise HypothesisSchemaError(f"{item.get('id', '?')}: chaves obrigatórias ausentes {sorted(missing)}")
    _validate_enum(item, "class", ALLOWED_CLASSES)
    _validate_enum(item, "unit", ALLOWED_UNITS)
    _validate_enum(item, "status", ALLOWED_STATUSES)
    _validate_test(item)
    _validate_data(item)
    _validate_status_fields(item)
    if not isinstance(item["refutation_attempts"], list):
        raise HypothesisSchemaError(f"{item['id']}: refutation_attempts deve ser lista")


def update_status(hypothesis_id: str, status: str, path: Path = HYPOTHESES_PATH, **fields: Any) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    target = _find(document["hypotheses"], hypothesis_id)
    target["status"] = status
    target.update(fields)
    validate_hypothesis(target)
    _write_atomically(path, document)
    return target


def _validate_enum(item: dict[str, Any], key: str, allowed: frozenset[str]) -> None:
    if item[key] not in allowed:
        raise HypothesisSchemaError(f"{item['id']}: {key}={item[key]!r} fora de {sorted(allowed)}")


def _validate_test(item: dict[str, Any]) -> None:
    test = item["test"]
    if not isinstance(test, dict) or set(test) != TEST_KEYS:
        raise HypothesisSchemaError(f"{item['id']}: test deve ter exatamente as chaves {sorted(TEST_KEYS)}")
    if not isinstance(test["controls"], list):
        raise HypothesisSchemaError(f"{item['id']}: test.controls deve ser lista")


def _validate_data(item: dict[str, Any]) -> None:
    data = item["data"]
    if not isinstance(data, list) or not data:
        raise HypothesisSchemaError(f"{item['id']}: data deve ser lista não vazia")
    for entry in data:
        if not isinstance(entry, dict) or set(entry) != DATA_KEYS:
            raise HypothesisSchemaError(f"{item['id']}: cada entrada de data deve ter as chaves {sorted(DATA_KEYS)}")
        if not isinstance(entry["columns"], list):
            raise HypothesisSchemaError(f"{item['id']}: data.columns deve ser lista")


def _validate_status_fields(item: dict[str, Any]) -> None:
    for field in REQUIRED_FIELDS_BY_STATUS.get(item["status"], ()):
        if not item.get(field):
            raise HypothesisSchemaError(f"{item['id']}: status {item['status']} exige o campo '{field}'")
    if "verdict" in item and item["verdict"] not in ALLOWED_VERDICTS:
        raise HypothesisSchemaError(f"{item['id']}: verdict fora de {sorted(ALLOWED_VERDICTS)}")


def _ensure_unique_ids(hypotheses: list[dict[str, Any]]) -> None:
    ids = [item["id"] for item in hypotheses]
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    if duplicates:
        raise HypothesisSchemaError(f"ids duplicados: {duplicates}")


def _find(hypotheses: list[dict[str, Any]], hypothesis_id: str) -> dict[str, Any]:
    for item in hypotheses:
        if item["id"] == hypothesis_id:
            return item
    raise KeyError(f"hipótese {hypothesis_id} não encontrada")


def _write_atomically(path: Path, document: dict[str, Any]) -> None:
    # Escrever em arquivo temporário no mesmo diretório e renomear garante que
    # um leitor concorrente nunca veja o YAML parcialmente gravado.
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=".hypotheses-", suffix=".yaml")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            yaml.safe_dump(document, handle, allow_unicode=True, sort_keys=False, width=100)
        os.replace(temporary_name, path)
    except BaseException:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
        raise
