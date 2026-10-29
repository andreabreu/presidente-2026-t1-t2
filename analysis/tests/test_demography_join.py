import pandas as pd
import pytest

from tse.demography.join import JOIN_BY_CODE, JOIN_BY_NAME, JOIN_BY_NAME_CORRECTED, join_electorate_population, normalize_name_key
from tse.demography.metrics import add_ratios, flag_excess


def test_normalize_name_key_strips_accents_and_punctuation():
    assert normalize_name_key("Espigão D'Oeste", "RO") == "ESPIGAO D OESTE|RO"


def _population():
    return pd.DataFrame(
        {
            "id_municipio_ibge": [1, 2, 3],
            "nome_municipio": ["Alfa", "Beta", "Gama"],
            "sigla_uf": ["XX"] * 3,
            "pop_total": [1000, 2000, 3000],
            "pop_total_ano": [2026] * 3,
            "pop_16mais": [800, 1600, 2400],
            "pop_16mais_ano": [2022] * 3,
            "chave_nome_uf": ["ALFA|XX", "BETA|XX", "GAMA|XX"],
        }
    )


def test_join_uses_code_then_name_fallback_and_corrects_swapped_codes():
    electorate = pd.DataFrame(
        {"SG_UF": ["XX"] * 3, "CD_MUNICIPIO": [10, 20, 30], "NM_MUNICIPIO": ["ALFA", "BETA", "GAMA"], "QT_APTOS": [700, 1500, 2000], "QT_COMPARECIMENTO": [600, 1200, 1500], "QT_ABSTENCOES": [100, 300, 500], "n_zonas": [1, 1, 1]}
    )
    crosswalk = pd.DataFrame({"id_municipio_tse": [10, 20], "id_municipio_ibge": [1, 3]})
    joined = join_electorate_population(electorate, crosswalk, _population()).set_index("NM_MUNICIPIO")
    assert joined.loc["ALFA", "metodo_join"] == JOIN_BY_CODE
    assert joined.loc["BETA", "metodo_join"] == JOIN_BY_NAME_CORRECTED
    assert joined.loc["BETA", "pop_total"] == 2000
    assert joined.loc["GAMA", "metodo_join"] == JOIN_BY_NAME
    assert joined.loc["GAMA", "pop_16mais"] == 2400


def test_ratios_and_excess_flag():
    frame = pd.DataFrame({"QT_APTOS": [900, 700], "QT_COMPARECIMENTO": [850, 500], "pop_total": [1000, 1000], "pop_16mais": [800, 800]})
    flagged = flag_excess(add_ratios(frame), tolerance=0.0)
    assert flagged["aptos_pop_total"].tolist() == pytest.approx([0.9, 0.7])
    assert flagged["flag_aptos_maior_pop16"].tolist() == [True, False]
    assert flagged["excesso_aptos_pop16"].iloc[0] == 100
    assert flagged["flag_comparecimento_maior_pop16"].tolist() == [True, False]
