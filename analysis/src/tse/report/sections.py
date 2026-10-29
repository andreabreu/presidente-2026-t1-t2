from __future__ import annotations

from .components import (
    CHART_BAR,
    CHART_HBAR,
    CHART_HIST,
    CHART_SCATTER,
    banner,
    bullet_list,
    chart,
    esc,
    figure,
    paragraph,
    section,
    static_table,
    table,
)
from .constants import (
    CARGO_LABELS,
    CARGO_PRESIDENTE,
    ECOLOGICAL_FALLACY_BANNER,
    FORENSIC_CLASS_SENTENCE,
    RISK_SCORE_SENTENCE,
    TURNO_1,
    TURNO_2,
)
from .context import ReportContext
from .prose import (
    AGG_COUNT,
    AGG_RATIO,
    AGG_SUM,
    FMT_DEC2,
    FMT_DEC3,
    FMT_INT,
    FMT_PCT1,
    FMT_PCT2,
    FMT_SHARE_PCT1,
    FMT_SHARE_PCT2,
    FMT_TEXT,
)

CHECK_BALANCE_SECAO = "BS01"
CHECK_DIVERGENCE_ZONA = "DF01_zona"
BR_GROUP = "BR"
GOODMAN_SIMPLEX = "goodman_simplex"
FINDING_COMPARECIMENTO = "comparecimento_extremo"
FINDING_BRANCOS_NULOS = "brancos_nulos_extremo"
SEVERITY_TWO_FINDINGS = 3
SEVERITY_DOCUMENTAL = 4


def _placar_prose(ctx: ReportContext) -> str:
    q = ctx.queries
    src = "desc_placar_presidente"

    def votos(turno: int, rank: int) -> str:
        return q.span(f"Q_DESC_placar_t{turno}_rank{rank}_votos", src, "votos", FMT_INT, {"NR_TURNO": turno, "rank": rank})

    def pct(turno: int, rank: int) -> str:
        return q.span(f"Q_DESC_placar_t{turno}_rank{rank}_pct", src, "pct_validos", FMT_PCT2, {"NR_TURNO": turno, "rank": rank})

    n_cand_t1 = q.span("Q_DESC_placar_t1_n_candidatos", src, "NR_CANDIDATO", FMT_INT, {"NR_TURNO": TURNO_1}, AGG_COUNT)
    first = paragraph(
        f"No 1º turno, {ctx.candidate_name_span('t1_first')} ({ctx.candidate_party_span('t1_first')}) obteve {votos(1, 1)} votos válidos "
        f"({pct(1, 1)} dos válidos) e {ctx.candidate_name_span('t1_second')} ({ctx.candidate_party_span('t1_second')}) obteve {votos(1, 2)} "
        f"({pct(1, 2)}), entre {n_cand_t1} candidatos com votos."
    )
    second = paragraph(
        f"No 2º turno, {ctx.candidate_name_span('a')} ({ctx.candidate_party_span('a')}) obteve {votos(2, 1)} votos ({pct(2, 1)}) e "
        f"{ctx.candidate_name_span('b')} ({ctx.candidate_party_span('b')}) obteve {votos(2, 2)} ({pct(2, 2)}). "
        f"A margem em votos e em pontos percentuais por UF e por município está nas tabelas abaixo."
    )
    return first + second


def _participacao_prose(ctx: ReportContext) -> str:
    q = ctx.queries
    src = "turnout_uf"
    aptos = q.span("Q_DESC_turnout_t1_aptos", src, "QT_APTOS", FMT_INT, {"NR_TURNO": TURNO_1}, AGG_SUM)
    comp_t1 = q.span("Q_DESC_turnout_t1_comparecimento", src, "QT_COMPARECIMENTO/QT_APTOS", FMT_SHARE_PCT2, {"NR_TURNO": TURNO_1}, AGG_RATIO)
    comp_t2 = q.span("Q_DESC_turnout_t2_comparecimento", src, "QT_COMPARECIMENTO/QT_APTOS", FMT_SHARE_PCT2, {"NR_TURNO": TURNO_2}, AGG_RATIO)
    nulos_t1 = q.span("Q_DESC_turnout_t1_nulos_comp", src, "QT_VOTOS_NULOS/QT_COMPARECIMENTO", FMT_SHARE_PCT2, {"NR_TURNO": TURNO_1}, AGG_RATIO)
    brancos_t1 = q.span("Q_DESC_turnout_t1_brancos_comp", src, "QT_VOTOS_BRANCOS/QT_COMPARECIMENTO", FMT_SHARE_PCT2, {"NR_TURNO": TURNO_1}, AGG_RATIO)
    nulos_t2 = q.span("Q_DESC_turnout_t2_nulos_comp", src, "QT_VOTOS_NULOS/QT_COMPARECIMENTO", FMT_SHARE_PCT2, {"NR_TURNO": TURNO_2}, AGG_RATIO)
    mediana = q.span("Q_DESC_turnout_dist_t1_comp_mediana", "turnout_distribuicao", "mediana", FMT_PCT1, {"NR_TURNO": TURNO_1, "metrica": "taxa_comparecimento"})
    p99_nulos = q.span("Q_DESC_turnout_dist_t1_nulos_p99", "turnout_distribuicao", "p99", FMT_PCT2, {"NR_TURNO": TURNO_1, "metrica": "taxa_nulos_comp"})
    return paragraph(
        f"Somando todas as UFs e o exterior, o eleitorado apto no 1º turno foi de {aptos}; o comparecimento foi de {comp_t1} no 1º turno e "
        f"{comp_t2} no 2º. No 1º turno, {brancos_t1} dos comparecimentos foram brancos e {nulos_t1} nulos; no 2º turno os nulos caíram para {nulos_t2}. "
        f"A mediana municipal do comparecimento no 1º turno é {mediana}, e o percentil noventa e nove da taxa de nulos é {p99_nulos}."
    )


def results_tab(ctx: ReportContext) -> str:
    store = ctx.store
    placar = section(
        "Placar nacional — Presidente",
        _placar_prose(ctx)
        + '<div class="grid-2">'
        + chart(CHART_BAR, "desc_placar_presidente", "Votos válidos por candidato — 1º turno", data_x="NM_URNA_CANDIDATO", data_y="votos", data_filter={"NR_TURNO": TURNO_1})
        + chart(CHART_BAR, "desc_placar_presidente", "Votos válidos por candidato — 2º turno", data_x="NM_URNA_CANDIDATO", data_y="votos", data_filter={"NR_TURNO": TURNO_2})
        + "</div>"
        + chart(CHART_HBAR, "desc_vencedor_presidente_uf", "Margem do vencedor por UF (pontos percentuais) — 2º turno", data_x="SG_UF", data_y="margem_pp", data_color="vencedor_nome", data_filter={"NR_TURNO": TURNO_2})
        + table(store, "desc_placar_presidente")
        + table(store, "desc_placar_presidente_uf")
        + table(store, "desc_vencedor_presidente_uf")
        + table(store, "desc_vencedor_presidente_mun"),
        "placar",
    )
    participacao = section(
        "Participação: comparecimento, abstenção, brancos e nulos",
        _participacao_prose(ctx)
        + chart(CHART_HBAR, "turnout_uf", "Taxa de comparecimento por UF", data_x="SG_UF", data_y="taxa_comparecimento", data_filter={"NR_TURNO": TURNO_1})
        + '<div class="grid-2">'
        + chart(CHART_HBAR, "turnout_uf", "Nulos / comparecimento por UF", data_x="SG_UF", data_y="taxa_nulos_comp", data_filter={"NR_TURNO": TURNO_1})
        + chart(CHART_HBAR, "turnout_uf", "Brancos / comparecimento por UF", data_x="SG_UF", data_y="taxa_brancos_comp", data_filter={"NR_TURNO": TURNO_1})
        + "</div><div class='grid-3'>"
        + chart(CHART_HIST, "turnout_mun", "Municípios: taxa de comparecimento", data_x="taxa_comparecimento", data_filter={"NR_TURNO": TURNO_1})
        + chart(CHART_HIST, "turnout_mun", "Municípios: nulos / comparecimento", data_x="taxa_nulos_comp", data_filter={"NR_TURNO": TURNO_1})
        + chart(CHART_HIST, "turnout_mun", "Municípios: brancos / comparecimento", data_x="taxa_brancos_comp", data_filter={"NR_TURNO": TURNO_1})
        + "</div>"
        + table(store, "turnout_outliers", title="Municípios extremos por métrica (aptos acima do mínimo do config)")
        + table(store, "turnout_uf")
        + table(store, "turnout_distribuicao")
        + table(store, "turnout_mun")
        + table(store, "turnout_zona")
        + table(store, "turnout_transito")
        + table(store, "desc_secao_tamanho")
        + table(store, "desc_modelo_urna")
        + banner("Modelo de urna: tabela apenas descritiva. A alocação de modelos não é aleatória (correlaciona com UF e porte); nenhum teste de hipótese é feito aqui.", "warn"),
        "participacao",
    )
    outros = section(
        "Governador e Deputado Federal",
        table(store, "desc_governador_uf")
        + table(store, "desc_placar_governador_uf")
        + table(store, "desc_depfed_partido")
        + table(store, "desc_depfed_top")
        + table(store, "turnout_depfed_uf"),
        "outros-cargos",
    )
    return placar + participacao + outros


def validation_tab(ctx: ReportContext) -> str:
    q = ctx.queries
    store = ctx.store
    src = "val_resumo"
    n_checks = q.span("Q_H01_val_n_checks", src, "check_id", FMT_INT, {}, AGG_COUNT)
    n_clean = q.span("Q_H01_val_n_checks_sem_violacao", src, "check_id", FMT_INT, {"n_violations": 0}, AGG_COUNT)
    bs01_viol = q.span("Q_H01_bs01_n_violations", src, "n_violations", FMT_INT, {"check_id": CHECK_BALANCE_SECAO})
    bs01_rows = q.span("Q_H01_bs01_n_rows_tested", src, "n_rows_tested", FMT_INT, {"check_id": CHECK_BALANCE_SECAO})
    bs01_delta = q.span("Q_H01_bs01_sum_abs_delta", src, "sum_abs_delta", FMT_INT, {"check_id": CHECK_BALANCE_SECAO})
    bs01_rel = q.span("Q_H01_bs01_rel_magnitude", src, "rel_magnitude", FMT_SHARE_PCT2, {"check_id": CHECK_BALANCE_SECAO})
    df01_viol = q.span("Q_H06_df01_zona_n_violations", src, "n_violations", FMT_INT, {"check_id": CHECK_DIVERGENCE_ZONA})
    df01_rows = q.span("Q_H06_df01_zona_n_rows_tested", src, "n_rows_tested", FMT_INT, {"check_id": CHECK_DIVERGENCE_ZONA})
    df01_delta = q.span("Q_H06_df01_zona_sum_abs_delta", src, "sum_abs_delta", FMT_INT, {"check_id": CHECK_DIVERGENCE_ZONA})
    n_inconsist = q.span("Q_H01_val_inconsistencias_n", "val_inconsistencias", "check_id", FMT_INT, {}, AGG_COUNT)
    prose = (
        paragraph(
            f"Foram executados {n_checks} checks de identidade aritmética e agregação sobre os arquivos oficiais; {n_clean} deles não têm nenhuma violação. "
            f"Cada linha de <code>val_resumo</code> é um check; cada violação individual está em <code>val_inconsistencias</code> ({n_inconsist} linhas)."
        )
        + paragraph(
            f"Identidade aptos = comparecimento + abstenções por seção: em {bs01_viol} de {bs01_rows} registros a soma não bate "
            f"(diferença total de {bs01_delta} eleitores, {bs01_rel} do total). Isso indica inconsistência de arquivo, concentrada em seções não instaladas, e pede conferência com o boletim de urna."
        )
        + paragraph(
            f"Divergência entre fontes por zona e candidato: dois arquivos oficiais do TSE informam totais diferentes para a mesma unidade em {df01_viol} de {df01_rows} pares "
            f"({df01_delta} votos). A causa documentada nas notas é critério de publicação (candidaturas excluídas do arquivo por candidato, votos convertidos em nulos técnicos); não dá para concluir mais sem o boletim."
        )
    )
    return section(
        "Validação matemática (Fase 1)",
        prose
        + chart(CHART_HBAR, "val_resumo", "Violações por check (escala log)", data_x="check_id", data_y="n_violations", data_logx=True, data_sort=False)
        + table(store, "val_resumo")
        + table(store, "val_inconsistencias")
        + table(store, "val_divergencia_fontes")
        + table(store, "val_agregacao_niveis")
        + table(store, "val_limites_fisicos")
        + table(store, "val_br_vs_brasil")
        + table(store, "val_balanco_secao")
        + table(store, "val_balanco_munzona")
        + table(store, "val_legenda_partido")
        + table(store, "val_cobertura_cand")
        + table(store, "val_timestamps")
        + table(store, "val_timestamps_geracao")
        + table(store, "val_totalizacao_datas")
        + table(store, "val_tamanho_secao"),
        "validacao",
    )


def demography_tab(ctx: ReportContext) -> str:
    q = ctx.queries
    store = ctx.store
    cobertura = q.span("Q_H20_demo_cobertura_pct", "demo_join_cobertura", "valor", FMT_PCT1, {"indicador": "cobertura_pct"})
    n_mun = q.span("Q_H20_demo_n_municipios", "demo_aptos_pop", "CD_MUNICIPIO", FMT_INT, {}, AGG_COUNT)
    razao = q.span("Q_H20_demo_aptos_pop16_nacional", "demo_aptos_pop_uf", "QT_APTOS/pop_16mais", FMT_DEC3, {}, AGG_RATIO)
    n_flag = q.span("Q_H20_demo_n_flag_aptos_maior_pop16", "demo_aptos_pop", "CD_MUNICIPIO", FMT_INT, {"flag_aptos_maior_pop16": True}, AGG_COUNT)
    n_outliers = q.span("Q_H20_demo_n_outliers_pop16", "demo_outliers", "CD_MUNICIPIO", FMT_INT, {"metrica": "aptos_pop_16mais"}, AGG_COUNT)
    prose = paragraph(
        f"O cruzamento com o IBGE cobre {cobertura} dos {n_mun} municípios com eleitores no 1º turno (exterior excluído). "
        f"Nacionalmente, a razão eleitores aptos / população de dezesseis anos ou mais é {razao}. "
        f"Em {n_flag} municípios há mais eleitores aptos do que população adulta estimada. Causas comuns: eleitores que moram em outro município, "
        f"estimativas populacionais defasadas e inscrições facultativas. Não indica irregularidade por si. "
        f"Dentro de cada estrato UF × porte, {n_outliers} municípios são outliers robustos nessa razão (<code>demo_outliers</code>)."
    )
    return section(
        "Demografia: eleitorado × população IBGE",
        prose
        + chart(CHART_SCATTER, "demo_aptos_pop", "Aptos × população de dezesseis anos ou mais (log-log)", data_x="pop_16mais", data_y="QT_APTOS", data_text="NM_MUNICIPIO", data_color="flag_aptos_maior_pop16", data_logx=True, data_logy=True)
        + chart(CHART_HBAR, "demo_aptos_pop_uf", "Razão aptos / pop. dezesseis ou mais por UF", data_x="SG_UF", data_y="aptos_pop_16mais")
        + figure("fig_demo_aptos_vs_pop16", "Figura estática da Fase 3 (não responde aos filtros)")
        + table(store, "demo_aptos_pop_uf")
        + table(store, "demo_outliers")
        + table(store, "demo_aptos_pop")
        + table(store, "demo_join_cobertura"),
        "demografia",
    )


def swing_tab(ctx: ReportContext) -> str:
    q = ctx.queries
    store = ctx.store
    base = "swing_baseline_comparacao"
    where_br = {"grupo": BR_GROUP}
    a_t1 = q.span("Q_H16_saldo_br_votos_t1_a", base, "votos_t1_a", FMT_INT, where_br)
    a_t2 = q.span("Q_H16_saldo_br_votos_t2_a", base, "votos_t2_a", FMT_INT, where_br)
    b_t1 = q.span("Q_H16_saldo_br_votos_t1_b", base, "votos_t1_b", FMT_INT, where_br)
    b_t2 = q.span("Q_H16_saldo_br_votos_t2_b", base, "votos_t2_b", FMT_INT, where_br)
    share_dupla = q.span("Q_H17_baseline_br_share_a_t1_dupla", base, "share_a_t1_dupla", FMT_SHARE_PCT2, where_br)
    share_obs = q.span("Q_H17_baseline_br_share_a_t2_obs", base, "share_a_t2_observada", FMT_SHARE_PCT2, where_br)
    excesso_pp = q.span("Q_H17_baseline_br_excesso_pp", base, "excesso_a_pp", FMT_DEC2, where_br)
    n_mun = q.span("Q_H16_saldos_mun_n", "swing_saldos_mun", "cd_municipio", FMT_INT, {}, AGG_COUNT)
    n_queda_a = q.span("Q_H16_saldos_mun_queda_a", "swing_saldos_mun", "cd_municipio", FMT_INT, {"delta_abs_a": "< 0"}, AGG_COUNT)
    n_queda_b = q.span("Q_H16_saldos_mun_queda_b", "swing_saldos_mun", "cd_municipio", FMT_INT, {"delta_abs_b": "< 0"}, AGG_COUNT)
    n_viradas = q.span("Q_DESC_mudanca_rank_n_mudou_lider", "desc_mudanca_rank_presidente_mun", "CD_MUNICIPIO", FMT_INT, {"mudou_lider": True}, AGG_COUNT)
    flags_mun = q.span("Q_H18_residuos_flag_mun_n", "swing_residuos_flag", "cd_municipio", FMT_INT, {"nivel": "municipio", "flag": True}, AGG_COUNT)
    flags_sec = q.span("Q_H18_residuos_flag_secao_n", "swing_residuos_flag", "cd_municipio", FMT_INT, {"nivel": "secao", "flag": True}, AGG_COUNT)
    fp_mun = q.span("Q_H18_residuos_resumo_mun_fp", "swing_residuos_resumo", "falsos_positivos_esperados", FMT_DEC2, {"nivel": "municipio"}, AGG_SUM)
    r2_mun = q.span("Q_H18_residuos_modelo_r2_mun", "swing_residuos_modelo", "r2", FMT_DEC3, {"nivel": "municipio"})
    q_fdr = q.config_span("Q_CFG_thresholds_fdr_q", "thresholds.fdr_q", FMT_DEC2)
    a_name, b_name = ctx.candidate_name_span("a"), ctx.candidate_name_span("b")
    prose = (
        paragraph(
            f"Entre os turnos, {a_name} passou de {a_t1} para {a_t2} votos e {b_name} de {b_t1} para {b_t2}. "
            f"Na disputa restrita aos dois finalistas no 1º turno, {a_name} tinha {share_dupla} dos votos; no 2º turno obteve {share_obs} dos válidos, "
            f"{excesso_pp} pontos percentuais acima do que uma repartição proporcional dos votos restantes (baseline) produziria."
        )
        + paragraph(
            f"Dos {n_mun} municípios, {n_queda_a} registraram queda de votos de {a_name} e {n_queda_b} queda de {b_name}; essas quedas devem ser lidas junto com a variação de comparecimento. "
            f"Em {n_viradas} linhas município × candidato o líder municipal mudou entre os turnos (<code>desc_mudanca_rank_presidente_mun</code>)."
        )
        + paragraph(
            f"Resíduos de virada: após controlar porte, comparecimento e composição do 1º turno (R² ponderado {r2_mun} em município), "
            f"{flags_mun} municípios e {flags_sec} seções ficaram fora do padrão do estado com q abaixo de {q_fdr}; "
            f"para municípios, esperamos cerca de {fp_mun} resultados extremos por acaso. Qualquer um deles individualmente ainda pode ser acaso: fica como item a verificar, não como conclusão."
        )
    )
    fluxo = section(
        "Matriz de fluxo agregado A→B com intervalos",
        banner(ECOLOGICAL_FALLACY_BANNER, "warn")
        + paragraph(
            "Leitura: pelos totais, entre o limite inferior e o superior (bounds de Duncan–Davis) dos votos de cada origem podem ter ido para cada destino; "
            "a estimativa pontual vem da regressão ecológica (Goodman simplex) com intervalo bootstrap. É um intervalo sobre grupos de eleitores, não sobre pessoas."
        )
        + figure("swing_sankey_br", "Fluxo agregado estimado 1º→2º turno (Brasil)")
        + table(store, "swing_fluxo_matriz", title="Matriz de fluxo (filtro inicial: Brasil, Goodman simplex)", filter={"uf": BR_GROUP, "metodo": GOODMAN_SIMPLEX})
        + table(store, "swing_eco_regressao")
        + table(store, "swing_bounds_uf")
        + table(store, "swing_bounds_mun")
        + table(store, "swing_baseline_comparacao"),
        "fluxo",
    )
    viradas = section(
        "Top viradas municipais e seccionais",
        figure("swing_scatter_t1_t2_uf", "Share do finalista A por UF: 1º × 2º turno (figura estática)")
        + table(store, "desc_mudanca_rank_presidente_mun", title="Mudança de líder por município (ordenada por |Δ pct válidos|)", filter={"mudou_lider": True})
        + table(store, "swing_saldos_mun", title="Saldos por município (ordenados por |Δ share de A|)")
        + table(store, "swing_saldos_zona")
        + table(store, "swing_saldos_secao", title="Saldos por seção (top por |Δ share de A|; parquet completo em outputs/tables)")
        + table(store, "swing_aptos_estabilidade"),
        "viradas-top",
    )
    residuos = section(
        "Resíduos anômalos da virada (FDR)",
        figure("swing_residuos_hist_mun", "Distribuição dos resíduos municipais (figura estática)")
        + table(store, "swing_residuos_flag")
        + table(store, "swing_residuos_resumo")
        + table(store, "swing_residuos_modelo")
        + table(store, "swing_residuos_sensibilidade"),
        "residuos",
    )
    governador = section(
        "Governador: UFs com 2º turno",
        table(store, "swing_governador_baseline_comparacao")
        + table(store, "swing_governador_fluxo_matriz")
        + table(store, "swing_governador_eco_regressao")
        + table(store, "swing_governador_bounds_uf")
        + table(store, "swing_governador_residuos_flag")
        + table(store, "swing_governador_residuos_resumo")
        + table(store, "swing_governador_saldos_mun")
        + table(store, "swing_governador_saldos_zona")
        + table(store, "swing_governador_residuos_sensibilidade"),
        "governador",
    )
    return section("Virada 1º→2º turno (Fase 4)", prose, "viradas") + fluxo + viradas + residuos + governador


def anomalies_tab(ctx: ReportContext) -> str:
    q = ctx.queries
    store = ctx.store
    resumo = "anom_resumo"
    where_comp_t1 = {"finding_type": FINDING_COMPARECIMENTO, "NR_TURNO": TURNO_1, "CD_CARGO": CARGO_PRESIDENTE}
    n_test = q.span("Q_H11_anom_comp_t1_n_testados", resumo, "n_testados", FMT_INT, where_comp_t1)
    n_flag = q.span("Q_H11_anom_comp_t1_n_flag", resumo, "n_flag_q_lt_005", FMT_INT, where_comp_t1)
    fp = q.span("Q_H11_anom_comp_t1_fp_esperados", resumo, "falsos_positivos_esperados", FMT_INT, where_comp_t1)
    n_unanime = q.span("Q_H23_anom_secao_unanime_n", "anom_secao_unanime", "NR_SECAO", FMT_INT, {}, AGG_COUNT)
    share_cfg = q.config_span("Q_CFG_near_unanimous_share", "thresholds.near_unanimous_share", FMT_DEC2)
    min_votes_cfg = q.config_span("Q_CFG_min_votes_unanimous", "thresholds.min_votes_unanimous", FMT_INT)
    sev3 = q.span("Q_H11_risk_n_severity3", "anom_risk_score", "severity", FMT_INT, {"severity": SEVERITY_TWO_FINDINGS}, AGG_COUNT)
    sev4 = q.span("Q_H11_risk_n_severity4", "anom_risk_score", "severity", FMT_INT, {"severity": SEVERITY_DOCUMENTAL}, AGG_COUNT)
    n_total = q.span("Q_H11_risk_n_total", "anom_risk_score", "severity", FMT_INT, {}, AGG_COUNT)
    n_forense = q.span("Q_H11_risk_n_forense", "anom_risk_score", "severity", FMT_INT, {"classe": "forense"}, AGG_COUNT)
    coef_t1 = q.span("Q_H13_nulos_margem_mun_t1_coef", "anom_nulos_margem", "coeficiente_taxa_nulos", FMT_DEC2, {"NR_TURNO": TURNO_1, "nivel": "municipio"})
    ic_lo = q.span("Q_H13_nulos_margem_mun_t1_ic_lo", "anom_nulos_margem", "ic95_inferior", FMT_DEC2, {"NR_TURNO": TURNO_1, "nivel": "municipio"})
    ic_hi = q.span("Q_H13_nulos_margem_mun_t1_ic_hi", "anom_nulos_margem", "ic95_superior", FMT_DEC2, {"NR_TURNO": TURNO_1, "nivel": "municipio"})
    gemeas_obs = q.span("Q_H25_gemeas_t2_pares_obs", "anom_gemeas_municipio", "pares_identicos_observados", FMT_INT, {"NR_TURNO": TURNO_2, "CD_CARGO": CARGO_PRESIDENTE}, AGG_SUM)
    gemeas_nulo = q.span("Q_H25_gemeas_t2_pares_nulo", "anom_gemeas_municipio", "pares_identicos_nulo_media", FMT_INT, {"NR_TURNO": TURNO_2, "CD_CARGO": CARGO_PRESIDENTE}, AGG_SUM)
    prose = (
        paragraph(
            f"Comparecimento extremo (1º turno, Presidente): ao testar {n_test} seções, esperamos cerca de {fp} resultados extremos por acaso ao nível nominal; "
            f"encontramos {n_flag} com q abaixo do limiar após correção de Benjamini–Hochberg. Os excedentes merecem olhar mais atento, mas qualquer um deles individualmente ainda pode ser acaso."
        )
        + paragraph(
            f"{n_unanime} seções registraram quase todos os votos (share igual ou acima de {share_cfg}, com pelo menos {min_votes_cfg} votos nominais) para um único candidato. "
            f"Isso ocorre naturalmente em localidades pequenas e homogêneas; listamos as de maior tamanho para conferência."
        )
        + paragraph(
            f"Nulos × margem (município, 1º turno): coeficiente {coef_t1} (IC {ic_lo} a {ic_hi}); municípios com mais nulos tendem a ter margem do líder ligeiramente menor. "
            f"A associação é fraca e tem várias explicações possíveis (perfil do eleitorado, voto de protesto)."
        )
        + paragraph(
            f"Seções gêmeas (2º turno, Presidente): {gemeas_obs} pares com vetor de votos idêntico contra {gemeas_nulo} esperados por permutação dentro do município; compatível com coincidência em vetores curtos."
        )
        + paragraph(
            f"Matriz de risco: {n_total} seções × turno avaliadas; {sev3} com severidade três (duas ou mais anomalias independentes) e {sev4} com severidade quatro (inconsistência documental). "
            f"Linhas com classe forense: {n_forense}. {FORENSIC_CLASS_SENTENCE}"
        )
    )
    return (
        section(
            "Ranking de anomalias e matriz de risco (Fase 5)",
            banner(f"<strong>{RISK_SCORE_SENTENCE}</strong> Severidade igual ou acima de quatro nunca decorre só de teste estatístico.", "warn")
            + prose
            + chart(CHART_BAR, resumo, "Flags com q abaixo do limiar por tipo de achado e turno", data_x="finding_type", data_y="n_flag_q_lt_005", data_series="NR_TURNO")
            + table(store, "anom_top200_secoes", title="Top seções por risk_score (fila de auditoria documental)")
            + table(store, "anom_risk_score", title="Matriz de risco por seção (top por risk_score; tabela completa em outputs/tables)")
            + table(store, "anom_mun_ranking")
            + table(store, "anom_resumo")
            + table(store, "anom_sensibilidade"),
            "anomalias",
        )
        + section(
            "Componentes",
            table(store, "anom_comparecimento", title="Comparecimento extremo por seção (top por |z|)")
            + table(store, "anom_brancos_nulos", title="Brancos + nulos extremos por seção (top por |z|)")
            + table(store, "anom_secao_unanime")
            + table(store, "anom_unanime_municipio")
            + table(store, "anom_nulos_margem")
            + table(store, "anom_nulos_margem_uf")
            + table(store, "anom_secoes_gemeas")
            + table(store, "anom_gemeas_municipio")
            + table(store, "anom_ultimo_digito")
            + banner("Último dígito: a contagem é eletrônica; o teste é triagem exploratória e não entra no risk_score.", "info"),
            "componentes",
        )
        + section(
            "Impressão digital comparecimento × share (descritivo)",
            '<div class="grid-2">' + figure("anom_fingerprint_t1", "1º turno") + figure("anom_fingerprint_t2", "2º turno") + "</div>"
            + table(store, "anom_fingerprint_uf"),
            "fingerprint",
        )
    )


def executive_tab(ctx: ReportContext, verdict_rows: list[dict], pending_sentence: str) -> str:
    store = ctx.store
    reviewed = [item for item in ctx.hypotheses if item.get("verdict") in {"SUSTENTADO", "FRÁGIL"} and item.get("status") in {"reviewed", "published"}]
    if not reviewed and not verdict_rows:
        calculated = [[esc(sid), esc(store.meta(sid).get("title_pt", sid)), esc(store.meta(sid).get("unit", "")), esc(store.meta(sid).get("n_rows", ""))] for sid in store.available_ids()]
        return section(
            "Sumário executivo",
            banner(esc(pending_sentence), "warn")
            + paragraph(FORENSIC_CLASS_SENTENCE)
            + paragraph("Enquanto a revisão não ocorre, este sumário lista apenas o que foi calculado, sem interpretação. Os resultados descritivos estão nas abas Resultados, Validação, Demografia, Viradas e Anomalias; cada número exibido lá abre a tabela de origem ao clique.")
            + "<h3>O que foi calculado</h3>"
            + static_table(["source_id", "título", "unidade", "linhas"], calculated),
            "executivo",
        )
    cards = []
    for item in reviewed:
        verdict = item["verdict"]
        cards.append(
            f'<div class="card {("verdict-sustentado" if verdict == "SUSTENTADO" else "verdict-fragil")}">'
            f'<div class="card-head"><span class="badge">{esc(verdict)}</span> <strong>{esc(item["id"])}</strong> {esc(item["title"])}</div>'
            f'<div class="card-body">Classe: {esc(item.get("class", ""))} · Unidade: {esc(item.get("unit", ""))} · Tabelas: <code>{esc(item.get("table", ""))}</code>'
            + (f'<div class="ressalvas">Ressalvas do revisor: {esc(item.get("notes", ""))}</div>' if verdict == "FRÁGIL" else "")
            + "</div></div>"
        )
    verdict_table = ""
    if verdict_rows:
        verdict_table = static_table(["achado", "classe", "veredito", "motivo"], [[esc(r.get("achado_id", "")), esc(r.get("classe", "")), f'<span class="badge {("verdict-sustentado" if r.get("veredito") == "SUSTENTADO" else "verdict-fragil")}">{esc(r.get("veredito", ""))}</span>', esc(r.get("motivo", ""))] for r in verdict_rows])
    return section(
        "Sumário executivo",
        paragraph("Apenas achados com veredito SUSTENTADO ou FRÁGIL após revisão adversarial aparecem aqui; FRÁGIL traz ressalvas obrigatórias. Refutados e inconclusivos estão na aba Revisão.")
        + paragraph(FORENSIC_CLASS_SENTENCE)
        + "".join(cards)
        + verdict_table,
        "executivo",
    )


def cargo_label(code: int) -> str:
    return CARGO_LABELS.get(code, str(code))


def tab_intro_list(items: list[str]) -> str:
    return bullet_list(items)
