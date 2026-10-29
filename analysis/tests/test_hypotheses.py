import copy
import shutil

import pytest
import yaml

from tse.hypotheses import (
    ALLOWED_STATUSES,
    HYPOTHESES_PATH,
    HypothesisSchemaError,
    load_hypotheses,
    update_status,
    validate_hypothesis,
)


@pytest.fixture
def yaml_copy(tmp_path):
    destination = tmp_path / "hypotheses.yaml"
    document = yaml.safe_load(HYPOTHESES_PATH.read_text(encoding="utf-8"))
    for item in document["hypotheses"]:
        item.update(status="proposed", refutation_attempts=[])
        for field in ("script", "table", "verdict", "reviewed_by"):
            item.pop(field, None)
    destination.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return destination


def test_repository_file_loads_and_has_expected_range():
    hypotheses = load_hypotheses()

    assert 20 <= len(hypotheses) <= 30
    assert all(item["status"] in ALLOWED_STATUSES for item in hypotheses)


def test_ids_are_sequential_and_unique():
    ids = [item["id"] for item in load_hypotheses()]

    assert ids == [f"H{index:02d}" for index in range(1, len(ids) + 1)]


def test_unknown_key_raises(yaml_copy):
    sample = copy.deepcopy(load_hypotheses(yaml_copy)[0])
    sample["fraud_probability"] = 0.1

    with pytest.raises(HypothesisSchemaError, match="desconhecidas"):
        validate_hypothesis(sample)


def test_missing_required_key_raises(yaml_copy):
    sample = copy.deepcopy(load_hypotheses(yaml_copy)[0])
    del sample["null_hypothesis"]

    with pytest.raises(HypothesisSchemaError, match="ausentes"):
        validate_hypothesis(sample)


def test_invalid_class_raises(yaml_copy):
    sample = copy.deepcopy(load_hypotheses(yaml_copy)[0])
    sample["class"] = "fraude"

    with pytest.raises(HypothesisSchemaError, match="class"):
        validate_hypothesis(sample)


def test_update_status_to_computed_persists_fields(yaml_copy):
    updated = update_status(
        "H01",
        "computed",
        path=yaml_copy,
        script="src/tse/validation/balance.py",
        table="outputs/tables/balance_aptos_secao.csv",
    )
    reloaded = {item["id"]: item for item in load_hypotheses(yaml_copy)}

    assert updated["status"] == "computed"
    assert reloaded["H01"]["table"] == "outputs/tables/balance_aptos_secao.csv"
    assert reloaded["H02"]["status"] == "proposed"


def test_update_status_computed_without_table_raises_and_keeps_file(yaml_copy):
    before = yaml_copy.read_text(encoding="utf-8")

    with pytest.raises(HypothesisSchemaError, match="exige o campo"):
        update_status("H01", "computed", path=yaml_copy, script="x.py")

    assert yaml_copy.read_text(encoding="utf-8") == before


def test_update_status_reviewed_requires_valid_verdict(yaml_copy):
    update_status("H03", "computed", path=yaml_copy, script="s.py", table="t.csv")

    attempts = [{"by": "agente_8", "date": "2026-10-28", "method": "reproducao", "outcome": "coincide"}]

    with pytest.raises(HypothesisSchemaError, match="verdict"):
        update_status("H03", "reviewed", path=yaml_copy, verdict="PROVADO", reviewed_by="agente_8", refutation_attempts=attempts)

    reviewed = update_status("H03", "reviewed", path=yaml_copy, verdict="FRÁGIL", reviewed_by="agente_8", refutation_attempts=attempts)
    assert reviewed["verdict"] == "FRÁGIL"


def test_reviewed_without_refutation_attempts_raises(yaml_copy):
    update_status("H04", "computed", path=yaml_copy, script="s.py", table="t.csv")

    with pytest.raises(HypothesisSchemaError, match="refutation_attempts"):
        update_status("H04", "reviewed", path=yaml_copy, verdict="SUSTENTADO", reviewed_by="agente_8")


def test_update_unknown_id_raises(yaml_copy):
    with pytest.raises(KeyError):
        update_status("H99", "computed", path=yaml_copy, script="s.py", table="t.csv")


def test_atomic_write_leaves_no_temporary_files(yaml_copy):
    update_status("H02", "computed", path=yaml_copy, script="s.py", table="t.csv")

    leftovers = [entry for entry in yaml_copy.parent.iterdir() if entry.name.startswith(".hypotheses-")]
    assert leftovers == []


def test_duplicate_ids_raise(yaml_copy):
    document = yaml.safe_load(yaml_copy.read_text(encoding="utf-8"))
    document["hypotheses"].append(copy.deepcopy(document["hypotheses"][0]))
    yaml_copy.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")

    with pytest.raises(HypothesisSchemaError, match="duplicados"):
        load_hypotheses(yaml_copy)
