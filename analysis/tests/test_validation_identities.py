import pytest

from tse.validation.checks import all_checks, comparison_sql, key_select
from tse.validation.identities import (
    CD_CARGO_DEPUTADO_FEDERAL,
    CD_CARGO_PRESIDENTE,
    CD_CARGO_SENADOR,
    MUNZONA_IDENTITIES,
    SECAO_IDENTITIES,
    SENATE_SEATS_RENEWED_2026,
    LinearIdentity,
    evaluate,
    identity_sql,
    linear_combination_sql,
    one,
    relative_delta,
    residual,
    votes_per_voter,
)


def identity(check_id):
    for item in (*SECAO_IDENTITIES, *MUNZONA_IDENTITIES):
        if item.check_id == check_id:
            return item
    raise KeyError(check_id)


def secao_row(**overrides):
    row = {
        "QT_APTOS": 300, "QT_COMPARECIMENTO": 250, "QT_ABSTENCOES": 50,
        "QT_VOTOS_NOMINAIS": 200, "QT_VOTOS_LEGENDA": 20, "QT_VOTOS_BRANCOS": 10, "QT_VOTOS_NULOS": 20,
        "QT_VOTOS_ANULADOS_APU_SEP": 0,
    }
    row.update(overrides)
    return row


def test_votes_per_voter_is_two_only_for_senador():
    assert votes_per_voter(CD_CARGO_SENADOR) == SENATE_SEATS_RENEWED_2026 == 2
    assert votes_per_voter(CD_CARGO_PRESIDENTE) == 1
    assert votes_per_voter(CD_CARGO_DEPUTADO_FEDERAL) == 1


def test_aptos_identity_holds_and_detects_residual():
    aptos = identity("BS01")
    assert residual(aptos, secao_row(), CD_CARGO_PRESIDENTE) == 0
    assert residual(aptos, secao_row(QT_ABSTENCOES=49), CD_CARGO_PRESIDENTE) == -1


def test_comparecimento_identity_scales_by_senate_seats():
    scaled = identity("BS03")
    row = secao_row(QT_VOTOS_NOMINAIS=450)
    assert residual(scaled, row, CD_CARGO_SENADOR) == 0
    assert residual(scaled, row, CD_CARGO_PRESIDENTE) == 250
    expected, observed = evaluate(scaled, row, CD_CARGO_SENADOR)
    assert (expected, observed) == (500, 500)


def test_unscaled_identity_fails_for_senador_with_two_votes():
    unscaled = identity("BS02")
    assert residual(unscaled, secao_row(QT_VOTOS_NOMINAIS=450), CD_CARGO_SENADOR) == 250


def test_munzona_votes_identity_includes_annulled_components():
    row = {
        "QT_VOTOS": 1000, "QT_TOTAL_VOTOS_VALIDOS": 900, "QT_VOTOS_BRANCOS": 30, "QT_TOTAL_VOTOS_NULOS": 50,
        "QT_TOTAL_VOTOS_ANULADOS": 15, "QT_TOTAL_VOTOS_ANUL_SUBJUD": 5, "QT_VOTOS_ANULADOS_APU_SEP": 0,
        "QT_COMPARECIMENTO": 1000,
    }
    assert residual(identity("BM05"), row, CD_CARGO_DEPUTADO_FEDERAL) == 0
    assert residual(identity("BM03"), row, CD_CARGO_DEPUTADO_FEDERAL) == -20


def test_relative_delta_handles_zero_expected():
    assert relative_delta(0, 5) is None
    assert relative_delta(200, 210) == pytest.approx(0.05)
    assert relative_delta(-200, -210) == pytest.approx(-0.05)


def test_linear_combination_sql_matches_python_semantics():
    sql = linear_combination_sql(one("QT_COMPARECIMENTO", "QT_ABSTENCOES"), scale_comparecimento=True)
    assert "QT_COMPARECIMENTO * (CASE WHEN CD_CARGO = 5 THEN 2 ELSE 1 END)" in sql
    assert "(1) * QT_ABSTENCOES" in sql
    lhs, rhs = identity_sql(identity("BS01"))
    assert lhs == "(1) * QT_APTOS"
    assert rhs == "(1) * QT_COMPARECIMENTO + (1) * QT_ABSTENCOES"


def test_identity_columns_are_unique_and_ordered():
    item = LinearIdentity("X", "x", one("A", "B"), one("B", "C"))
    assert item.columns() == ("A", "B", "C")


def test_key_select_fills_missing_keys_with_null():
    select = key_select(("SG_UF", "NR_TURNO", "CD_CARGO"), extra="SQ_CANDIDATO")
    assert "SG_UF AS SG_UF" in select
    assert "NULL AS NR_SECAO" in select
    assert select.endswith("CAST(SQ_CANDIDATO AS VARCHAR) AS chave_extra")


def test_comparison_sql_exposes_standard_columns():
    sql = comparison_sql(key_select(("SG_UF",)), "QT_APTOS", "QT_COMPARECIMENTO", "SELECT * FROM t", "observed > expected")
    for column in ("expected", "observed", "is_violation", "chave_extra"):
        assert column in sql


def test_all_check_ids_are_unique():
    checks = all_checks([95], [96])
    ids = [check.check_id for check in checks]
    assert len(ids) == len(set(ids))
    assert all(check.hypothesis_id.startswith("H") for check in checks)
