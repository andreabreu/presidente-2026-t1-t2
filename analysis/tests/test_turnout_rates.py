import numpy as np
import pandas as pd
import pytest

from tse.turnout.rates import add_rates, distribution_summary, safe_rate, top_and_bottom


def test_safe_rate_handles_zero_denominator():
    result = safe_rate([5, 3], [10, 0])
    assert result[0] == pytest.approx(50.0)
    assert np.isnan(result[1])


def test_add_rates_identity_comparecimento_plus_abstencao():
    frame = pd.DataFrame({"QT_APTOS": [1000], "QT_COMPARECIMENTO": [800], "QT_ABSTENCOES": [200], "QT_VOTOS_BRANCOS": [8], "QT_VOTOS_NULOS": [16], "QT_VOTOS_VALIDOS": [776]})
    rated = add_rates(frame)
    assert rated["taxa_comparecimento"][0] + rated["taxa_abstencao"][0] == pytest.approx(100.0)
    assert rated["taxa_brancos_comp"][0] == pytest.approx(1.0)
    assert rated["taxa_nulos_comp"][0] == pytest.approx(2.0)
    assert rated["taxa_validos_comp"][0] + rated["taxa_brancos_comp"][0] + rated["taxa_nulos_comp"][0] == pytest.approx(100.0)


def test_top_and_bottom_returns_both_extremes():
    frame = pd.DataFrame({"id": list("abcde"), "x": [1.0, 5.0, 3.0, 4.0, 2.0]})
    result = top_and_bottom(frame, "x", 2, ["id"])
    assert result.loc[result["extremo"] == "maior", "id"].tolist() == ["b", "d"]
    assert result.loc[result["extremo"] == "menor", "id"].tolist() == ["a", "e"]
    assert set(result["metrica"]) == {"x"}
    assert "valor" in result.columns


def test_distribution_summary_weighted_mean():
    frame = pd.DataFrame({"x": [10.0, 20.0], "w": [1, 3]})
    summary = distribution_summary(frame, "x", [], "w")
    assert summary["media_ponderada"].iloc[0] == pytest.approx(17.5)
    assert summary["n"].iloc[0] == 2
