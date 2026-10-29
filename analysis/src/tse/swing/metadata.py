from __future__ import annotations

import re

from .data import Contest

STATIC_COLUMNS = {
    "uf": "Sigla da UF (ZZ = exterior)",
    "cd_municipio": "Código TSE do município",
    "nm_municipio": "Nome do município",
    "nr_zona": "Zona eleitoral",
    "nr_secao": "Seção eleitoral",
    "nr_local_votacao": "Código do local de votação (1º turno)",
    "st_secao_instalada": "Seção instalada (1º turno)",
    "porte": "Faixa de eleitores aptos (1º turno) da unidade",
    "presenca": "Presença da unidade nos turnos: ambos / so_t1 / so_t2",
    "aptos_t1": "Eleitores aptos 1º turno", "aptos_t2": "Eleitores aptos 2º turno", "delta_aptos": "aptos_t2 - aptos_t1",
    "comp_t1": "Comparecimento 1º turno", "comp_t2": "Comparecimento 2º turno", "delta_comp": "comp_t2 - comp_t1",
    "taxa_comp_t1": "comp_t1/aptos_t1", "taxa_comp_t2": "comp_t2/aptos_t2", "delta_comp_pp": "Variação da taxa de comparecimento em pontos percentuais",
    "brancos_t1": "Votos brancos 1º turno", "brancos_t2": "Votos brancos 2º turno",
    "nulos_t1": "Votos nulos 1º turno (inclui nulos técnicos no nível mun/zona)", "nulos_t2": "Votos nulos 2º turno",
    "finalista_a": "NR do finalista A (mais votado no 2º turno)", "finalista_b": "NR do finalista B",
    "votos_t1_a": "Votos do finalista A no 1º turno", "votos_t2_a": "Votos do finalista A no 2º turno",
    "votos_t1_b": "Votos do finalista B no 1º turno", "votos_t2_b": "Votos do finalista B no 2º turno",
    "delta_abs_a": "votos_t2_a - votos_t1_a", "delta_pct_a": "delta_abs_a / votos_t1_a em %",
    "delta_abs_b": "votos_t2_b - votos_t1_b", "delta_pct_b": "delta_abs_b / votos_t1_b em %",
    "votos_eliminados_t1": "Soma dos votos de candidatos eliminados no 1º turno",
    "delta_brancos_nulos": "(brancos+nulos T1) - (brancos+nulos T2)",
    "pool_residual": "eliminados + delta_brancos_nulos + delta_comp (= delta_abs_a + delta_abs_b)",
    "identidade_ok": "Identidade contábil ganho A + ganho B = pool residual satisfeita",
    "share_a_t1_dupla": "votos_t1_a / (votos_t1_a + votos_t1_b)", "share_a_t2_valid": "votos_t2_a / (votos_t2_a + votos_t2_b)",
    "delta_share_a_pp": "(share_a_t2_valid - share_a_t1_dupla) em pontos percentuais",
    "z_mad_delta_comp": "z robusto (MAD) de delta_comp_pp dentro do estrato UF×porte (H19)",
    "p_empirico_delta_comp": "Percentil empírico bilateral de |delta_comp_pp| no estrato", "p_param_delta_comp": "p bilateral normal do z robusto",
    "q_fdr_delta_comp": "q Benjamini–Hochberg de p_param_delta_comp (bateria: todas as seções)", "flag_delta_comp": "q_fdr_delta_comp < q_threshold",
    "n_unidades": "Número de unidades", "n_ambos": "Unidades presentes nos dois turnos", "n_so_t1": "Unidades só no 1º turno", "n_so_t2": "Unidades só no 2º turno",
    "n_aptos_diferente": "Unidades com QT_APTOS diferente entre turnos", "pct_aptos_diferente": "% de unidades com aptos diferente",
    "soma_abs_delta_aptos": "Soma de |delta_aptos|", "max_abs_delta_aptos": "Máximo de |delta_aptos|",
    "origem": "Linha de origem (comportamento no 1º turno, agregado)", "destino": "Coluna de destino (comportamento no 2º turno, agregado)",
    "estimativa": "Fração estimada da origem que vai ao destino (agregado, inferência ecológica)",
    "ci_low": "Limite inferior IC 95% bootstrap (reamostragem de unidades)", "ci_high": "Limite superior IC 95% bootstrap",
    "bound_low": "Limite inferior determinístico (fração da origem)", "bound_high": "Limite superior determinístico (fração da origem)",
    "bound_low_votos": "Limite inferior determinístico em votos", "bound_high_votos": "Limite superior determinístico em votos",
    "votos_origem": "Votos/eleitores na origem", "votos_estimados": "estimativa × votos_origem",
    "metodo": "Método de estimação", "nivel": "Nível de agregação das unidades usadas", "grupo": "Grupo de agregação (UF ou BR)",
    "agregado_de": "Nível a partir do qual os bounds foram agregados", "viavel": "Unidade compatível com a hipótese de retenção total",
    "n_unidades_viaveis": "Unidades compatíveis com a hipótese do método", "soma_linha_origem": "Soma das estimativas da origem sobre destinos (diagnóstico; ideal = 1)",
    "n_bootstrap": "Réplicas bootstrap", "cargo": "CD_CARGO", "scope": "Escopo dos dados (BR ou UF)",
    "share_a_t2_observada": "Share de A entre válidos no 2º turno observado", "share_a_t2_baseline": "Share de A sob baseline proporcional",
    "baseline_t2_a": "Votos esperados de A sob baseline proporcional", "baseline_t2_b": "Votos esperados de B sob baseline proporcional",
    "excesso_a_votos": "votos_t2_a - baseline_t2_a", "excesso_a_pp": "share observado - share baseline em pontos percentuais",
    "predito": "Share de A no 2º turno predito pelo modelo de resíduos", "residuo_pp": "Resíduo (observado - predito) em pontos percentuais = effect_size",
    "residuo_student": "Resíduo studentizado interno (WLS)", "estrato": "Estrato de referência (UF×porte; porte nacional se estrato < 30 unidades)",
    "z_mad": "z robusto (mediana/MAD) do resíduo studentizado dentro do estrato", "p_empirico": "Percentil empírico bilateral dentro do estrato (não é p-valor paramétrico)",
    "p_param": "p bilateral normal de z_mad", "q_fdr": "q Benjamini–Hochberg (bateria = todas as unidades do nível)", "flag": "q_fdr < q_threshold",
    "effect_size": "Resíduo em pontos percentuais", "n_flag": "Unidades com q_fdr < q_threshold", "falsos_positivos_esperados": "n_flag × q_threshold",
    "q_threshold": "Limiar de q usado", "residuo_pp_mediano": "Mediana do resíduo em pp", "residuo_pp_abs_p99": "Percentil 99 de |resíduo| em pp",
    "variante": "Variante de sensibilidade", "n_flag_base": "Flags na especificação base", "n_flag_variante": "Flags na variante",
    "jaccard": "Jaccard entre conjuntos de flags base e variante", "r2": "R² ponderado do modelo", "n_parametros": "Número de parâmetros do modelo",
    "rank": "Posição por |residuo_student| dentro do nível",
}


def describe_columns(contest: Contest | None = None) -> dict[str, str]:
    descriptions = dict(STATIC_COLUMNS)
    if contest is not None:
        for nr, name in contest.candidates.items():
            descriptions[f"votos_t1_{nr}"] = f"Votos 1º turno de {name} (NR {nr})"
    return descriptions


def describe_dynamic(column: str, contest: Contest | None) -> str:
    match = re.fullmatch(r"votos_t1_(\d+)", column)
    if match and contest is not None:
        return f"Votos 1º turno do candidato NR {match.group(1)} ({contest.candidates.get(int(match.group(1)), '?')})"
    return STATIC_COLUMNS.get(column, "")
