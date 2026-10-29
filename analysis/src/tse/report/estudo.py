"""Estudo completo 1º × 2º turno (Presidente 2026) em HTML único.

Uso: python -m tse.report.estudo  ->  outputs/estudo_t1_t2.html
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from tse.config import ANALYSIS_ROOT, load_config
from tse.tables import get_logger, tables_dir

logger = get_logger("estudo")

PLOTLY_JS = Path(__file__).resolve().parent / "estudo_assets" / "vendor" / "plotly-2.35.2.min.js"
INTERIM = ANALYSIS_ROOT / "data" / "interim"
OUT_HTML = ANALYSIS_ROOT / "outputs" / "estudo_t1_t2.html"
PAGES_DIR = ANALYSIS_ROOT.parent / "docs"
PAGES_HTML = PAGES_DIR / "estudo_t1_t2.html"
ESTUDO_DATA_DIR = ANALYSIS_ROOT.parent / "data" / "estudo"
ESTUDO_TABLE_CSVS = (
    "desc_placar_presidente",
    "turnout_uf",
    "swing_baseline_comparacao",
    "desc_vencedor_presidente_uf",
    "swing_fluxo_matriz",
    "swing_residuos_resumo",
    "swing_residuos_flag",
    "swing_saldos_mun",
    "t2_apuracao_10min",
)

ORIGEM_LABEL = {
    "t1_13_lula": "Lula (T1)",
    "t1_22_flavio_bolsonaro": "Flávio (T1)",
    "t1_70_escritor_augusto_cury": "Augusto Cury (T1)",
    "t1_14_renan_santos": "Renan Santos (T1)",
    "t1_55_ronaldo_caiado": "Ronaldo Caiado (T1)",
    "outros_eliminados_t1": "Outros eliminados (T1)",
    "brancos_nulos_t1": "Brancos/nulos (T1)",
    "abstencao_t1": "Abstenção (T1)",
}
DESTINO_LABEL = {
    "t2_13_lula": "Lula (T2)",
    "t2_22_flavio_bolsonaro": "Flávio (T2)",
    "brancos_nulos_t2": "Brancos/nulos (T2)",
    "abstencao_t2": "Abstenção (T2)",
}


def _t(name: str) -> pd.DataFrame:
    return pd.read_parquet(tables_dir() / f"{name}.parquet")


def _clean(obj):
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return None if (np.isnan(f) or np.isinf(f)) else round(f, 6)
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def _records(df: pd.DataFrame) -> list[dict]:
    return _clean(df.to_dict(orient="records"))


def _nacional() -> dict:
    placar = _t("desc_placar_presidente")
    turnout = _t("turnout_uf").groupby("NR_TURNO")[
        ["QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES", "QT_VOTOS_BRANCOS", "QT_VOTOS_NULOS", "QT_VOTOS_VALIDOS"]
    ].sum()
    t1, t2 = turnout.loc[1], turnout.loc[2]
    v = lambda turno, nr: float(placar.loc[(placar.NR_TURNO == turno) & (placar.NR_CANDIDATO == nr), "votos"].sum())  # noqa: E731
    lula1, lula2, fl1, fl2 = v(1, 13), v(2, 13), v(1, 22), v(2, 22)
    elim = float(placar.loc[(placar.NR_TURNO == 1) & (~placar.NR_CANDIDATO.isin([13, 22])), "votos"].sum())
    bn1 = float(t1.QT_VOTOS_BRANCOS + t1.QT_VOTOS_NULOS)
    bn2 = float(t2.QT_VOTOS_BRANCOS + t2.QT_VOTOS_NULOS)
    dcomp = float(t2.QT_COMPARECIMENTO - t1.QT_COMPARECIMENTO)
    pool = elim + (bn1 - bn2) + dcomp
    ganho_l, ganho_f = lula2 - lula1, fl2 - fl1
    margem1, margem2 = lula1 - fl1, lula2 - fl2
    needed = (1 + (fl1 - lula1) / pool) / 2

    sec = _t("swing_saldos_secao")
    d = sec.comp_t2 - sec.comp_t1
    return {
        "placar": _records(placar[["NR_TURNO", "NR_CANDIDATO", "NM_URNA_CANDIDATO", "SG_PARTIDO", "votos", "pct_validos"]]),
        "turnout": {
            "t1": _clean(t1.to_dict()),
            "t2": _clean(t2.to_dict()),
        },
        "lula_t1": lula1,
        "lula_t2": lula2,
        "flavio_t1": fl1,
        "flavio_t2": fl2,
        "ganho_lula": ganho_l,
        "ganho_flavio": ganho_f,
        "margem_t1": margem1,
        "margem_t2": margem2,
        "deslocamento_margem": margem2 - margem1,
        "eliminados_t1": elim,
        "bn_t1": bn1,
        "bn_t2": bn2,
        "queda_bn": bn1 - bn2,
        "delta_comparecimento": dcomp,
        "pool": pool,
        "share_pool_lula": ganho_l / pool,
        "share_pool_flavio": ganho_f / pool,
        "share_pool_necessario_lula": needed,
        "troca_direta_hipotetica": (margem2 - margem1) / 2,
        "retornos_min_secao": float(d.clip(lower=0).sum()),
        "saidas_min_secao": float(-d.clip(upper=0).sum()),
        "secoes_comp_subiu": int((d > 0).sum()),
        "secoes_comp_caiu": int((d < 0).sum()),
        "secoes_comp_igual": int((d == 0).sum()),
        "n_secoes": int(len(sec)),
    }


def _fluxo() -> dict:
    f = _t("swing_fluxo_matriz")
    br = f[f.uf == "BR"].copy()
    br["origem_label"] = br.origem.map(ORIGEM_LABEL).fillna(br.origem)
    br["destino_label"] = br.destino.map(DESTINO_LABEL).fillna(br.destino)
    cols = ["metodo", "origem", "destino", "origem_label", "destino_label", "estimativa", "ci_low", "ci_high",
            "bound_low", "bound_high", "votos_origem", "votos_estimados"]
    return {"br": _records(br[cols])}


def _uf() -> list[dict]:
    base = _t("swing_baseline_comparacao")
    base = base[base.grupo != "BR"]
    tu = _t("turnout_uf")
    t1 = tu[tu.NR_TURNO == 1].set_index("SG_UF")
    t2 = tu[tu.NR_TURNO == 2].set_index("SG_UF")
    plac = _t("desc_vencedor_presidente_uf")
    v1 = plac[plac.NR_TURNO == 1].set_index("SG_UF")
    v2 = plac[plac.NR_TURNO == 2].set_index("SG_UF")
    mun = _t("swing_saldos_mun")
    lead1 = mun.votos_t1_a >= mun.votos_t1_b
    lead2 = mun.votos_t2_a >= mun.votos_t2_b
    mun = mun.assign(virou_lula=(~lead1) & lead2, virou_flavio=lead1 & (~lead2))
    vir = mun.groupby("uf")[["virou_lula", "virou_flavio"]].sum()
    rows = []
    for r in base.itertuples():
        uf = r.grupo
        val1 = float(t1.loc[uf, "QT_VOTOS_VALIDOS"])
        rows.append({
            "uf": uf,
            "lula_t1_pct": r.votos_t1_a / val1 * 100,
            "flavio_t1_pct": r.votos_t1_b / val1 * 100,
            "lula_t2_pct": r.share_a_t2_observada * 100,
            "flavio_t2_pct": (1 - r.share_a_t2_observada) * 100,
            "ganho_lula": r.votos_t2_a - r.votos_t1_a,
            "ganho_flavio": r.votos_t2_b - r.votos_t1_b,
            "baseline_lula_pct": r.share_a_t2_baseline * 100,
            "excesso_pp": r.excesso_a_pp,
            "excesso_votos": r.excesso_a_votos,
            "comp_t1_pct": float(t1.loc[uf, "taxa_comparecimento"]),
            "comp_t2_pct": float(t2.loc[uf, "taxa_comparecimento"]),
            "delta_comp": float(t2.loc[uf, "QT_COMPARECIMENTO"] - t1.loc[uf, "QT_COMPARECIMENTO"]),
            "abst_t1": float(t1.loc[uf, "QT_ABSTENCOES"]),
            "abst_t2": float(t2.loc[uf, "QT_ABSTENCOES"]),
            "vencedor_t1": str(v1.loc[uf, "vencedor_nome"]),
            "vencedor_t2": str(v2.loc[uf, "vencedor_nome"]),
            "mun_virou_lula": int(vir.loc[uf, "virou_lula"]) if uf in vir.index else 0,
            "mun_virou_flavio": int(vir.loc[uf, "virou_flavio"]) if uf in vir.index else 0,
        })
    return _clean(rows)


def _municipios() -> dict:
    m = _t("swing_saldos_mun")
    lead1 = m.votos_t1_a >= m.votos_t1_b
    lead2 = m.votos_t2_a >= m.votos_t2_b
    m = m.assign(
        virada=np.select([(~lead1) & lead2, lead1 & (~lead2)], ["Flávio→Lula", "Lula→Flávio"], "sem virada")
    )
    pts = m[["uf", "nm_municipio", "aptos_t2", "delta_comp_pp", "delta_share_a_pp", "share_a_t2_valid", "virada"]]
    vir = m[m.virada != "sem virada"].sort_values("aptos_t2", ascending=False)
    vir = vir.assign(
        lula_t1=vir.votos_t1_a, flavio_t1=vir.votos_t1_b, lula_t2=vir.votos_t2_a, flavio_t2=vir.votos_t2_b
    )[["uf", "nm_municipio", "virada", "aptos_t2", "lula_t1", "flavio_t1", "lula_t2", "flavio_t2"]]
    return {
        "pontos": _records(pts),
        "viradas": _records(vir),
        "n_flavio_lula": int((m.virada == "Flávio→Lula").sum()),
        "n_lula_flavio": int((m.virada == "Lula→Flávio").sum()),
        "aptos_virados": float(m.loc[m.virada != "sem virada", "aptos_t2"].sum()),
        "quedas_lula": int((m.delta_abs_a < 0).sum()),
        "quedas_flavio": int((m.delta_abs_b < 0).sum()),
        "n_mun": int(len(m)),
    }


def _tipo_local(nome: str) -> str:
    x = str(nome).upper()
    if re.search(r"IND[IÍ]GENA|ALDEIA|TERRA IND", x):
        return "Indígena"
    if "QUILOMB" in x:
        return "Quilombola"
    if re.search(r"POVOADO|S[IÍ]TIO|FAZENDA|ASSENTAMENTO|COMUNIDADE|RIBEIR|ZONA RURAL|LOCALIDADE|AGROVILA|POV\.", x):
        return "Rural/povoado"
    return "Urbano/outros"


def _secoes(con: duckdb.DuckDBPyConnection) -> tuple[pd.DataFrame, dict]:
    s = _t("swing_saldos_secao")
    for c in ["cd_municipio", "nr_zona", "nr_secao"]:
        s[c] = s[c].astype(int)
    elim = [c for c in s.columns if c.startswith("votos_t1_") and c[9:].isdigit()]
    s["val1"] = s.votos_t1_a + s.votos_t1_b + s[elim].sum(axis=1)
    s["val2"] = s.votos_t2_a + s.votos_t2_b
    s = s[s.val2 > 0].copy()
    loc = con.sql(
        f"""select distinct SG_UF uf, CAST(CD_MUNICIPIO AS INT) cd_municipio, CAST(NR_ZONA AS INT) nr_zona,
            CAST(NR_SECAO AS INT) nr_secao, NM_LOCAL_VOTACAO local
            from read_parquet('{INTERIM}/votacao_secao/**/*.parquet', hive_partitioning=1) where NR_TURNO=2"""
    ).df()
    s = s.merge(loc, on=["uf", "cd_municipio", "nr_zona", "nr_secao"], how="left")
    s["tipo"] = s.local.map(_tipo_local)
    s["fb1"] = s.votos_t1_b / s.val1
    s["fb2"] = s.votos_t2_b / s.val2
    s["lu1"] = s.votos_t1_a / s.val1
    s["lu2"] = s.votos_t2_a / s.val2

    def conta(col_share, col_votos):
        return {
            "zero": int((s[col_votos] == 0).sum()),
            "lt5": int((s[col_share] < 0.05).sum()),
            "lt10": int((s[col_share] < 0.10).sum()),
            "lt20": int((s[col_share] < 0.20).sum()),
        }

    low = s[s.fb2 < 0.10]
    zero = s[s.votos_t2_b == 0]
    tipo = (
        pd.DataFrame({
            "todas": s.tipo.value_counts(),
            "lt10": low.tipo.value_counts(),
            "zero": zero.tipo.value_counts(),
        })
        .fillna(0)
        .astype(int)
        .reset_index(names="tipo")
    )
    bins = np.linspace(0, 1, 51)
    hist = {
        "bins": bins[:-1].tolist(),
        "flavio_t1": np.histogram(s.fb1.clip(0, 0.9999), bins)[0].tolist(),
        "flavio_t2": np.histogram(s.fb2.clip(0, 0.9999), bins)[0].tolist(),
        "lula_t1": np.histogram(s.lu1.clip(0, 0.9999), bins)[0].tolist(),
        "lula_t2": np.histogram(s.lu2.clip(0, 0.9999), bins)[0].tolist(),
    }
    top_zero = zero.sort_values("val2", ascending=False).head(40)[
        ["uf", "nm_municipio", "nr_zona", "nr_secao", "local", "tipo", "val2", "votos_t2_a", "votos_t1_b", "val1"]
    ]
    bruscas = s[(s.fb1 >= 0.2) & (s.fb2 < 0.10)][
        ["uf", "nm_municipio", "nr_zona", "nr_secao", "local", "val1", "votos_t1_b", "fb1", "val2", "votos_t2_b", "fb2"]
    ]
    margem = float(s.votos_t2_a.sum() - s.votos_t2_b.sum())
    info = {
        "flavio_t2": conta("fb2", "votos_t2_b"),
        "flavio_t1": conta("fb1", "votos_t1_b"),
        "lula_t2": conta("lu2", "votos_t2_a"),
        "lula_t1": conta("lu1", "votos_t1_a"),
        "lt10_ja_t1": int((low.fb1 < 0.10).sum()),
        "lt10_bruscas": int(len(bruscas)),
        "zero_votos_flavio_t1": float(zero.votos_t1_b.sum()),
        "lt10_lula": float(low.votos_t2_a.sum()),
        "lt10_flavio": float(low.votos_t2_b.sum()),
        "lt10_validos": float(low.val2.sum()),
        "zero_lula": float(zero.votos_t2_a.sum()),
        "margem_sem_lt10": margem - float(low.votos_t2_a.sum() - low.votos_t2_b.sum()),
        "margem_sem_zero": margem - float(zero.votos_t2_a.sum() - zero.votos_t2_b.sum()),
        "lt10_por_uf": _records(low.uf.value_counts().head(15).rename_axis("uf").reset_index(name="n")),
        "tipo": _records(tipo),
        "hist": hist,
        "top_zero": _records(top_zero),
        "bruscas": _records(bruscas),
        "n_secoes": int(len(s)),
    }
    return s, info


def _tempo(con: duckdb.DuckDBPyConnection, s: pd.DataFrame) -> dict:
    t = con.sql(
        f"""select SG_UF uf, CAST(CD_MUNICIPIO AS INT) cd_municipio, CAST(NR_ZONA AS INT) nr_zona,
            CAST(NR_SECAO AS INT) nr_secao,
            min(strptime(DT_RECEBIMENTO_BU_HOR_TSE,'%d/%m/%Y %H:%M:%S')) rec
            from read_parquet('{INTERIM}/detalhe_votacao_secao/**/*.parquet', hive_partitioning=1)
            where NR_TURNO=2 and CD_CARGO=1 group by all"""
    ).df()
    x = s.merge(t, on=["uf", "cd_municipio", "nr_zona", "nr_secao"], how="left").sort_values("rec")
    x["pred_a"] = x.share_a_t1_dupla * x.val2
    x["res"] = x.votos_t2_a - x.pred_a
    ufres = x.groupby("uf").res.sum() / x.groupby("uf").val2.sum()
    x["res_uf"] = x.uf.map(ufres) * x.val2

    m = (
        x.set_index("rec")
        .resample("1min")
        .agg({"uf": "size", "votos_t2_a": "sum", "votos_t2_b": "sum", "val2": "sum"})
        .rename(columns={"uf": "bus"})
    )
    m["cumA"] = m.votos_t2_a.cumsum()
    m["cumB"] = m.votos_t2_b.cumsum()
    m["cumV"] = m.val2.cumsum()
    m = m[m.cumV > 0]
    m["share_lula"] = m.cumA / m.cumV * 100
    m["margem"] = m.cumA - m.cumB
    m["pct_apurado"] = m.cumV / x.val2.sum() * 100
    m = m.reset_index().rename(columns={"rec": "minuto"})

    b = (
        x.set_index("rec")
        .resample("10min")
        .agg({"val2": "sum", "res": "sum", "res_uf": "sum", "uf": "size", "votos_t2_a": "sum"})
        .rename(columns={"uf": "bus"})
    )
    b = b[b.bus > 200]
    b["res_pp"] = b.res / b.val2 * 100
    b["res_ajust_pp"] = (b.res - b.res_uf) / b.val2 * 100
    b["share_bloco"] = b.votos_t2_a / b.val2 * 100
    b = b.reset_index().rename(columns={"rec": "bloco"})

    x["r_pp"] = x.res / x.val2 * 100
    q = x.groupby("uf").rec.rank(pct=True)
    quart = []
    for lo, hi, nome in [(0, 0.25, "1º quarto"), (0.25, 0.5, "2º quarto"), (0.5, 0.75, "3º quarto"), (0.75, 1.0, "4º quarto")]:
        k = x[(q > lo) & (q <= hi)] if lo > 0 else x[q <= hi]
        quart.append({"grupo": nome, "residuo_pp": float(k.res.sum() / k.val2.sum() * 100), "n": int(len(k))})
    h = (x.rec - x.rec.min()).dt.total_seconds() / 3600
    r_dm = x.r_pp - x.groupby("uf").r_pp.transform("mean")
    h_dm = h - h.groupby(x.uf).transform("mean")
    beta = float((x.val2 * r_dm * h_dm).sum() / (x.val2 * h_dm**2).sum())

    lead = m.set_index("minuto")
    neg = lead[lead.margem < 0]
    i_min = lead.margem.idxmin()
    virada = lead[(lead.index > i_min) & (lead.margem > 0)].index[0]
    ordem = (
        x.groupby("uf")
        .agg(mediana=("rec", "median"), A=("votos_t2_a", "sum"), V=("val2", "sum"))
        .assign(share_lula=lambda d: d.A / d.V * 100)
        .sort_values("mediana")
        .reset_index()[["uf", "mediana", "share_lula", "V"]]
    )
    active = m[m.bus > 0]
    zeros = (m.bus == 0)
    runs = (zeros != zeros.shift()).cumsum()
    gaps = []
    for _, g in m[zeros].groupby(runs[zeros]):
        if len(g) >= 10:
            gaps.append({"inicio": g.minuto.min(), "fim": g.minuto.max(), "minutos": int(len(g))})
    n = len(x)
    return _clean({
        "minuto": _records(m[["minuto", "bus", "share_lula", "margem", "pct_apurado"]]),
        "blocos": _records(b[["bloco", "bus", "res_pp", "res_ajust_pp", "share_bloco"]]),
        "quartis": quart,
        "inclinacao_pp_hora": beta,
        "ordem_uf": _records(ordem),
        "gaps": gaps,
        "bus_min_mediana": float(active.bus.median()),
        "bus_min_pico": int(active.bus.max()),
        "bus_min_pico_em": active.loc[active.bus.idxmax(), "minuto"],
        "p50": x.rec.iloc[n // 2],
        "p90": x.rec.iloc[int(n * 0.9)],
        "p99": x.rec.iloc[int(n * 0.99)],
        "ultima": x.rec.max(),
        "primeira": x.rec.min(),
        "min_margem": float(lead.margem.min()),
        "min_margem_em": i_min,
        "min_margem_pct": float(lead.loc[i_min, "pct_apurado"]),
        "virada_em": virada,
        "virada_pct": float(lead.loc[virada, "pct_apurado"]),
        "flavio_frente_inicio": neg.index.min() if len(neg) else None,
    })


def _anomalias() -> dict:
    res = _t("swing_residuos_flag")
    mun = res[(res.nivel == "municipio") & (res.flag)].sort_values("q_fdr").head(15)
    resumo = _t("swing_residuos_resumo")
    tot = resumo.groupby("nivel").agg(n=("n_unidades", "sum"), flag=("n_flag", "sum"), fp=("falsos_positivos_esperados", "sum"))
    return _clean({
        "por_nivel": _records(tot.reset_index()),
        "top_mun": _records(mun[["uf", "nm_municipio", "residuo_pp", "residuo_student", "q_fdr"]]),
    })


def build_payload() -> dict:
    load_config()
    con = duckdb.connect()
    sec, sec_info = _secoes(con)
    payload = {
        "gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "nacional": _nacional(),
        "fluxo": _fluxo(),
        "uf": _uf(),
        "municipios": _municipios(),
        "secoes": sec_info,
        "tempo": _tempo(con, sec),
        "anomalias": _anomalias(),
    }
    return _clean(payload)


def export_estudo_data(payload: dict) -> Path:
    """Pacote enxuto em data/estudo/ (CSVs + secao parquet + payload JSON)."""
    import shutil

    ESTUDO_DATA_DIR.mkdir(parents=True, exist_ok=True)
    td = tables_dir()
    for name in ESTUDO_TABLE_CSVS:
        src_csv = td / f"{name}.csv"
        dst = ESTUDO_DATA_DIR / f"{name}.csv"
        if src_csv.is_file() and src_csv.stat().st_size > 2048:
            shutil.copy2(src_csv, dst)
        else:
            _t(name).to_csv(dst, index=False)
    secao_pq = td / "swing_saldos_secao.parquet"
    if secao_pq.is_file():
        shutil.copy2(secao_pq, ESTUDO_DATA_DIR / "swing_saldos_secao.parquet")
    (ESTUDO_DATA_DIR / "estudo_payload.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    files = sorted(p.name for p in ESTUDO_DATA_DIR.iterdir() if p.is_file())
    (ESTUDO_DATA_DIR / "manifest.json").write_text(
        json.dumps(
            {
                "descricao": "Tabelas e payload do estudo Presidente 2026 (1º × 2º turno).",
                "fonte": "https://dadosabertos.tse.jus.br/dataset/resultados-2026",
                "arquivos": files,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info("estudo data: %s (%.1f MB)", ESTUDO_DATA_DIR, sum(p.stat().st_size for p in ESTUDO_DATA_DIR.iterdir()) / 1e6)
    return ESTUDO_DATA_DIR


def build() -> Path:
    payload = build_payload()
    template = (Path(__file__).resolve().parent / "estudo_assets" / "estudo.html").read_text(encoding="utf-8")
    js = (Path(__file__).resolve().parent / "estudo_assets" / "estudo.js").read_text(encoding="utf-8")
    plotly_js = PLOTLY_JS.read_text(encoding="utf-8")
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = (
        template.replace("__DATA__", data)
        .replace("__JS__", js)
        .replace("__PLOTLY__", plotly_js)
    )
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    PAGES_HTML.write_text(html, encoding="utf-8")
    (PAGES_DIR / ".nojekyll").write_text("", encoding="utf-8")
    export_estudo_data(payload)
    logger.info("estudo: %s e %s (%.1f KB)", OUT_HTML, PAGES_HTML, OUT_HTML.stat().st_size / 1e3)
    return OUT_HTML


def main() -> int:
    print(build())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
