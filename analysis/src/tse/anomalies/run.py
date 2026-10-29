from __future__ import annotations

import copy
import json

import numpy as np
import pandas as pd

from tse.anomalies import features, fingerprint, last_digit, nulos_margem, risk, screening, twins, unanimity
from tse.anomalies.outputs import configure_logging, figures_dir, read_optional_table, tables_dir, write_table
from tse.anomalies.stats import jaccard
from tse.config import load_config
from tse.hypotheses import update_status
from tse.io import connect

TOP_N = 200
EXTERNAL_DIVERGENCE_TABLE = "val_inconsistencias"
SWING_TURNO = 2
EXTERNAL_SWING_TABLE = "swing_residuos_flag"
COMMON_CAVEAT = "risk_score ordena unidades para eventual auditoria documental; não é probabilidade de fraude nem de erro."
HYPOTHESES_TABLES = {
    "H11": "anom_comparecimento",
    "H12": "anom_brancos_nulos",
    "H13": "anom_nulos_margem",
    "H23": "anom_unanime_municipio",
    "H25": "anom_gemeas_municipio",
    "H28": "anom_ultimo_digito",
}
SECTION_COLUMNS_PT = {
    "SG_UF": "UF", "CD_MUNICIPIO": "código TSE do município", "NM_MUNICIPIO": "nome do município",
    "NR_ZONA": "zona", "NR_SECAO": "seção", "NR_TURNO": "turno", "CD_CARGO": "cargo (1 Presidente, 6 Dep. Federal)",
}
logger = configure_logging()


def main() -> None:
    config = load_config()
    conn = connect()
    codes = features.discover_special_codes(conn, features.SCOPE_PRESIDENTE, features.CARGO_PRESIDENTE)
    logger.info("códigos branco/nulo descobertos: %s", codes)

    base = _presidential_base(conn, codes, config)
    proportional = _proportional_summaries(conn, config)
    external = _external_findings(base)

    findings_stat = statistical_findings(base, proportional, config, write=True)
    twin_findings = _twins(conn, base, config)
    findings = pd.concat([findings_stat, twin_findings, external["findings"]], ignore_index=True)

    _last_digit(conn, codes, config)
    _fingerprint(conn, base, config)
    _nulos_margem(conn, base, codes, config)

    matrix = _risk_outputs(base, findings, external["available"], config)
    _sensitivity(base, proportional, twin_findings, external, matrix, config)
    _summary(findings, config)
    _export(matrix, findings)
    _update_hypotheses()
    logger.info("anomalies concluído")


def _presidential_base(conn, codes, config) -> pd.DataFrame:
    detail = features.section_detail(conn, features.SCOPE_PRESIDENTE, features.CARGO_PRESIDENTE)
    zones = features.zone_aggregated_sections(conn, features.SCOPE_PRESIDENTE, features.CARGO_PRESIDENTE)
    base = screening.annotate_sections(detail, zones, config)
    summary = features.section_candidate_summary(conn, features.SCOPE_PRESIDENTE, features.CARGO_PRESIDENTE, codes)
    base = base.merge(summary, on=["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO"], how="left")
    base["margem_lider_secao"] = (base["votos_top1"] - base["votos_top2"]) / base["votos_nominais"].replace(0, np.nan)
    logger.info("base Presidente: %d seções×turno", len(base))
    return base


def _proportional_summaries(conn, config) -> pd.DataFrame:
    frames = []
    for scope in features.PROPORTIONAL_SCOPES:
        codes = features.discover_special_codes(conn, scope, features.CARGO_DEPUTADO_FEDERAL)
        detail = features.section_detail(conn, scope, features.CARGO_DEPUTADO_FEDERAL, turno=1)
        zones = features.zone_aggregated_sections(conn, scope, features.CARGO_DEPUTADO_FEDERAL)
        annotated = screening.annotate_sections(detail, zones, config)
        summary = features.section_candidate_summary(conn, scope, features.CARGO_DEPUTADO_FEDERAL, codes, turno=1)
        frames.append(annotated.merge(summary, on=["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO"], how="left"))
    frame = pd.concat(frames, ignore_index=True)
    logger.info("base Deputado Federal SP/MG/RJ: %d seções", len(frame))
    return frame


def statistical_findings(base: pd.DataFrame, proportional: pd.DataFrame, config: dict, write: bool) -> pd.DataFrame:
    turnout = screening.extreme_screen(base, "taxa_comparecimento", risk.FINDING_TURNOUT, config)
    blank_null = screening.extreme_screen(base, "taxa_brancos_nulos", risk.FINDING_BLANK_NULL, config)
    unanimous_sections, unanimous_municipio = _unanimity(pd.concat([base, proportional], ignore_index=True), config)
    if write:
        _write_screen(turnout, "anom_comparecimento", "Comparecimento extremo por seção (Presidente)", ["H11"],
                      "taxa QT_COMPARECIMENTO/QT_APTOS")
        _write_screen(blank_null, "anom_brancos_nulos", "Brancos+nulos extremos por seção (Presidente)", ["H12"],
                      "taxa (QT_VOTOS_BRANCOS+QT_VOTOS_NULOS)/QT_COMPARECIMENTO")
        _write_unanimity(unanimous_sections, unanimous_municipio)
    unanimity_findings = _unanimity_findings(unanimous_sections, unanimous_municipio)
    columns = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO", "CD_CARGO", "finding_type",
               "metric_value", "p_empirico", "q_fdr", "peso_componente"]
    for frame in (turnout, blank_null):
        frame["peso_componente"] = 1.0
    return pd.concat([turnout[columns], blank_null[columns], unanimity_findings[columns]], ignore_index=True)


def _unanimity(sections: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    share = config["thresholds"]["near_unanimous_share"]
    min_votes = config["anomalies"]["min_valid_votes_unanimous"]
    tested = sections.loc[screening.testable_mask(sections, config) & sections["votos_nominais"].notna()]
    flagged = unanimity.flag_near_unanimous(tested, share, min_votes)
    municipio = unanimity.municipio_excess(flagged, share, min_votes)
    flagged = flagged.merge(
        municipio[unanimity.MUNICIPIO_KEYS + ["q_fdr", "p_poisson", "esperado_binomial", "n_quase_unanimes", "share_lider_mun"]],
        on=unanimity.MUNICIPIO_KEYS, how="left",
    )
    return flagged, municipio


def _unanimity_findings(flagged: pd.DataFrame, municipio: pd.DataFrame) -> pd.DataFrame:
    sections = flagged.loc[flagged["quase_unanime"]].copy()
    sections["finding_type"] = risk.FINDING_UNANIMITY
    sections["metric_value"] = sections["share_top1"]
    sections["p_empirico"] = sections["p_poisson"]
    sections["peso_componente"] = 1.0
    return sections


def _twins(conn, base: pd.DataFrame, config: dict) -> pd.DataFrame:
    settings = config["anomalies"]
    pairs, municipio_rows = [], []
    jobs = [(features.SCOPE_PRESIDENTE, features.CARGO_PRESIDENTE, turno, settings["twins_permutations"]) for turno in (1, 2)]
    jobs += [(scope, features.CARGO_DEPUTADO_FEDERAL, 1, settings["twins_permutations_proporcional"]) for scope in features.PROPORTIONAL_SCOPES]
    for scope, cargo, turno, n_perms in jobs:
        vectors = features.section_vote_vectors(conn, scope, cargo, turno, settings["twins_min_comparecimento"])
        observed_pairs = twins.identical_pairs(vectors)
        observed_pairs["CD_CARGO"] = cargo
        long_votes = features.votes_wide_for_municipio(conn, scope, cargo, turno, settings["twins_min_comparecimento"])
        null = twins.permutation_null_by_municipio(twins.municipio_wide_matrices(long_votes), n_perms, config["seed"])
        null["NR_TURNO"], null["CD_CARGO"] = turno, cargo
        null = null.merge(vectors[["CD_MUNICIPIO", "SG_UF", "NM_MUNICIPIO"]].drop_duplicates(), on="CD_MUNICIPIO", how="left")
        pairs.append(observed_pairs)
        municipio_rows.append(null)
        logger.info("gêmeas %s cargo %d turno %d: %d pares idênticos observados", scope, cargo, turno, len(observed_pairs))
    pairs_frame = pd.concat(pairs, ignore_index=True)
    municipio_frame = pd.concat(municipio_rows, ignore_index=True)
    _write_twins(pairs_frame, municipio_frame)
    return _twin_findings(pairs_frame, municipio_frame)


def _twin_findings(pairs: pd.DataFrame, municipio: pd.DataFrame) -> pd.DataFrame:
    if pairs.empty:
        return pd.DataFrame(columns=["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO", "CD_CARGO",
                                     "finding_type", "metric_value", "p_empirico", "q_fdr", "peso_componente"])
    sides = []
    for suffix in ("a", "b"):
        side = pairs[["SG_UF", "CD_MUNICIPIO", "NR_TURNO", "CD_CARGO", f"NR_ZONA_{suffix}", f"NR_SECAO_{suffix}", "QT_COMPARECIMENTO"]]
        sides.append(side.rename(columns={f"NR_ZONA_{suffix}": "NR_ZONA", f"NR_SECAO_{suffix}": "NR_SECAO"}))
    findings = pd.concat(sides, ignore_index=True).drop_duplicates()
    findings = findings.merge(municipio[["CD_MUNICIPIO", "NR_TURNO", "CD_CARGO", "p_permutacao", "q_fdr"]],
                              on=["CD_MUNICIPIO", "NR_TURNO", "CD_CARGO"], how="left")
    findings["finding_type"] = risk.FINDING_TWIN
    findings["metric_value"] = findings["QT_COMPARECIMENTO"].astype(float)
    findings["p_empirico"] = findings["p_permutacao"]
    findings["peso_componente"] = 1.0
    return findings.drop(columns=["QT_COMPARECIMENTO", "p_permutacao"])


def _last_digit(conn, codes: dict, config: dict) -> None:
    settings = config["anomalies"]
    jobs = [(features.SCOPE_PRESIDENTE, features.CARGO_PRESIDENTE, codes)]
    jobs += [(scope, features.CARGO_DEPUTADO_FEDERAL, features.discover_special_codes(conn, scope, features.CARGO_DEPUTADO_FEDERAL))
             for scope in features.PROPORTIONAL_SCOPES]
    frames = []
    for scope, cargo, scope_codes in jobs:
        votes = features.candidate_votes_long(conn, scope, cargo, scope_codes, min(settings["min_count_last_digit"]))
        for minimum in settings["min_count_last_digit"]:
            frame = last_digit.last_digit_by_group(votes[votes["QT_VOTOS"] >= minimum], settings["min_observations_last_digit"], cargo)
            frame["limiar_minimo_votos"] = minimum
            frames.append(frame)
    frame = pd.concat(frames, ignore_index=True)
    frame["q_fdr"] = np.nan
    for _, index in frame.groupby(["NR_TURNO", "CD_CARGO", "limiar_minimo_votos"]).groups.items():
        frame.loc[index, "q_fdr"] = last_digit.benjamini_hochberg(frame.loc[index, "p_valor"].to_numpy())
    write_table(
        frame, "anom_ultimo_digito", "Uniformidade do último dígito de QT_VOTOS por UF × turno × candidato",
        "Qui-quadrado de uniformidade do último dígito das contagens por seção (QT_VOTOS ≥ limiar) para Presidente (BR) e Deputado Federal (SP, MG, RJ).",
        ["H28"], "uf",
        {"SG_UF": "UF", "NR_TURNO": "turno", "CD_CARGO": "cargo", "NR_VOTAVEL": "número do votável", "NM_VOTAVEL": "nome",
         "n_secoes": "seções com QT_VOTOS ≥ limiar", "chi2": "estatística qui-quadrado (9 g.l.)", "p_valor": "p-valor",
         "max_desvio_digito": "maior desvio absoluto de 0,10 entre os dígitos", "digito_mais_frequente": "dígito modal",
         "q_fdr": "q BH dentro de turno × cargo × limiar", "limiar_minimo_votos": "QT_VOTOS mínimo da linha para entrar no teste"},
        "qui-quadrado de uniformidade em {0..9}; BH por turno × cargo × limiar",
        ["Triagem exploratória: a contagem em urna eletrônica não passa por transcrição humana, mecanismo que o teste captura; "
         "desvios não entram no risk_score.", "Contagens pequenas violam a premissa de uniformidade: com limiar 10 o dígito 0 domina porque P(10..19) decresce com o valor (artefato de distribuição, não de digitação); comparar sempre com o limiar 100.",
         "Não foi feito Benford de 1º dígito em agregados (ver STRATEGY §2)."],
    )


def _fingerprint(conn, base: pd.DataFrame, config: dict) -> None:
    winners = fingerprint.national_winner(base.dropna(subset=["nr_votavel_top1"]))
    frames = []
    for turno, nr_votavel in winners.items():
        votes = features.section_votes_for_candidate(conn, features.SCOPE_PRESIDENTE, features.CARGO_PRESIDENTE, turno, nr_votavel)
        frame = base.loc[(base["NR_TURNO"] == turno) & screening.testable_mask(base, config)].merge(
            votes, on=["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO"], how="left")
        frame["share_vencedor"] = frame["votos_vencedor"].fillna(0) / frame["votos_nominais"].replace(0, np.nan)
        frame["nr_votavel_vencedor"] = nr_votavel
        frames.append(frame.dropna(subset=["share_vencedor", "taxa_comparecimento"]))
        fingerprint.write_fingerprint_figure(frames[-1], turno, config["anomalies"]["fingerprint_bins"],
                                             figures_dir() / f"anom_fingerprint_t{turno}.json")
    frame = pd.concat(frames, ignore_index=True)
    stats = fingerprint.fingerprint_stats(frame)
    stats["nr_votavel_vencedor"] = stats["NR_TURNO"].map(winners)
    write_table(
        stats, "anom_fingerprint_uf", "Impressão digital comparecimento × share do vencedor por UF (descritivo)",
        "Estatísticas descritivas (curtose, coeficiente de bimodalidade, correlação) da distribuição bivariada comparecimento × share do vencedor nacional por seção, por UF e turno; heatmaps em outputs/figures/anom_fingerprint_t{1,2}.json.",
        [], "uf",
        {"SG_UF": "UF", "NR_TURNO": "turno", "n_secoes": "seções testáveis", "comparecimento_media": "média da taxa de comparecimento",
         "comparecimento_curtose_excesso": "curtose em excesso", "comparecimento_bimodalidade": "coeficiente de bimodalidade de Sarle (>0,555 sugere bimodalidade)",
         "share_vencedor_media": "média do share do vencedor nacional", "share_vencedor_curtose_excesso": "curtose em excesso",
         "share_vencedor_bimodalidade": "coeficiente de bimodalidade", "correlacao_spearman": "Spearman comparecimento × share",
         "frac_canto_superior": "fração de seções com comparecimento > 0,95 e share > 0,95", "nr_votavel_vencedor": "número do vencedor nacional"},
        "histograma 2D (Klimek et al. 2012) descritivo; sem teste de hipótese",
        ["Voto obrigatório no Brasil comprime o comparecimento em 70–85% e desloca a distribuição; o método foi calibrado para voto facultativo.",
         "Método global, não gera p por seção e não deve ranquear seções.", "Bimodalidade por UF pode refletir heterogeneidade urbano/rural legítima."],
    )


def _nulos_margem(conn, base: pd.DataFrame, codes: dict, config: dict) -> None:
    tested = base.loc[screening.testable_mask(base, config)]
    municipio = nulos_margem.municipio_frame(tested)
    margin = nulos_margem.municipio_margin(None, features.candidate_votes_by_municipio(conn, features.SCOPE_PRESIDENTE, features.CARGO_PRESIDENTE, codes))
    municipio = municipio.merge(margin, on=["SG_UF", "CD_MUNICIPIO", "NR_TURNO"], how="inner")
    municipio["faixa_aptos"] = pd.qcut(municipio["aptos"], 5, labels=[f"q{i}" for i in range(1, 6)]).astype(str)
    rows = [nulos_margem.fixed_effects_regression(municipio, turno) for turno in (1, 2)]
    rows += [nulos_margem.within_municipio_regression(tested, turno) for turno in (1, 2)]
    write_table(
        pd.DataFrame(rows), "anom_nulos_margem", "Associação taxa de nulos × margem do líder (Presidente)",
        "OLS da margem do líder sobre a taxa de nulos com efeitos fixos de UF e porte (município) e versão centrada por município (seção), com erros robustos.",
        ["H13"], "municipio",
        {"NR_TURNO": "turno", "nivel": "unidade da regressão", "n": "observações", "coeficiente_taxa_nulos": "variação da margem (fração) por unidade de taxa de nulos",
         "erro_padrao_hc1": "erro-padrão robusto", "ic95_inferior": "IC 95% inferior", "ic95_superior": "IC 95% superior", "p_valor": "p-valor",
         "r2_parcial": "R² parcial da taxa de nulos", "r2_modelo": "R² do modelo", "controles": "controles"},
        "OLS com efeitos fixos (UF, faixa de aptos) e HC1; seção: variáveis centradas por município com erros agrupados",
        ["Nulos correlacionam com escolaridade, renda e ruralidade, que correlacionam com voto: associação não é causal.",
         "Em urna eletrônica o nulo é digitado pelo eleitor; o mecanismo clássico de anulação pela mesa não existe.",
         "Sem covariáveis socioeconômicas por seção nos arquivos atuais."],
    )
    write_table(
        nulos_margem.spearman_by_uf(municipio), "anom_nulos_margem_uf", "Spearman taxa de nulos × margem do líder por UF (municípios)",
        "Correlação de Spearman entre taxa de nulos e margem do líder nos municípios de cada UF, com IC 95% (transformação de Fisher).",
        ["H13"], "uf",
        {"SG_UF": "UF", "NR_TURNO": "turno", "n_municipios": "municípios", "spearman_rho": "rho de Spearman",
         "ic95_inferior": "IC 95% inferior", "ic95_superior": "IC 95% superior", "p_valor": "p-valor"},
        "Spearman por UF × turno; IC via Fisher z",
        ["Correlação ecológica entre municípios; não descreve eleitores.", "UFs com poucos municípios têm IC largo."],
    )


def _external_findings(base: pd.DataFrame) -> dict:
    available = [risk.COMPONENT_BY_FINDING[risk.FINDING_TURNOUT], risk.COMPONENT_BY_FINDING[risk.FINDING_BLANK_NULL],
                 risk.COMPONENT_BY_FINDING[risk.FINDING_UNANIMITY]]
    frames, notes = [], {}
    for table, finding_type in ((EXTERNAL_DIVERGENCE_TABLE, risk.FINDING_DIVERGENCE), (EXTERNAL_SWING_TABLE, risk.FINDING_SWING)):
        external = read_optional_table(table)
        adapted = _adapt_external(external, finding_type, base) if external is not None else None
        if adapted is None:
            notes[table] = "ausente: componente zerado e peso renormalizado"
            logger.info("tabela externa %s ausente; componente %s indisponível", table, finding_type)
            continue
        frames.append(adapted)
        available.append(risk.COMPONENT_BY_FINDING[finding_type])
        notes[table] = f"lida: {len(adapted)} linhas por seção"
    empty = pd.DataFrame(columns=["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO", "CD_CARGO", "finding_type",
                                  "metric_value", "p_empirico", "q_fdr", "peso_componente"])
    return {"findings": pd.concat(frames, ignore_index=True) if frames else empty, "available": available, "notes": notes}


def _adapt_external(external: pd.DataFrame, finding_type: str, base: pd.DataFrame) -> pd.DataFrame | None:
    external = external.drop(columns=[name for name in external.columns if name.upper() == "SG_UF"])
    if finding_type == risk.FINDING_SWING and not any(name.upper() == "NR_TURNO" for name in external.columns):
        external = external.assign(NR_TURNO=SWING_TURNO)
    columns = {name.upper(): name for name in external.columns}
    required = ["CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO"]
    if not all(name in columns for name in required):
        logger.warning("tabela externa para %s sem chaves de seção %s; ignorada", finding_type, required)
        return None
    frame = external.rename(columns={columns[name]: name for name in columns if name in required + ["Q_FDR", "P_EMPIRICO", "METRIC_VALUE", "CD_CARGO"]})
    frame["CD_CARGO"] = frame.get("CD_CARGO", features.CARGO_PRESIDENTE)
    frame["q_fdr"] = frame["Q_FDR"] if "Q_FDR" in frame else 0.0
    frame["p_empirico"] = frame["P_EMPIRICO"] if "P_EMPIRICO" in frame else frame["q_fdr"]
    frame["metric_value"] = frame["METRIC_VALUE"] if "METRIC_VALUE" in frame else np.nan
    frame["finding_type"] = finding_type
    frame["peso_componente"] = 1.0
    frame = frame.merge(base[["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO"]].drop_duplicates(),
                        on=["CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO"], how="inner")
    return frame[["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO", "CD_CARGO", "finding_type",
                  "metric_value", "p_empirico", "q_fdr", "peso_componente"]]


def _risk_outputs(base: pd.DataFrame, findings: pd.DataFrame, available: list[str], config: dict) -> pd.DataFrame:
    settings = config["anomalies"]
    matrix = risk.build_risk_matrix(base, findings, settings["risk_weights"], available, settings["risk_component_q_cutoff"])
    matrix_out = matrix.copy()
    matrix_out["finding_types"] = matrix_out["finding_types"].map(",".join)
    matrix_out["flags_exclusao"] = matrix_out["flags_exclusao"].map(",".join)
    columns = {
        **SECTION_COLUMNS_PT, "NM_LOCAL_VOTACAO": "nome do local de votação", "n_eleitores": "QT_APTOS da seção",
        "finding_types": "achados com q < limiar (lista)", "classe": "documental | estatistico (forense nunca com os arquivos atuais)",
        "severity": "severidade 1–5 (rubrica FORENSIC_CHECKLIST §3)", "p_empirico_min": "menor percentil empírico entre os achados",
        "q_fdr_min": "menor q BH entre os achados", "risk_score": "score ponderado em [0,1] para ordenar auditoria; não é probabilidade",
        "flags_exclusao": "motivos de desconto", "what_bu_would_resolve": "o que o BU/correspondência resolveria",
        "source_query_id": "origem", "componentes_disponiveis": "componentes com peso ativo", "n_findings_significativos": "nº de achados independentes com q < limiar",
        "tem_flag_exclusao": "há flag de exclusão",
    }
    columns.update({f"comp_{name}": f"componente {name} (1 − q se q < limiar, senão 0)" for name in settings["risk_weights"]})
    caveats = [COMMON_CAVEAT, "Componentes indisponíveis (divergência de fontes, resíduo de virada, demografia) têm peso renormalizado quando a tabela de origem não existe.",
               "Classe forense não é atribuível com os arquivos atuais.", "Seções pequenas, locais especiais e zonas com seções agregadas recebem flags de exclusão e severity 1."]
    write_table(matrix_out, "anom_risk_score", "Matriz de risco por seção (Presidente)",
                "Uma linha por seção × turno com componentes, severity, classe e risk_score consolidado.", list(HYPOTHESES_TABLES), "secao",
                columns, "média ponderada de componentes (1 − q_fdr) com pesos de config.yaml renormalizados aos componentes disponíveis", caveats)
    top = matrix_out.head(TOP_N)
    write_table(top, "anom_top200_secoes", "Top 200 seções por risk_score", "As 200 seções com maior risk_score, com todas as métricas.",
                list(HYPOTHESES_TABLES), "secao", columns, "ordenação por risk_score e severity", caveats)
    ranking = risk.aggregate_to_municipio(matrix)
    write_table(ranking, "anom_mun_ranking", "Ranking de municípios por risk_score médio",
                "Agregação da matriz de risco por município × turno.", list(HYPOTHESES_TABLES), "municipio",
                {**{k: v for k, v in SECTION_COLUMNS_PT.items() if k not in ("NR_ZONA", "NR_SECAO")}, "n_secoes": "seções", "n_eleitores": "aptos",
                 "risk_score_medio": "média do risk_score das seções", "risk_score_max": "máximo", "n_secoes_severity_ge2": "seções com severity ≥ 2",
                 "n_secoes_severity_ge3": "seções com severity ≥ 3", "n_secoes_com_achado": "seções com ≥ 1 achado q < limiar",
                 "q_fdr_min": "menor q", "share_secoes_com_achado": "fração de seções com achado"},
                "média e contagens por município", caveats)
    return matrix


def _sensitivity(base, proportional, twin_findings, external, baseline: pd.DataFrame, config: dict) -> None:
    pct = config["thresholds"]["sensitivity_pct"]
    baseline_top = _top_keys(baseline)
    rows = []
    for direction, factor in (("-", 1 - pct), ("+", 1 + pct)):
        variant = copy.deepcopy(config)
        settings = variant["anomalies"]
        settings["min_aptos_tested"] = int(round(settings["min_aptos_tested"] * factor))
        settings["min_valid_votes_unanimous"] = int(round(settings["min_valid_votes_unanimous"] * factor))
        settings["risk_component_q_cutoff"] = settings["risk_component_q_cutoff"] * factor
        variant["thresholds"]["near_unanimous_share"] = 1 - (1 - variant["thresholds"]["near_unanimous_share"]) * factor
        findings = pd.concat([statistical_findings(base, proportional, variant, write=False), twin_findings, external["findings"]], ignore_index=True)
        matrix = risk.build_risk_matrix(base, findings, settings["risk_weights"], external["available"], settings["risk_component_q_cutoff"])
        rows.append({
            "variante": f"limiares {direction}{int(pct * 100)}%", "min_aptos_tested": settings["min_aptos_tested"],
            "min_valid_votes_unanimous": settings["min_valid_votes_unanimous"], "near_unanimous_share": variant["thresholds"]["near_unanimous_share"],
            "risk_component_q_cutoff": settings["risk_component_q_cutoff"], "n_secoes_severity_ge2": int((matrix["severity"] >= 2).sum()),
            "n_secoes_score_positivo": int((matrix["risk_score"] > 0).sum()), "jaccard_top200_vs_base": jaccard(baseline_top, _top_keys(matrix)),
        })
    rows.insert(0, {"variante": "base", "min_aptos_tested": config["anomalies"]["min_aptos_tested"],
                    "min_valid_votes_unanimous": config["anomalies"]["min_valid_votes_unanimous"],
                    "near_unanimous_share": config["thresholds"]["near_unanimous_share"],
                    "risk_component_q_cutoff": config["anomalies"]["risk_component_q_cutoff"],
                    "n_secoes_severity_ge2": int((baseline["severity"] >= 2).sum()),
                    "n_secoes_score_positivo": int((baseline["risk_score"] > 0).sum()), "jaccard_top200_vs_base": 1.0})
    write_table(pd.DataFrame(rows), "anom_sensibilidade", "Sensibilidade do ranking aos limiares (±20%)",
                "Recalcula a matriz de risco com limiares ±20% e compara o top-200 por Jaccard.", list(HYPOTHESES_TABLES), "secao",
                {"variante": "cenário", "min_aptos_tested": "limiar de aptos", "min_valid_votes_unanimous": "mínimo de votos para unanimidade",
                 "near_unanimous_share": "share mínimo", "risk_component_q_cutoff": "q máximo para componente > 0",
                 "n_secoes_severity_ge2": "seções com severity ≥ 2", "n_secoes_score_positivo": "seções com risk_score > 0",
                 "jaccard_top200_vs_base": "Jaccard do top-200 contra o cenário base"},
                "recomputação completa dos testes estatísticos por cenário", [COMMON_CAVEAT, "Pares gêmeos e componentes externos mantidos fixos entre cenários."])


def _top_keys(matrix: pd.DataFrame) -> list[tuple]:
    return list(matrix.head(TOP_N)[["CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO", "CD_CARGO"]].itertuples(index=False, name=None))


def _summary(findings: pd.DataFrame, config: dict) -> None:
    q_limit = config["thresholds"]["fdr_q"]
    rows = []
    for (finding_type, turno, cargo), group in findings.groupby(["finding_type", "NR_TURNO", "CD_CARGO"]):
        tested = int(group["q_fdr"].notna().sum())
        flagged = int((group["q_fdr"] < q_limit).sum())
        rows.append({"finding_type": finding_type, "NR_TURNO": turno, "CD_CARGO": cargo, "n_testados": tested,
                     "n_flag_q_lt_005": flagged, "falsos_positivos_esperados": q_limit * tested,
                     "share_flag": flagged / tested if tested else np.nan, "excedente_sobre_esperado": flagged - q_limit * tested})
    write_table(pd.DataFrame(rows), "anom_resumo", "Resumo por tipo de achado × turno × cargo",
                "Número de unidades testadas, flags com q < 0,05, falsos positivos esperados sob H0 e excedente.", list(HYPOTHESES_TABLES), "secao",
                {"finding_type": "tipo de achado", "NR_TURNO": "turno", "CD_CARGO": "cargo", "n_testados": "unidades com q calculado",
                 "n_flag_q_lt_005": "unidades com q < 0,05", "falsos_positivos_esperados": "0,05 × n_testados",
                 "share_flag": "fração flagada", "excedente_sobre_esperado": "flags − FP esperados"},
                "contagem após BH por bateria", ["Para unanimidade e gêmeas o q é do município e replicado nas seções; n_testados conta seções flagadas, não municípios.",
                                                "Qualquer unidade individual flagada ainda pode ser acaso."])


def _export(matrix: pd.DataFrame, findings: pd.DataFrame) -> None:
    top = matrix.head(TOP_N).copy()
    keys = ["CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO", "CD_CARGO"]
    detail = findings.merge(top[keys], on=keys, how="inner")
    records = []
    for _, row in top.iterrows():
        mask = (detail[keys] == row[keys].to_numpy()).all(axis=1)
        record = {k: (v.item() if hasattr(v, "item") else v) for k, v in row.items()}
        record["achados"] = [{k: (v.item() if hasattr(v, "item") else v) for k, v in r.items()} for r in detail.loc[mask].to_dict("records")]
        records.append(record)
    payload = {"aviso": COMMON_CAVEAT, "classe_forense": "não atribuível com os arquivos atuais", "n": len(records), "secoes": records}
    (tables_dir() / "anom_export.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def _write_screen(frame: pd.DataFrame, source_id: str, title: str, hypotheses: list[str], metric_pt: str) -> None:
    out = frame.copy()
    out["flags_exclusao"] = out["flags_exclusao"].map(",".join)
    write_table(out, source_id, title, f"Métrica {metric_pt} por seção com z robusto (MAD), percentil empírico bilateral dentro de UF × faixa de aptos × turno e q BH por turno.",
                hypotheses, "secao",
                {**SECTION_COLUMNS_PT, "finding_type": "tipo", "metric_value": metric_pt, "cauda": "alto/baixo", "n_eleitores": "QT_APTOS",
                 "QT_COMPARECIMENTO": "comparecimento", "z_mad": "z robusto", "p_empirico": "percentil empírico bilateral (2·min(F, 1−F))",
                 "p_valor_z": "p bilateral normal do z robusto (base do BH)", "q_fdr": "q BH por turno sobre p_valor_z", "n_referencia": "tamanho do grupo de referência", "reference_group_id": "UF|faixa|turno",
                 "flags_exclusao": "flags", "NM_LOCAL_VOTACAO": "local"},
                "z MAD + percentil empírico por estrato + BH",
                ["Seções com QT_APTOS < limiar, não instaladas ou sem comparecimento foram excluídas do teste.",
                 "p_empirico mínimo possível é 2/n do estrato, o que impede q < 0,05 após BH em ~500 mil testes; por isso o BH usa p_valor_z (normal sobre z MAD), e p_empirico fica como medida descritiva de raridade.",
                 "Extremos em locais especiais (presídio, aldeia, hospital) são esperados; ver flags_exclusao."])


def _write_unanimity(sections: pd.DataFrame, municipio: pd.DataFrame) -> None:
    flagged = sections.loc[sections["quase_unanime"]].copy()
    flagged["flags_exclusao"] = flagged["flags_exclusao"].map(",".join)
    write_table(flagged[["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO", "CD_CARGO", "QT_APTOS", "QT_COMPARECIMENTO",
                         "votos_nominais", "votos_top1", "nr_votavel_top1", "share_top1", "share_lider_mun", "esperado_binomial", "n_quase_unanimes",
                         "p_poisson", "q_fdr", "NM_LOCAL_VOTACAO", "flags_exclusao"]],
                "anom_secao_unanime", "Seções quase unânimes (share ≥ limiar, votos nominais ≥ mínimo)",
                "Lista de seções em que o candidato mais votado recebeu fração ≥ near_unanimous_share dos votos nominais, com nome do local para reconhecimento de presídio/aldeia/hospital.",
                ["H23"], "secao",
                {**SECTION_COLUMNS_PT, "QT_APTOS": "aptos", "QT_COMPARECIMENTO": "comparecimento", "votos_nominais": "votos nominais válidos",
                 "votos_top1": "votos do mais votado", "nr_votavel_top1": "número do mais votado", "share_top1": "fração do mais votado",
                 "share_lider_mun": "fração do líder no município", "esperado_binomial": "nº esperado de seções quase unânimes no município sob binomial",
                 "n_quase_unanimes": "observado no município", "p_poisson": "p de excesso (Poisson) do município", "q_fdr": "q BH por turno (município)",
                 "NM_LOCAL_VOTACAO": "local", "flags_exclusao": "flags"},
                "limiar de share e votos; excesso municipal vs binomial com prevalência do município",
                ["Unanimidade ocorre naturalmente em aldeias, presídios, hospitais e comunidades homogêneas.",
                 "A binomial subestima a dispersão real entre seções do mesmo município; p_poisson é anticonservador."])
    write_table(municipio, "anom_unanime_municipio", "Excesso de seções quase unânimes por município",
                "Observado vs esperado (binomial com prevalência do líder municipal) de seções quase unânimes, com p de Poisson e q BH.",
                ["H23"], "municipio",
                {"SG_UF": "UF", "CD_MUNICIPIO": "município", "NR_TURNO": "turno", "CD_CARGO": "cargo", "n_secoes_testadas": "seções com votos ≥ mínimo",
                 "n_quase_unanimes": "observado", "esperado_binomial": "esperado", "share_lider_mun": "fração do líder", "p_poisson": "p de excesso",
                 "q_fdr": "q BH por turno", "excesso": "observado − esperado"},
                "soma de P(Bin(n_i, p_mun) ≥ limiar·n_i) por município; Poisson para o excesso; BH por turno",
                ["Modelo nulo binomial é anticonservador na presença de heterogeneidade intramunicipal.",
                 "Municípios pequenos com líder muito forte terão esperado alto e excesso pequeno."])


def _write_twins(pairs: pd.DataFrame, municipio: pd.DataFrame) -> None:
    write_table(pairs, "anom_secoes_gemeas", "Pares de seções com vetor de votos idêntico no mesmo município",
                "Pares de seções distintas do mesmo município e turno com vetor completo de votos (incl. brancos/nulos) idêntico e comparecimento ≥ mínimo.",
                ["H25"], "secao",
                {"SG_UF": "UF", "CD_MUNICIPIO": "município", "NM_MUNICIPIO": "nome", "NR_TURNO": "turno", "CD_CARGO": "cargo",
                 "NR_ZONA_a": "zona A", "NR_SECAO_a": "seção A", "NR_ZONA_b": "zona B", "NR_SECAO_b": "seção B",
                 "QT_COMPARECIMENTO": "comparecimento (igual nas duas)", "vetor": "votável:votos;..."},
                "igualdade exata de vetores via hash de string",
                ["Pares idênticos entre seções pequenas são esperados; antes de qualquer leitura, suspeitar de duplicação na exportação."])
    write_table(municipio, "anom_gemeas_municipio", "Pares idênticos observados vs nulo por permutação, por município",
                "Para cada município com ≥ 2 seções elegíveis: pares idênticos observados e distribuição sob permutação independente dos votos de cada votável entre seções.",
                ["H25"], "municipio",
                {"CD_MUNICIPIO": "município", "SG_UF": "UF", "NM_MUNICIPIO": "nome", "NR_TURNO": "turno", "CD_CARGO": "cargo",
                 "n_secoes_elegiveis": "seções com comparecimento ≥ mínimo", "pares_identicos_observados": "observado",
                 "pares_identicos_nulo_media": "média sob permutação", "pares_identicos_nulo_p95": "percentil 95 sob permutação",
                 "p_permutacao": "(1 + #nulo ≥ obs)/(1 + n_perm)", "n_permutacoes": "permutações", "q_fdr": "q BH"},
                "permutação por coluna dentro do município com seed do config",
                ["O nulo permutado quebra a correlação entre candidatos dentro da seção; é um nulo de independência, não de 'seção legítima'.",
                 "Para Deputado Federal usou-se menos permutações (vetor longo torna pares idênticos virtualmente impossíveis sob H0)."])


def _update_hypotheses() -> None:
    for hypothesis_id, table in HYPOTHESES_TABLES.items():
        update_status(hypothesis_id, "computed", script="src/tse/anomalies", table=table)
