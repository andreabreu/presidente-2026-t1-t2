"""Testes do dashboard interativo (artefatos + payload + JS)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tse.config import ANALYSIS_ROOT, load_config
from tse.report.dashboard import ASSETS_JS, build, build_payload


@pytest.fixture(scope="module")
def payload():
    load_config()
    return build_payload()


@pytest.fixture(scope="module")
def rebuilt(payload):  # noqa: ARG001 — garante payload válido antes do build
    return build()


def test_payload_kpis_and_finalists(payload):
    assert payload["finalists"]["a"]
    assert payload["finalists"]["b"]
    assert payload["finalists"]["a"] != payload["finalists"]["b"]
    k = payload["kpis"]
    assert k["aptos_t1"] > 0 and k["aptos_t2"] > 0
    assert k["comp_t1"] > 0 and k["comp_t2"] > 0
    assert k["abst_t1"] >= 0 and k["abst_t2"] >= 0
    assert k["abst_que_votou_proxy"] >= 0
    assert 0 < k["taxa_comp_t1"] < 1
    assert 0 < k["taxa_comp_t2"] < 1


def test_payload_placar_has_both_turnos(payload):
    turnos = {r["NR_TURNO"] for r in payload["placar"]}
    assert turnos == {1, 2}
    t2 = [r for r in payload["placar"] if r["NR_TURNO"] == 2]
    assert len(t2) >= 2
    assert all(r["votos"] is not None and r["votos"] > 0 for r in t2)


def test_payload_uf_cascade_fields(payload):
    assert len(payload["uf"]) >= 26
    row = payload["uf"][0]
    for col in [
        "SG_UF",
        "taxa_comparecimento_t1",
        "taxa_comparecimento_t2",
        "abstencao_que_votou_proxy",
        "vencedor_t1",
        "vencedor_t2",
        "virada_uf",
    ]:
        assert col in row
    ufs = {r["SG_UF"] for r in payload["uf"]}
    assert "SP" in ufs and "RJ" in ufs and "MG" in ufs


def test_payload_mun_cascade_and_viradas(payload):
    assert len(payload["mun"]) > 1000
    row = payload["mun"][0]
    for col in [
        "uf",
        "cd_municipio",
        "nm_municipio",
        "porte",
        "virada_finalistas",
        "cenario",
        "abstencao_que_votou_proxy",
        "delta_share_a_pp",
        "comp_t1",
        "comp_t2",
    ]:
        assert col in row
    ufs = {r["uf"] for r in payload["mun"]}
    assert "SP" in ufs
    sp = [r for r in payload["mun"] if r["uf"] == "SP"]
    assert len(sp) > 100
    viradas = sum(1 for r in payload["mun"] if r["virada_finalistas"])
    assert viradas > 0
    assert all(r["cenario"] in ("com_virada", "sem_virada") for r in payload["mun"])


def test_mun_codes_unique_per_uf(payload):
    pairs = {(r["uf"], str(r["cd_municipio"])) for r in payload["mun"]}
    assert len(pairs) == len(payload["mun"])


def test_build_writes_external_assets(rebuilt):
    out = ANALYSIS_ROOT / "outputs"
    html = out / "dashboard.html"
    css = out / "dashboard.css"
    js = out / "dashboard.js"
    data_js = out / "dashboard_data.js"
    data_json = out / "dashboard_data.json"
    assert rebuilt == html
    assert html.exists() and css.exists() and js.exists() and data_js.exists() and data_json.exists()
    text = html.read_text(encoding="utf-8")
    assert "plotly-2.35.2.min.js" in text
    assert 'src="dashboard_data.js"' in text
    assert 'src="dashboard.js"' in text
    assert 'href="dashboard.css"' in text
    assert "id=\"cPlacar\"" in text
    assert "id=\"fUF\"" in text and "id=\"fMun\"" in text
    # Não embute payload gigante nem Object spread quebrado por f-string
    assert "window.DASH" not in text
    assert "{...layoutBase}" not in text
    assert len(text) < 50_000


def test_dashboard_js_has_cascade_and_plotly_safe(rebuilt):  # noqa: ARG001
    js = (ANALYSIS_ROOT / "outputs" / "dashboard.js").read_text(encoding="utf-8")
    assert "refreshMunicipioSelect" in js
    assert "munOptionsForUf" in js
    assert "Object.assign" in js
    assert "{...layoutBase}" not in js
    assert "Plotly.newPlot" in js
    assert js.count("Plotly.newPlot") >= 8
    assert "window.__DASH_OK__" in js
    assert ASSETS_JS.exists()


def test_dashboard_data_js_parses(rebuilt):  # noqa: ARG001
    raw = (ANALYSIS_ROOT / "outputs" / "dashboard_data.js").read_text(encoding="utf-8")
    assert raw.startswith("window.DASH = ")
    assert raw.rstrip().endswith(";")
    payload = json.loads(raw[len("window.DASH = ") :].rstrip().rstrip(";"))
    assert "mun" in payload and "uf" in payload and "placar" in payload
    # JSON também deve existir e ser equivalente em chaves
    j = json.loads((ANALYSIS_ROOT / "outputs" / "dashboard_data.json").read_text(encoding="utf-8"))
    assert set(j.keys()) == set(payload.keys())


def test_js_syntax_no_python_fstring_artifacts():
    js = ASSETS_JS.read_text(encoding="utf-8")
    # Artefatos típicos de f-string Python vazando no JS
    assert not re.search(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}", js)
    assert "layoutBase" in js
    assert "function redraw" in js
