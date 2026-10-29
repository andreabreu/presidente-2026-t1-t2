"""Dashboard interativo Plotly: T1/T2, viradas, abstenções, UF/município em cascata."""

from __future__ import annotations

import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from tse.config import ANALYSIS_ROOT, load_config
from tse.tables import get_logger, tables_dir

logger = get_logger("dashboard")

PLOTLY_VENDOR = Path(__file__).resolve().parent / "estudo_assets" / "vendor" / "plotly-2.35.2.min.js"
PLOTLY_LOCAL = "plotly-2.35.2.min.js"
OUTPUT_HTML = "outputs/dashboard.html"
OUTPUT_JSON = "outputs/dashboard_data.json"
OUTPUT_JS = "outputs/dashboard.js"
ASSETS_JS = Path(__file__).resolve().parent / "dashboard_assets" / "dashboard.js"


def _read(source_id: str) -> pd.DataFrame:
    base = tables_dir()
    parquet = base / f"{source_id}.parquet"
    csv = base / f"{source_id}.csv"
    if parquet.exists():
        return pd.read_parquet(parquet)
    if csv.exists():
        return pd.read_csv(csv)
    raise FileNotFoundError(source_id)


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, (bool, int, str)):
        return value
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:  # noqa: BLE001
            return str(value)
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _records(frame: pd.DataFrame, columns: list[str] | None = None) -> list[dict]:
    if columns:
        frame = frame[[c for c in columns if c in frame.columns]].copy()
    out = []
    for row in frame.itertuples(index=False, name=None):
        out.append({frame.columns[i]: _json_safe(row[i]) for i in range(len(frame.columns))})
    return out


def build_payload() -> dict:
    placar = _read("desc_placar_presidente")
    turnout_uf = _read("turnout_uf")
    turnout_mun = _read("turnout_mun")
    swing = _read("swing_saldos_mun")
    vencedor_uf = _read("desc_vencedor_presidente_uf")
    try:
        fluxo = _read("swing_fluxo_matriz")
    except FileNotFoundError:
        fluxo = pd.DataFrame()

    placar_cols = ["NR_TURNO", "NR_CANDIDATO", "NM_URNA_CANDIDATO", "SG_PARTIDO", "votos", "pct_validos", "rank"]
    placar_n = placar[placar_cols].copy()

    t1 = turnout_uf[turnout_uf["NR_TURNO"] == 1].set_index("SG_UF")
    t2 = turnout_uf[turnout_uf["NR_TURNO"] == 2].set_index("SG_UF")
    uf = pd.DataFrame(index=sorted(set(t1.index) | set(t2.index)))
    uf.index.name = "SG_UF"
    for col in [
        "QT_APTOS",
        "QT_COMPARECIMENTO",
        "QT_ABSTENCOES",
        "QT_VOTOS_BRANCOS",
        "QT_VOTOS_NULOS",
        "taxa_comparecimento",
        "taxa_abstencao",
        "taxa_brancos_comp",
        "taxa_nulos_comp",
    ]:
        if col in t1.columns:
            uf[f"{col}_t1"] = t1[col]
            uf[f"{col}_t2"] = t2[col]
    uf["delta_comparecimento"] = uf["QT_COMPARECIMENTO_t2"] - uf["QT_COMPARECIMENTO_t1"]
    uf["delta_abstencao"] = uf["QT_ABSTENCOES_t2"] - uf["QT_ABSTENCOES_t1"]
    uf["abstencao_que_votou_proxy"] = (-uf["delta_abstencao"]).clip(lower=0)
    uf["novos_abstentos_proxy"] = uf["delta_abstencao"].clip(lower=0)
    uf["delta_taxa_comp_pp"] = uf["taxa_comparecimento_t2"] - uf["taxa_comparecimento_t1"]
    uf = uf.reset_index()

    v1 = vencedor_uf[vencedor_uf["NR_TURNO"] == 1][
        ["SG_UF", "vencedor_nome", "vencedor_pct_validos", "margem_pp"]
    ].rename(columns={"vencedor_nome": "vencedor_t1", "vencedor_pct_validos": "pct_t1", "margem_pp": "margem_t1"})
    v2 = vencedor_uf[vencedor_uf["NR_TURNO"] == 2][
        ["SG_UF", "vencedor_nome", "vencedor_pct_validos", "margem_pp"]
    ].rename(columns={"vencedor_nome": "vencedor_t2", "vencedor_pct_validos": "pct_t2", "margem_pp": "margem_t2"})
    uf = uf.merge(v1, on="SG_UF", how="left").merge(v2, on="SG_UF", how="left")
    uf["virada_uf"] = uf["vencedor_t1"].fillna("") != uf["vencedor_t2"].fillna("")

    mun = swing.copy()
    mun["abstencao_t1"] = mun["aptos_t1"] - mun["comp_t1"]
    mun["abstencao_t2"] = mun["aptos_t2"] - mun["comp_t2"]
    mun["delta_abstencao"] = mun["abstencao_t2"] - mun["abstencao_t1"]
    mun["abstencao_que_votou_proxy"] = (-mun["delta_abstencao"]).clip(lower=0)
    mun["novos_abstentos_proxy"] = mun["delta_abstencao"].clip(lower=0)
    mun["lider_t1_finalistas"] = mun.apply(
        lambda r: r["finalista_a"] if r["votos_t1_a"] >= r["votos_t1_b"] else r["finalista_b"],
        axis=1,
    )
    mun["lider_t2_finalistas"] = mun.apply(
        lambda r: r["finalista_a"] if r["votos_t2_a"] >= r["votos_t2_b"] else r["finalista_b"],
        axis=1,
    )
    mun["virada_finalistas"] = mun["lider_t1_finalistas"] != mun["lider_t2_finalistas"]
    mun["cenario"] = mun["virada_finalistas"].map({True: "com_virada", False: "sem_virada"})

    mun_cols = [
        "uf",
        "cd_municipio",
        "nm_municipio",
        "porte",
        "aptos_t1",
        "aptos_t2",
        "comp_t1",
        "comp_t2",
        "abstencao_t1",
        "abstencao_t2",
        "delta_comp",
        "delta_comp_pp",
        "delta_abstencao",
        "abstencao_que_votou_proxy",
        "novos_abstentos_proxy",
        "taxa_comp_t1",
        "taxa_comp_t2",
        "finalista_a",
        "finalista_b",
        "votos_t1_a",
        "votos_t2_a",
        "votos_t1_b",
        "votos_t2_b",
        "delta_abs_a",
        "delta_abs_b",
        "delta_share_a_pp",
        "share_a_t1_dupla",
        "share_a_t2_valid",
        "votos_eliminados_t1",
        "pool_residual",
        "virada_finalistas",
        "cenario",
    ]
    mun = mun[[c for c in mun_cols if c in mun.columns]]

    swing_w = swing.copy()
    swing_w["_w"] = swing_w["delta_share_a_pp"] * swing_w["aptos_t2"]
    agg = swing_w.groupby("uf", as_index=False).agg(
        delta_share_a_pp_med=("delta_share_a_pp", "median"),
        _w_sum=("_w", "sum"),
        aptos_sum=("aptos_t2", "sum"),
        n_mun=("delta_share_a_pp", "count"),
        votos_eliminados=("votos_eliminados_t1", "sum"),
        pool=("pool_residual", "sum"),
        delta_comp_sum=("delta_comp", "sum"),
    )
    agg["delta_share_a_pp_pond"] = agg["_w_sum"] / agg["aptos_sum"].where(agg["aptos_sum"] > 0)
    agg = agg.drop(columns=["_w_sum", "aptos_sum"])
    vir = mun.groupby("uf", as_index=False)["virada_finalistas"].sum().rename(
        columns={"virada_finalistas": "n_mun_com_virada"}
    )
    agg = agg.merge(vir, on="uf", how="left")
    uf = uf.merge(agg.rename(columns={"uf": "SG_UF"}), on="SG_UF", how="left")

    fluxo_nat: list[dict] = []
    if len(fluxo):
        sub = fluxo[fluxo["metodo"] == "baseline_proporcional"].copy() if "metodo" in fluxo.columns else fluxo.copy()
        if "nivel" in sub.columns:
            nat = sub[sub["nivel"].isin(["brasil", "nacional", "BR"])]
            if nat.empty:
                g = sub.groupby(["origem", "destino"], as_index=False).agg(
                    votos_origem=("votos_origem", "sum"),
                    votos_estimados=("votos_estimados", "sum"),
                )
                g["estimativa"] = g["votos_estimados"] / g["votos_origem"].where(g["votos_origem"] > 0)
                fluxo_nat = _records(g)
            else:
                fluxo_nat = _records(nat)
        else:
            fluxo_nat = _records(sub.head(500))

    def _sum_turno(df: pd.DataFrame, turno: int, col: str) -> float:
        return float(df.loc[df["NR_TURNO"] == turno, col].sum())

    kpis = {
        "aptos_t1": _sum_turno(turnout_uf, 1, "QT_APTOS"),
        "aptos_t2": _sum_turno(turnout_uf, 2, "QT_APTOS"),
        "comp_t1": _sum_turno(turnout_uf, 1, "QT_COMPARECIMENTO"),
        "comp_t2": _sum_turno(turnout_uf, 2, "QT_COMPARECIMENTO"),
        "abst_t1": _sum_turno(turnout_uf, 1, "QT_ABSTENCOES"),
        "abst_t2": _sum_turno(turnout_uf, 2, "QT_ABSTENCOES"),
    }
    kpis["abst_que_votou_proxy"] = max(0.0, kpis["abst_t1"] - kpis["abst_t2"])
    kpis["taxa_comp_t1"] = kpis["comp_t1"] / kpis["aptos_t1"] if kpis["aptos_t1"] else None
    kpis["taxa_comp_t2"] = kpis["comp_t2"] / kpis["aptos_t2"] if kpis["aptos_t2"] else None

    finalists = placar[placar["NR_TURNO"] == 2].sort_values("rank").head(2)
    names = {
        "a": str(finalists.iloc[0]["NM_URNA_CANDIDATO"]) if len(finalists) else "A",
        "b": str(finalists.iloc[1]["NM_URNA_CANDIDATO"]) if len(finalists) > 1 else "B",
        "nr_a": int(finalists.iloc[0]["NR_CANDIDATO"]) if len(finalists) else None,
        "nr_b": int(finalists.iloc[1]["NR_CANDIDATO"]) if len(finalists) > 1 else None,
    }

    tm1 = turnout_mun[turnout_mun["NR_TURNO"] == 1][
        ["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "taxa_comparecimento", "taxa_abstencao", "taxa_nulos_comp", "taxa_brancos_comp"]
    ]
    tm2 = turnout_mun[turnout_mun["NR_TURNO"] == 2][
        ["SG_UF", "CD_MUNICIPIO", "taxa_comparecimento", "taxa_abstencao", "taxa_nulos_comp", "taxa_brancos_comp"]
    ]
    tm = tm1.merge(tm2, on=["SG_UF", "CD_MUNICIPIO"], suffixes=("_t1", "_t2"), how="inner")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "finalists": names,
        "kpis": {k: _json_safe(v) for k, v in kpis.items()},
        "placar": _records(placar_n),
        "uf": _records(uf),
        "mun": _records(mun),
        "turnout_mun": _records(tm),
        "fluxo": fluxo_nat,
        "caveats": [
            "Proxy 'abstenção que foi votar' = redução de abstenções entre T1 e T2 (não identifica eleitores).",
            "Virada municipal = troca do líder local entre os dois finalistas do 2º turno.",
            "Transferências A→B são ecológicas (agregadas), não votos individuais.",
        ],
    }


def _html_shell(a: str, b: str) -> str:
    # HTML estático — JS/JSON externos (evita f-string quebrando Plotly)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Dashboard TSE 2026 — Presidente</title>
<script src="{PLOTLY_LOCAL}"></script>
<link rel="stylesheet" href="dashboard.css"/>
</head>
<body>
<header>
  <h1>Dashboard Presidente 2026 — T1 / T2 / Viradas / Abstenções</h1>
  <p>Finalistas 2º turno: <strong>{a}</strong> × <strong>{b}</strong>. Filtros em cascata UF → município. Proxy de “abstenção que votou” = queda de abstenções T1→T2 (agregado).</p>
</header>
<section class="filters">
  <label>Turno view
    <select id="fTurno"><option value="ambos">T1 e T2</option><option value="1">Só T1</option><option value="2">Só T2</option></select>
  </label>
  <label>Cenário virada
    <select id="fCenario"><option value="todos">Todos</option><option value="com_virada">Com virada finalistas</option><option value="sem_virada">Sem virada</option></select>
  </label>
  <label>UF
    <select id="fUF"><option value="">Brasil (todas)</option></select>
  </label>
  <label>Município
    <select id="fMun"><option value="">Todos municípios</option></select>
  </label>
  <label>Busca município
    <input id="fSearch" type="search" placeholder="Digite parte do nome"/>
  </label>
  <label>Porte
    <select id="fPorte"><option value="">Todos</option></select>
  </label>
  <label>Top N
    <select id="fTop"><option>30</option><option>50</option><option selected>80</option><option>150</option><option>300</option></select>
  </label>
  <label>Ordenar por
    <select id="fSort">
      <option value="abstencao_que_votou_proxy">Abstenção→voto (proxy)</option>
      <option value="delta_comp">Δ comparecimento</option>
      <option value="delta_share_a_pp">Δ share finalista A (p.p.)</option>
      <option value="delta_abs_a">Δ votos A</option>
      <option value="taxa_comp_t2">Taxa comparecimento T2</option>
      <option value="abstencao_t1">Abstenção T1</option>
    </select>
  </label>
</section>
<section class="kpis" id="kpis"></section>
<section class="note" id="caveats"></section>
<main class="grid">
  <div class="card"><h2>Placar nacional por turno</h2><div class="chart" id="cPlacar"></div></div>
  <div class="card"><h2>Comparecimento × abstenção por UF</h2><div class="chart" id="cUfTurnout"></div></div>
  <div class="card"><h2>Quem “voltou a votar” (proxy) por UF</h2><div class="chart" id="cUfAbstBack"></div></div>
  <div class="card"><h2>Δ share finalista A (p.p.) por UF</h2><div class="chart" id="cUfSwing"></div></div>
  <div class="card"><h2>Viradas de UF (vencedor T1 ≠ T2)</h2><div class="chart" id="cUfFlip"></div></div>
  <div class="card"><h2>Fluxo ecológico aparente (baseline)</h2><div class="chart" id="cFluxo"></div></div>
  <div class="card full"><h2>Municípios — ranking interativo</h2><div class="chart" id="cMunRank"></div></div>
  <div class="card"><h2>Scatter: Δ comparecimento × Δ share A</h2><div class="chart" id="cScatter"></div></div>
  <div class="card"><h2>Scatter: abstenção T1 × share A no T2</h2><div class="chart" id="cScatter2"></div></div>
  <div class="card full"><h2>Tabela filtrada (municípios)</h2><div class="tblwrap" id="tbl"></div></div>
</main>
<footer>Gerado por <code>python -m tse.dashboard</code>. Sirva via HTTP local (não abra só como file:// se o browser bloquear fetch). Dados: TSE Dados Abertos.</footer>
<script src="dashboard_data.js"></script>
<script src="dashboard.js"></script>
</body>
</html>
"""


CSS = """
:root{--bg:#0b1220;--card:#152238;--line:#2a3b55;--text:#e8eef7;--muted:#93a4bd;--accent:#4da3ff;--ok:#3ecf8e;--warn:#f0b429}
*{box-sizing:border-box}html,body{margin:0;max-width:100%;overflow-x:hidden;font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif;background:var(--bg);color:var(--text)}
header{padding:1rem 1.25rem;border-bottom:1px solid var(--line);background:linear-gradient(120deg,#122038,#0b1220 55%,#1a1430)}
header h1{margin:0;font-size:1.35rem}header p{margin:.35rem 0 0;color:var(--muted)}
.filters{display:flex;flex-wrap:wrap;gap:.6rem;padding:.85rem 1.25rem;border-bottom:1px solid var(--line);position:sticky;top:0;background:#0f1828f2;backdrop-filter:blur(8px);z-index:20;max-width:100%}
.filters label{display:flex;flex-direction:column;gap:.2rem;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;max-width:100%}
.filters select,.filters input{width:180px;max-width:min(180px,42vw);background:#0b1220;border:1px solid var(--line);color:var(--text);padding:.45rem .55rem;border-radius:8px}
.filters #fMun,.filters #fSearch{width:220px;max-width:min(220px,70vw)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:.75rem;padding:1rem 1.25rem}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:.85rem}
.kpi .v{font-size:1.35rem;font-weight:700}.kpi .l{color:var(--muted);font-size:12px;margin-top:.15rem}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem;padding:0 1.25rem 1.25rem}
@media(max-width:1100px){.grid{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:.5rem .5rem .75rem;min-height:360px;max-width:100%;overflow-x:clip}
.card h2{margin:.35rem .5rem .1rem;font-size:.95rem}
.note{margin:0 1.25rem 1rem;padding:.85rem 1rem;border-radius:10px;background:#1c2a18;border:1px solid #355533;color:#cfe8c8;font-size:13px}
.chart{width:100%;max-width:100%;height:320px;position:relative}
.full{grid-column:1/-1}
.full .chart{height:auto;min-height:320px}
table.dt{width:100%;border-collapse:collapse;font-size:12px}
table.dt th,table.dt td{padding:.35rem .45rem;border-bottom:1px solid var(--line);text-align:left}
table.dt th{position:sticky;top:0;background:#1b2b44}
.tblwrap{max-height:360px;overflow:auto;margin:.5rem}
footer{padding:1rem 1.25rem 2rem;color:var(--muted);font-size:12px}
"""


def build() -> Path:
    load_config()
    payload = build_payload()
    out_dir = ANALYSIS_ROOT / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_json = out_dir / "dashboard_data.json"
    out_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    # JS que define window.DASH (sem fetch — funciona em file:// e http://)
    data_js = out_dir / "dashboard_data.js"
    data_js.write_text(
        "window.DASH = " + json.dumps(payload, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )

    out_js = out_dir / "dashboard.js"
    shutil.copyfile(ASSETS_JS, out_js)
    shutil.copyfile(PLOTLY_VENDOR, out_dir / PLOTLY_LOCAL)

    (out_dir / "dashboard.css").write_text(CSS, encoding="utf-8")

    out_html = out_dir / "dashboard.html"
    out_html.write_text(
        _html_shell(payload["finalists"]["a"], payload["finalists"]["b"]),
        encoding="utf-8",
    )
    logger.info(
        "dashboard: %s (html %.1fKB, data.js %.1fMB, mun=%s)",
        out_html,
        out_html.stat().st_size / 1e3,
        data_js.stat().st_size / 1e6,
        len(payload["mun"]),
    )
    return out_html


def main() -> int:
    print(build())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
