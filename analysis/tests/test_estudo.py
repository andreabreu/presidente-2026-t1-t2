"""Testes do estudo HTML 1º × 2º turno."""

from __future__ import annotations

import json
import re

import pytest

from tse.report.estudo import OUT_HTML, PAGES_HTML, PLOTLY_JS, build, build_payload


@pytest.fixture(scope="module")
def payload():
    return build_payload()


def test_aritmetica_fecha(payload):
    n = payload["nacional"]
    assert n["ganho_lula"] + n["ganho_flavio"] == pytest.approx(n["pool"])
    assert n["pool"] == pytest.approx(n["eliminados_t1"] + n["queda_bn"] + n["delta_comparecimento"])
    assert n["deslocamento_margem"] == pytest.approx(n["margem_t2"] - n["margem_t1"])
    assert n["share_pool_lula"] + n["share_pool_flavio"] == pytest.approx(1.0)
    assert n["retornos_min_secao"] - n["saidas_min_secao"] == pytest.approx(n["delta_comparecimento"])


def test_secoes_contagens_coerentes(payload):
    s = payload["secoes"]
    f2 = s["flavio_t2"]
    assert f2["zero"] <= f2["lt5"] <= f2["lt10"] <= f2["lt20"]
    assert s["lt10_ja_t1"] <= f2["lt10"]
    assert sum(r["lt10"] for r in s["tipo"]) == f2["lt10"]
    assert sum(r["todas"] for r in s["tipo"]) == s["n_secoes"]
    assert s["margem_sem_lt10"] < payload["nacional"]["margem_t2"]


def test_tempo_series(payload):
    t = payload["tempo"]
    assert t["minuto"] and t["blocos"]
    assert t["minuto"][-1]["pct_apurado"] == pytest.approx(100.0)
    assert t["minuto"][-1]["margem"] == pytest.approx(payload["nacional"]["margem_t2"], abs=1)
    assert t["gaps"] and t["gaps"][0]["minutos"] >= 100
    assert len(t["quartis"]) == 4


def test_html_gerado(payload):  # noqa: ARG001
    path = build()
    assert path == OUT_HTML
    html = path.read_text(encoding="utf-8")
    assert "__DATA__" not in html and "__JS__" not in html and "__PLOTLY__" not in html
    assert "plotly.js v2.35.2" in html and '<script src="https://cdn.plot.ly' not in html
    m = re.search(r"window\.ESTUDO = (.*?);</script>", html, re.S)
    assert m
    data = json.loads(m.group(1).replace("<\\/", "</"))
    assert set(data) >= {"nacional", "fluxo", "uf", "municipios", "secoes", "tempo", "anomalias"}
    assert "arneiroz" not in data
    assert 'id="arneiroz"' not in html
    assert "Caso: Arneiroz" not in html
    # texto editorial (sem o bundle Plotly nem o JSON de municípios)
    editorial = html.split("window.ESTUDO", 1)[0]
    assert "fraude" not in editorial.lower()
    for chart_id in ["cPlacar", "cPote", "cSankey", "cHist", "cBus", "cRes", "cMunScatter"]:
        assert f'id="{chart_id}"' in html
    assert "{...}" not in html.replace(PLOTLY_JS.read_text(encoding="utf-8"), "")
    assert PAGES_HTML.is_file()
    assert PAGES_HTML.read_text(encoding="utf-8") == html
