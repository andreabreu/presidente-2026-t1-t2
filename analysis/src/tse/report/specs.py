from __future__ import annotations

from .data import TableSpec

SECAO_KEYS = ("SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO", "CD_CARGO")
RISK_COLUMNS = SECAO_KEYS + (
    "NM_LOCAL_VOTACAO", "n_eleitores", "finding_types", "classe", "severity", "p_empirico_min", "q_fdr_min",
    "risk_score", "flags_exclusao", "tem_flag_exclusao", "what_bu_would_resolve",
)
TURNOUT_COLUMNS = (
    "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_TURNO", "QT_APTOS", "QT_COMPARECIMENTO", "faixa_aptos", "exterior",
    "taxa_comparecimento", "taxa_abstencao", "taxa_brancos_comp", "taxa_nulos_comp",
    "taxa_abstencao_z_mad", "taxa_abstencao_p_empirico", "taxa_nulos_comp_z_mad", "taxa_nulos_comp_p_empirico",
    "taxa_brancos_comp_z_mad", "taxa_brancos_comp_p_empirico",
)
SALDOS_COLUMNS = (
    "uf", "cd_municipio", "nm_municipio", "nr_zona", "nr_secao", "porte", "aptos_t1", "aptos_t2", "comp_t1", "comp_t2",
    "delta_comp_pp", "finalista_a", "votos_t1_a", "votos_t2_a", "delta_abs_a", "delta_pct_a",
    "finalista_b", "votos_t1_b", "votos_t2_b", "delta_abs_b", "delta_pct_b", "votos_eliminados_t1", "delta_brancos_nulos",
    "pool_residual", "share_a_t1_dupla", "share_a_t2_valid", "delta_share_a_pp", "z_mad_delta_comp", "q_fdr_delta_comp", "flag_delta_comp",
)
DEMO_COLUMNS = (
    "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "porte", "QT_APTOS", "QT_COMPARECIMENTO", "pop_total", "pop_16mais",
    "aptos_pop_total", "aptos_pop_16mais", "comparecimento_pop_16mais", "flag_aptos_maior_pop16", "excesso_aptos_pop16",
    "aptos_pop_16mais_z_mad", "aptos_pop_16mais_p_empirico", "aptos_pop_16mais_outlier_mad", "classe",
)
ANOM_SECAO_COLUMNS = SECAO_KEYS + ("finding_type", "metric_value", "cauda", "n_eleitores", "z_mad", "p_empirico", "q_fdr", "reference_group_id", "flags_exclusao", "NM_LOCAL_VOTACAO")

TABLE_SPECS: dict[str, TableSpec] = {
    "anom_risk_score": TableSpec(columns=RISK_COLUMNS, sort_by="risk_score"),
    "anom_top200_secoes": TableSpec(columns=RISK_COLUMNS, sort_by="risk_score"),
    "anom_comparecimento": TableSpec(columns=ANOM_SECAO_COLUMNS, sort_by="z_mad", sort_abs=True),
    "anom_brancos_nulos": TableSpec(columns=ANOM_SECAO_COLUMNS, sort_by="z_mad", sort_abs=True),
    "anom_mun_ranking": TableSpec(sort_by="risk_score_medio"),
    "anom_secao_unanime": TableSpec(sort_by="votos_nominais"),
    "anom_unanime_municipio": TableSpec(sort_by="q_fdr", ascending=True),
    "anom_gemeas_municipio": TableSpec(sort_by="pares_identicos_observados"),
    "turnout_mun": TableSpec(columns=TURNOUT_COLUMNS),
    "turnout_zona": TableSpec(columns=TURNOUT_COLUMNS),
    "swing_saldos_mun": TableSpec(columns=SALDOS_COLUMNS, sort_by="delta_share_a_pp", sort_abs=True),
    "swing_saldos_zona": TableSpec(columns=SALDOS_COLUMNS, sort_by="delta_share_a_pp", sort_abs=True),
    "swing_saldos_secao": TableSpec(columns=SALDOS_COLUMNS, sort_by="delta_share_a_pp", sort_abs=True),
    "swing_bounds_mun": TableSpec(sort_by="votos_origem"),
    "swing_residuos_flag": TableSpec(sort_by="q_fdr", ascending=True),
    "swing_governador_residuos_flag": TableSpec(sort_by="q_fdr", ascending=True),
    "desc_mudanca_rank_presidente_mun": TableSpec(sort_by="delta_pct_validos", sort_abs=True),
    "demo_aptos_pop": TableSpec(columns=DEMO_COLUMNS, sort_by="aptos_pop_16mais"),
    "demo_outliers": TableSpec(sort_by="z_mad", sort_abs=True),
    "val_inconsistencias": TableSpec(sort_by="delta_abs", sort_abs=True),
    "turnout_outliers": TableSpec(),
}
