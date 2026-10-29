from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from tse.config import ANALYSIS_ROOT, load_config
from tse.hypotheses import update_status
from tse.io import connect

from . import figures
from .balances import (
    assign_porte,
    build_balances,
    destination_counts,
    key_stability_summary,
    origin_counts,
    reference_aptos,
)
from .bounds import BoundSet, aggregate_bound_shares, compute_bound_sets, unit_bounds_long
from .constants import (
    BOOTSTRAP_REPLICATES,
    CARGO_GOVERNADOR,
    CARGO_PRESIDENTE,
    KEY_COLUMNS,
    LEVEL_MUNICIPIO,
    LEVEL_SECAO,
    LEVEL_ZONA,
    METHOD_BASELINE_PROPORCIONAL,
    METHOD_BOUNDS_DUNCAN_DAVIS,
    METHOD_GOODMAN_RESTRITO,
    METHOD_GOODMAN_SIMPLEX,
    METHOD_GOODMAN_WLS,
    MODULE_NAME,
    SCRIPT_NAME,
    NATIONAL_LABEL,
    SCOPE_PRESIDENTE,
    TOP_FLAGGED_ROWS,
    TOP_SECAO_CSV_ROWS,
)
from .data import Contest, describe_contest, governor_runoff_scopes, load_munzona_wide, load_secao_wide
from .ecological import baseline_flow_rows, fit_goodman, proportional_baseline_by_group
from .fdr import benjamini_hochberg, effective_strata, stratified_tests
from .metadata import describe_columns
from .outputs import write_table
from .residuals import fit_residual_model, flag_residuals, flagged_ids, jaccard, summarize_by_uf

log = logging.getLogger(MODULE_NAME)

SENSITIVITY_FACTORS = {"q_menos_20pct": 0.8, "q_mais_20pct": 1.2}
WEIGHT_COLUMN = "comp_t2"
MIN_UNITS_GOODMAN_UF = 10


@dataclass
class RunOptions:
    include_secao: bool = True
    include_governador: bool = True
    include_presidente: bool = True
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES


@dataclass
class Context:
    config: dict
    rng: np.random.Generator
    tables_dir: Path
    figures_dir: Path
    q_threshold: float
    options: RunOptions


def setup_logging() -> None:
    logs_dir = ANALYSIS_ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(logs_dir / f"{MODULE_NAME}.log", encoding="utf-8"), logging.StreamHandler()],
    )


def build_context(options: RunOptions) -> Context:
    config = load_config()
    outputs_dir = config["outputs_dir"]
    return Context(
        config=config,
        rng=np.random.default_rng(config["seed"]),
        tables_dir=outputs_dir / "tables",
        figures_dir=outputs_dir / "figures",
        q_threshold=float(config["thresholds"]["fdr_q"]),
        options=options,
    )


def run(options: RunOptions) -> dict:
    setup_logging()
    context = build_context(options)
    conn = connect()
    report = {"presidente": run_presidente(conn, context) if options.include_presidente else None}
    if options.include_governador:
        report["governador"] = run_governador(conn, context)
    mark_hypotheses_computed(options)
    return report


HYPOTHESIS_TABLES = {
    "H15": "swing_aptos_estabilidade",
    "H16": "swing_saldos_mun",
    "H17": "swing_residuos_flag",
    "H18": "swing_bounds_uf",
    "H19": "swing_saldos_secao",
}
SECAO_ONLY_HYPOTHESES = {"H15", "H19"}


def mark_hypotheses_computed(options: RunOptions) -> None:
    if not options.include_presidente:
        return
    for hypothesis_id, table in HYPOTHESIS_TABLES.items():
        if hypothesis_id in SECAO_ONLY_HYPOTHESES and not options.include_secao:
            continue
        update_status(hypothesis_id, "computed", script=SCRIPT_NAME, table=table)
        log.info("hipótese %s marcada como computed (tabela %s)", hypothesis_id, table)


# ---------------------------------------------------------------- presidente


def run_presidente(conn, context: Context) -> dict:
    contest = describe_contest(conn, CARGO_PRESIDENTE, SCOPE_PRESIDENTE)
    log.info("presidente: finalistas %s, eliminados principais %s", contest.finalists, contest.major_eliminated)
    columns = describe_columns(contest)
    wide_mun = load_munzona_wide(conn, contest, LEVEL_MUNICIPIO)
    wide_zona = load_munzona_wide(conn, contest, LEVEL_ZONA)
    balances = {
        LEVEL_MUNICIPIO: build_balances(wide_mun, contest, LEVEL_MUNICIPIO),
        LEVEL_ZONA: build_balances(wide_zona, contest, LEVEL_ZONA),
    }
    identity_ok = {level: bool(frame["identidade_ok"].all()) for level, frame in balances.items()}
    log.info("identidade contábil: %s", identity_ok)
    write_balances(context, balances[LEVEL_MUNICIPIO], "swing_saldos_mun", LEVEL_MUNICIPIO, contest, columns)
    write_balances(context, balances[LEVEL_ZONA], "swing_saldos_zona", LEVEL_ZONA, contest, columns)

    secao_bounds_by_uf = None
    stability = None
    if context.options.include_secao:
        wide_secao = load_secao_wide(conn, contest)
        stability = key_stability_summary(wide_secao)
        write_table(stability, context.tables_dir, "swing_aptos_estabilidade", "Estabilidade de chaves e aptos por seção entre turnos (Presidente)",
                    "Por UF: seções presentes em um só turno e seções com QT_APTOS diferente entre 1º e 2º turno.", ["H15"], "uf", columns,
                    "Join de detalhe_votacao_secao (scope=BR) por (UF, município, zona, seção) entre turnos.", [])
        balances[LEVEL_SECAO] = add_turnout_change_tests(build_balances(wide_secao, contest, LEVEL_SECAO), context.q_threshold)
        write_balances(context, balances[LEVEL_SECAO], "swing_saldos_secao", LEVEL_SECAO, contest, columns, csv_rows=TOP_SECAO_CSV_ROWS)
        secao_bounds_by_uf = bounds_aggregated(wide_secao, contest, LEVEL_SECAO)
        del wide_secao

    bound_sets, origins_mun, keys_mun = bound_sets_for(wide_mun, contest, LEVEL_MUNICIPIO)
    unit_bounds = pd.concat([unit_bounds_long(b, keys_mun, origins_mun) for b in bound_sets], ignore_index=True)
    write_table(unit_bounds, context.tables_dir, "swing_bounds_mun", "Bounds determinísticos de transferência por município (Presidente)",
                "Para cada município, origem (1º turno) e destino (2º turno): mínimo e máximo de votos/fração compatíveis com os totais marginais.",
                ["H18"], LEVEL_MUNICIPIO, columns, bounds_method_text(), bounds_caveats())
    bounds_uf = bounds_consistency_table(wide_mun, contest, bound_sets, origins_mun, secao_bounds_by_uf)
    write_table(bounds_uf, context.tables_dir, "swing_bounds_uf", "Bounds de transferência agregados por UF e Brasil (Presidente)",
                "Bounds agregados a partir de seções, de municípios e calculados diretamente nos totais da UF; permite verificar coerência entre níveis (H18).",
                ["H18"], "uf", columns, bounds_method_text(), bounds_caveats())

    eco = ecological_tables(wide_mun, contest, context)
    write_table(eco, context.tables_dir, "swing_eco_regressao", "Regressão ecológica (Goodman) da virada por UF e Brasil (Presidente)",
                "Coeficientes de transferência origem→destino estimados por regressão ecológica com unidades = municípios ponderados por comparecimento do 2º turno; IC bootstrap.",
                ["H16", "H17"], LEVEL_MUNICIPIO, columns, goodman_method_text(context), goodman_caveats())
    baseline = baseline_tables(wide_mun, contest)
    write_table(baseline, context.tables_dir, "swing_baseline_comparacao", "Baseline proporcional vs observado por UF (Presidente)",
                "Baseline: finalistas retêm 100% e eliminados/pool se dividem na proporção dos finalistas no 1º turno; compara share observado no 2º turno.",
                ["H16"], "uf", columns, "share_a_t2_baseline = share_a_t1_dupla; excesso = observado - baseline.", ["Baseline é comparador descritivo, não contrafactual causal."])
    flow = flow_matrix(eco, baseline, bounds_uf, contest, origins_mun, wide_mun)
    write_table(flow, context.tables_dir, "swing_fluxo_matriz", "Matriz de fluxo agregado 1º→2º turno com IC e bounds (Presidente)",
                "Estimativas ecológicas (Goodman simplex e WLS), baseline proporcional e bounds determinísticos por origem×destino, por UF e Brasil.",
                ["H16", "H17", "H18"], LEVEL_MUNICIPIO, columns, goodman_method_text(context) + " " + bounds_method_text(), goodman_caveats() + bounds_caveats())

    residual_report = residual_tables(balances, contest, context, "swing_residuos", ["H17", "H19"])
    write_presidente_figures(context, balances, flow, residual_report["flags"])

    return {
        "contest": contest,
        "identity_ok": identity_ok,
        "flow_national": flow[(flow["uf"] == NATIONAL_LABEL)],
        "residual_summary": residual_report["summary"],
        "top_flags": residual_report["top"],
        "sensitivity": residual_report["sensitivity"],
        "stability": stability,
        "baseline_national": baseline[baseline["grupo"] == NATIONAL_LABEL],
    }


def write_balances(context: Context, frame: pd.DataFrame, source_id: str, level: str, contest: Contest, columns: dict, csv_rows: int | None = None) -> None:
    ordered = frame
    if csv_rows is not None and "z_mad_delta_comp" in frame:
        ordered = frame.assign(_abs=frame["z_mad_delta_comp"].abs()).sort_values("_abs", ascending=False).drop(columns="_abs")
    write_table(
        ordered, context.tables_dir, source_id, f"Saldos agregados 1º→2º turno por {level}",
        "Votos por candidato no 1º turno, finalistas no 2º turno, aptos/comparecimento/brancos/nulos nos dois turnos, deltas e pool residual.",
        ["H15", "H16", "H19"] if level == LEVEL_SECAO else ["H16"], level, columns,
        "Agregação DuckDB de votacao_*/detalhe_* por unidade e turno; pool_residual = eliminados + Δ(brancos+nulos) + Δcomparecimento.",
        ["Unidades presentes em apenas um turno são excluídas dos saldos (ver swing_aptos_estabilidade).",
         f"Finalista A = NR {contest.finalist_a} ({contest.candidates[contest.finalist_a]}), B = NR {contest.finalist_b} ({contest.candidates[contest.finalist_b]})."],
        csv_rows=csv_rows,
    )


def add_turnout_change_tests(balances: pd.DataFrame, q_threshold: float) -> pd.DataFrame:
    strata = effective_strata(balances, ["uf", "porte"], ["uf"])
    tests = stratified_tests(balances["delta_comp_pp"], strata)
    balances["z_mad_delta_comp"] = tests["z_mad"]
    balances["p_empirico_delta_comp"] = tests["p_empirico"]
    balances["p_param_delta_comp"] = tests["p_param"]
    balances["q_fdr_delta_comp"] = benjamini_hochberg(tests["p_param"].to_numpy())
    balances["flag_delta_comp"] = balances["q_fdr_delta_comp"] < q_threshold
    return balances


# ---------------------------------------------------------------- bounds


def bound_sets_for(wide: pd.DataFrame, contest: Contest, level: str) -> tuple[list[BoundSet], np.ndarray, pd.DataFrame]:
    both = wide[wide["presenca"] == "ambos"].reset_index(drop=True)
    origins = origin_counts(both, contest)
    destinations = destination_counts(both, contest)
    total = reference_aptos(both).to_numpy()
    sets = compute_bound_sets(
        origins, destinations, total,
        (contest.origin_label(contest.finalist_a), contest.origin_label(contest.finalist_b)),
        (contest.destination_label(contest.finalist_a), contest.destination_label(contest.finalist_b)),
    )
    keys = both[KEY_COLUMNS[level] + [c for c in ("nm_municipio",) if c in both]]
    return sets, origins.to_numpy(float), keys


def bounds_aggregated(wide: pd.DataFrame, contest: Contest, level: str) -> pd.DataFrame:
    sets, origins, keys = bound_sets_for(wide, contest, level)
    groups = keys["uf"].reset_index(drop=True)
    national = pd.Series(NATIONAL_LABEL, index=groups.index)
    frames = []
    for bound_set in sets:
        frames.append(aggregate_bound_shares(bound_set, origins, groups))
        frames.append(aggregate_bound_shares(bound_set, origins, national))
    return pd.concat(frames, ignore_index=True).assign(agregado_de=level)


def bounds_consistency_table(wide_mun, contest, mun_sets, origins_mun, secao_bounds) -> pd.DataFrame:
    keys = wide_mun[wide_mun["presenca"] == "ambos"].reset_index(drop=True)["uf"]
    frames = []
    for bound_set in mun_sets:
        frames.append(aggregate_bound_shares(bound_set, origins_mun, keys).assign(agregado_de=LEVEL_MUNICIPIO))
        frames.append(aggregate_bound_shares(bound_set, origins_mun, pd.Series(NATIONAL_LABEL, index=keys.index)).assign(agregado_de=LEVEL_MUNICIPIO))
    frames.append(direct_uf_bounds(wide_mun, contest))
    if secao_bounds is not None:
        frames.append(secao_bounds)
    table = pd.concat(frames, ignore_index=True).rename(columns={"grupo": "uf"})
    return table.sort_values(["metodo", "agregado_de", "uf", "origem", "destino"]).reset_index(drop=True)


def direct_uf_bounds(wide_mun: pd.DataFrame, contest: Contest) -> pd.DataFrame:
    both = wide_mun[wide_mun["presenca"] == "ambos"]
    numeric = both.select_dtypes("number").columns
    uf_totals = both.groupby("uf")[numeric].sum().reset_index()
    national = uf_totals[numeric].sum().to_frame().T.assign(uf=NATIONAL_LABEL)
    totals = pd.concat([uf_totals, national], ignore_index=True).assign(presenca="ambos")
    sets, origins, keys = bound_sets_for(totals, contest, LEVEL_MUNICIPIO)
    frames = [aggregate_bound_shares(s, origins, keys["uf"].reset_index(drop=True)) for s in sets]
    return pd.concat(frames, ignore_index=True).assign(agregado_de="uf_direto")


def bounds_method_text() -> str:
    return (
        "Duncan–Davis: para cada unidade, origem r e destino d, low = max(0, R_r + C_d − N), high = min(R_r, C_d), "
        "com N = max(aptos T1, aptos T2) e abstenção = N − comparecimento. Variante 'retencao_total' assume que "
        "eleitores de finalistas no 1º turno repetem o voto no 2º (A→A = A1), de modo que o influxo líquido de cada finalista "
        "(C_A − A1) é repartido entre as origens não finalistas; unidades com C_A < A1 são marcadas inviáveis e excluídas da agregação. "
        "Agregação: soma dos limites em votos sobre unidades dividida pela soma dos votos da origem."
    )


def bounds_caveats() -> list[str]:
    return [
        "Bounds Duncan–Davis puros são largos por construção (finalistas grandes); a agregação a partir de unidades menores (seção) os estreita.",
        "A variante de retenção total é uma HIPÓTESE, não um fato; serve de comparador, não de evidência.",
    ]


# ---------------------------------------------------------------- Goodman / baseline / flow


def ecological_tables(wide_mun: pd.DataFrame, contest: Contest, context: Context) -> pd.DataFrame:
    both = wide_mun[wide_mun["presenca"] == "ambos"].reset_index(drop=True)
    frames = [goodman_for_group(both, contest, context, NATIONAL_LABEL)]
    for uf, subset in both.groupby("uf"):
        if len(subset) >= MIN_UNITS_GOODMAN_UF:
            frames.append(goodman_for_group(subset.reset_index(drop=True), contest, context, uf))
    return pd.concat(frames, ignore_index=True)


def goodman_for_group(frame: pd.DataFrame, contest: Contest, context: Context, label: str) -> pd.DataFrame:
    origins = origin_counts(frame, contest)
    destinations = destination_counts(frame, contest)
    total = reference_aptos(frame).to_numpy()
    weights = frame[WEIGHT_COLUMN].to_numpy(float)
    results = []
    for method in (METHOD_GOODMAN_SIMPLEX, METHOD_GOODMAN_WLS):
        result = fit_goodman(origins, destinations, total, weights, method, context.rng, context.options.bootstrap_replicates)
        results.append(result.to_frame().assign(uf=label, nivel=LEVEL_MUNICIPIO))
    log.info("goodman %s: n=%d", label, len(frame))
    return pd.concat(results, ignore_index=True)


def goodman_method_text(context: Context) -> str:
    return (
        "Regressão ecológica de Goodman sem intercepto: share_destino_T2 (sobre N = max aptos) ~ shares de todas as origens T1 "
        "(finalistas, eliminados principais, outros eliminados, brancos+nulos, abstenção), unidades = municípios, pesos = comparecimento T2. "
        f"'{METHOD_GOODMAN_SIMPLEX}': mínimos quadrados ponderados conjuntos com coeficientes em [0,1] e soma por origem = 1 (SLSQP sobre matrizes de Gram); '{METHOD_GOODMAN_WLS}': WLS irrestrito. "
        f"IC 95% por bootstrap de unidades ({context.options.bootstrap_replicates} réplicas, seed {context.config['seed']}). "
        "Variante hierárquica: ajuste separado por UF (heterogeneidade)."
    )


def goodman_caveats() -> list[str]:
    return [
        "Coeficientes fora de [0,1] no WLS irrestrito indicam violação das premissas de Goodman (homogeneidade entre unidades); são reportados, não truncados.",
        "No WLS irrestrito, soma por origem diferente de 1 (soma_linha_origem) é diagnóstico de má especificação; no simplex a soma é 1 por construção.",
        f"UFs com menos de {MIN_UNITS_GOODMAN_UF} municípios (ex.: DF) não têm ajuste por UF.",
        "Candidatos com < 1% dos válidos nacionais foram agrupados em 'outros_eliminados_t1' para evitar colinearidade.",
    ]


def baseline_tables(wide_mun: pd.DataFrame, contest: Contest) -> pd.DataFrame:
    both = wide_mun[wide_mun["presenca"] == "ambos"].reset_index(drop=True)
    by_uf = proportional_baseline_by_group(both, contest, both["uf"])
    national = proportional_baseline_by_group(both, contest, pd.Series(NATIONAL_LABEL, index=both.index))
    return pd.concat([national, by_uf], ignore_index=True)


def flow_matrix(eco, baseline, bounds_uf, contest, origins_mun, wide_mun) -> pd.DataFrame:
    plain_bounds = bounds_uf[(bounds_uf["metodo"] == METHOD_BOUNDS_DUNCAN_DAVIS) & (bounds_uf["agregado_de"] == bounds_uf["agregado_de"].iloc[0])]
    bound_lookup = plain_bounds.set_index(["uf", "origem", "destino"])[["bound_low", "bound_high", "votos_origem"]]
    eco_rows = eco[["uf", "nivel", "metodo", "origem", "destino", "estimativa", "ci_low", "ci_high"]].copy()
    baseline_rows = []
    origins = list(dict.fromkeys(eco["origem"]))
    for row in baseline.itertuples():
        for record in baseline_flow_rows(row._asdict(), contest, origins):
            baseline_rows.append({**record, "uf": row.grupo, "nivel": LEVEL_MUNICIPIO, "ci_low": np.nan, "ci_high": np.nan})
    flow = pd.concat([eco_rows, pd.DataFrame(baseline_rows)], ignore_index=True)
    flow = flow.join(bound_lookup, on=["uf", "origem", "destino"])
    flow["votos_estimados"] = flow["estimativa"] * flow["votos_origem"]
    ordered = ["origem", "destino", "estimativa", "ci_low", "ci_high", "bound_low", "bound_high", "metodo", "nivel", "uf", "votos_origem", "votos_estimados"]
    return flow[ordered].sort_values(["uf", "metodo", "origem", "destino"]).reset_index(drop=True)


# ---------------------------------------------------------------- residuals


def residual_tables(balances: dict[str, pd.DataFrame], contest: Contest, context: Context, prefix: str, hypothesis_ids: list[str]) -> dict:
    columns = describe_columns(contest)
    flags, summaries, sensitivities, model_info = [], [], [], []
    for level, frame in balances.items():
        base_fit = fit_residual_model(frame, contest, level, with_controls=True)
        base = flag_residuals(base_fit, context.q_threshold).assign(nivel=level)
        base["rank"] = base["residuo_student"].abs().rank(ascending=False, method="first").astype(int)
        flags.append(base)
        summaries.append(summarize_by_uf(base, context.q_threshold).assign(nivel=level))
        model_info.append({"nivel": level, "n_parametros": base_fit.n_parameters, "r2": base_fit.r_squared, "n_unidades": len(base)})
        sensitivities.extend(sensitivity_rows(frame, contest, level, base, base_fit, context))
        log.info("residuos %s: n=%d flags=%d r2=%.3f", level, len(base), int(base["flag"].sum()), base_fit.r_squared)
    all_flags = pd.concat(flags, ignore_index=True)
    top = all_flags.sort_values(["nivel", "rank"]).groupby("nivel").head(TOP_FLAGGED_ROWS).reset_index(drop=True)
    summary = pd.concat(summaries, ignore_index=True)
    sensitivity = pd.DataFrame(sensitivities)
    method = (
        "WLS de share_a_t2_valid sobre shares T1 (finalista A, eliminados principais, outros, brancos+nulos; B omitido) + controles "
        "(log aptos, taxa de comparecimento T1, Δcomparecimento pp, efeitos fixos de porte e UF); pesos = comparecimento T2. "
        "Seção: variáveis centradas na média do município (efeito fixo de município absorve UF). Resíduo studentizado interno; "
        "z robusto (mediana/MAD) dentro de UF×porte (estrato < 30 → porte nacional); p bilateral normal; q Benjamini–Hochberg na bateria do nível."
    )
    caveats = [
        "Resíduo extremo = anomalia estatística relativa ao padrão da UF/porte; requer auditoria de BU, não é evidência de irregularidade.",
        "p_empirico é percentil dentro do estrato (uniforme por construção); q_fdr deriva de p_param (z robusto).",
        "Unidades pequenas têm resíduos studentizados mais instáveis apesar da ponderação.",
    ]
    write_table(top, context.tables_dir, f"{prefix}_flag", "Resíduos anômalos da virada (top por nível)",
                f"Top {TOP_FLAGGED_ROWS} unidades por |resíduo studentizado| em cada nível, com p_empirico, q_fdr e effect_size.", hypothesis_ids, "municipio/zona/secao", columns, method, caveats)
    write_table(summary, context.tables_dir, f"{prefix}_resumo", "Resumo de resíduos anômalos por UF e nível",
                "Por UF e nível: unidades, flags q<limiar, falsos positivos esperados e resumo dos resíduos.", hypothesis_ids, "uf", columns, method, caveats)
    write_table(sensitivity, context.tables_dir, f"{prefix}_sensibilidade", "Sensibilidade dos flags de resíduo",
                "Jaccard entre flags da especificação base e variantes (sem controles; q ±20%).", hypothesis_ids, "nivel", columns, method, caveats)
    write_table(pd.DataFrame(model_info), context.tables_dir, f"{prefix}_modelo", "Diagnóstico dos modelos de resíduo", "R² ponderado e número de parâmetros por nível.", hypothesis_ids, "nivel", columns, method, caveats)
    return {"flags": all_flags, "summary": summary, "top": top, "sensitivity": sensitivity}


def sensitivity_rows(frame, contest, level, base, base_fit, context) -> list[dict]:
    base_ids = flagged_ids(base, level)
    rows = []
    no_controls = flag_residuals(fit_residual_model(frame, contest, level, with_controls=False), context.q_threshold)
    rows.append(sensitivity_record(level, "sem_controles", base_ids, flagged_ids(no_controls, level)))
    for name, factor in SENSITIVITY_FACTORS.items():
        variant = flag_residuals(base_fit, context.q_threshold * factor)
        rows.append(sensitivity_record(level, name, base_ids, flagged_ids(variant, level)))
    return rows


def sensitivity_record(level: str, variant: str, base_ids: pd.Index, variant_ids: pd.Index) -> dict:
    return {"nivel": level, "variante": variant, "n_flag_base": len(base_ids), "n_flag_variante": len(variant_ids), "jaccard": jaccard(base_ids, variant_ids)}


# ---------------------------------------------------------------- figures


def write_presidente_figures(context: Context, balances: dict, flow: pd.DataFrame, flags: pd.DataFrame) -> None:
    mun_flags = flags[flags["nivel"] == LEVEL_MUNICIPIO]
    figures.write_figure(figures.residual_histogram(mun_flags, "Resíduos studentizados — municípios (Presidente)"), context.figures_dir / "swing_residuos_hist_mun.json")
    figures.write_figure(figures.scatter_by_uf(balances[LEVEL_MUNICIPIO], "Share do finalista A: 1º turno (dupla) vs 2º turno, por UF"), context.figures_dir / "swing_scatter_t1_t2_uf.json")
    national = flow[(flow["uf"] == NATIONAL_LABEL) & (flow["metodo"] == METHOD_GOODMAN_SIMPLEX)]
    figures.write_figure(figures.flow_sankey(national, "Fluxo agregado estimado 1º→2º turno (Brasil, Goodman simplex; IC no hover)"), context.figures_dir / "swing_sankey_br.json")


# ---------------------------------------------------------------- governador


def run_governador(conn, context: Context) -> dict:
    scopes = governor_runoff_scopes(conn)
    log.info("governador com 2º turno: %s", scopes)
    collected: dict[str, list[pd.DataFrame]] = {k: [] for k in ("saldos_mun", "saldos_zona", "bounds_uf", "eco", "baseline", "fluxo", "flags", "resumo", "sensibilidade")}
    contests = {}
    for scope in scopes:
        contest = describe_contest(conn, CARGO_GOVERNADOR, scope)
        contests[scope] = contest
        wide_mun = load_munzona_wide(conn, contest, LEVEL_MUNICIPIO)
        wide_zona = load_munzona_wide(conn, contest, LEVEL_ZONA)
        balances = {LEVEL_MUNICIPIO: build_balances(wide_mun, contest, LEVEL_MUNICIPIO), LEVEL_ZONA: build_balances(wide_zona, contest, LEVEL_ZONA)}
        collected["saldos_mun"].append(relabel_candidates(balances[LEVEL_MUNICIPIO], contest))
        collected["saldos_zona"].append(relabel_candidates(balances[LEVEL_ZONA], contest))
        eco_level = LEVEL_MUNICIPIO if (wide_mun["presenca"] == "ambos").sum() >= MIN_UNITS_GOODMAN_UF else LEVEL_ZONA
        wide_eco = wide_mun if eco_level == LEVEL_MUNICIPIO else wide_zona
        both = wide_eco[wide_eco["presenca"] == "ambos"].reset_index(drop=True)
        sets, origins, keys = bound_sets_for(wide_eco, contest, eco_level)
        bounds_uf = pd.concat([aggregate_bound_shares(s, origins, keys["uf"].reset_index(drop=True)) for s in sets], ignore_index=True).rename(columns={"grupo": "uf"}).assign(agregado_de=eco_level)
        collected["bounds_uf"].append(bounds_uf)
        eco = goodman_for_group(both, contest, context, scope).assign(nivel=eco_level)
        collected["eco"].append(eco)
        baseline = proportional_baseline_by_group(both, contest, both["uf"])
        collected["baseline"].append(baseline)
        collected["fluxo"].append(flow_matrix(eco, baseline, bounds_uf, contest, origins, wide_eco).assign(nivel=eco_level))
        balances = {level: frame for level, frame in balances.items() if len(frame) >= MIN_UNITS_GOODMAN_UF}
        residual = governor_residuals(balances, contest, context, scope)
        collected["flags"].append(residual["top"])
        collected["resumo"].append(residual["summary"])
        collected["sensibilidade"].append(residual["sensitivity"])
    write_governador_tables(context, collected, contests)
    return {"scopes": scopes, "contests": contests, "resumo": pd.concat(collected["resumo"], ignore_index=True) if scopes else None,
            "fluxo": pd.concat(collected["fluxo"], ignore_index=True) if scopes else None}


def relabel_candidates(balances: pd.DataFrame, contest: Contest) -> pd.DataFrame:
    frame = balances.drop(columns=[f"votos_t1_{nr}" for nr in contest.eliminated], errors="ignore")
    frame["nome_finalista_a"] = contest.candidates[contest.finalist_a]
    frame["nome_finalista_b"] = contest.candidates[contest.finalist_b]
    frame["cargo"] = CARGO_GOVERNADOR
    return frame


def governor_residuals(balances, contest, context, scope) -> dict:
    flags, summaries, sensitivities = [], [], []
    for level, frame in balances.items():
        base_fit = fit_residual_model(frame, contest, level, with_controls=True)
        base = flag_residuals(base_fit, context.q_threshold).assign(nivel=level, scope=scope)
        base["rank"] = base["residuo_student"].abs().rank(ascending=False, method="first").astype(int)
        flags.append(base.sort_values("rank").head(TOP_FLAGGED_ROWS))
        summaries.append(summarize_by_uf(base, context.q_threshold).assign(nivel=level))
        sensitivities.extend([{**r, "scope": scope} for r in sensitivity_rows(frame, contest, level, base, base_fit, context)])
    return {"top": pd.concat(flags), "summary": pd.concat(summaries), "sensitivity": pd.DataFrame(sensitivities)}


def write_governador_tables(context: Context, collected: dict, contests: dict[str, Contest]) -> None:
    if not contests:
        return
    columns = describe_columns()
    columns.update({"nome_finalista_a": "Nome de urna do finalista A", "nome_finalista_b": "Nome de urna do finalista B"})
    finalists_text = "; ".join(f"{uf}: A={c.candidates[c.finalist_a]} (NR {c.finalist_a}), B={c.candidates[c.finalist_b]} (NR {c.finalist_b})" for uf, c in contests.items())
    common = [f"UFs com 2º turno para Governador detectadas nos dados: {', '.join(contests)}.", f"Finalistas: {finalists_text}."]
    specs = {
        "saldos_mun": ("swing_governador_saldos_mun", "Saldos 1º→2º turno Governador por município", LEVEL_MUNICIPIO, ["H16"], "Idem swing_saldos_mun, por UF com 2º turno (scope=UF, CD_CARGO=3)."),
        "saldos_zona": ("swing_governador_saldos_zona", "Saldos 1º→2º turno Governador por zona", LEVEL_ZONA, ["H16"], "Idem swing_saldos_zona."),
        "bounds_uf": ("swing_governador_bounds_uf", "Bounds de transferência Governador por UF", "uf", ["H18"], bounds_method_text()),
        "eco": ("swing_governador_eco_regressao", "Regressão ecológica Governador por UF", LEVEL_MUNICIPIO, ["H16", "H17"], goodman_method_text(context)),
        "baseline": ("swing_governador_baseline_comparacao", "Baseline proporcional Governador por UF", "uf", ["H16"], "share_a_t2_baseline = share_a_t1_dupla."),
        "fluxo": ("swing_governador_fluxo_matriz", "Matriz de fluxo Governador por UF", LEVEL_MUNICIPIO, ["H16", "H17", "H18"], goodman_method_text(context) + " " + bounds_method_text()),
        "flags": ("swing_governador_residuos_flag", "Resíduos anômalos Governador (top por UF e nível)", "municipio/zona", ["H17"], f"Idem swing_residuos_flag, sem efeitos fixos de UF (uma UF por modelo); níveis com menos de {MIN_UNITS_GOODMAN_UF} unidades (DF município) são omitidos e a regressão ecológica usa zonas."),
        "resumo": ("swing_governador_residuos_resumo", "Resumo de resíduos Governador", "uf", ["H17"], "Idem swing_residuos_resumo."),
        "sensibilidade": ("swing_governador_residuos_sensibilidade", "Sensibilidade dos flags Governador", "nivel", ["H17"], "Idem swing_residuos_sensibilidade."),
    }
    for key, (source_id, title, unit, hypotheses, method) in specs.items():
        frame = pd.concat(collected[key], ignore_index=True)
        write_table(frame, context.tables_dir, source_id, title, title + ".", hypotheses, unit, columns, method, common + goodman_caveats() + bounds_caveats())
