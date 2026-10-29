from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from ..config import load_config
from ..io import connect
from ..tables import get_logger, tables_dir
from .analysis import (
    LEVEL_NACIONAL,
    NATIONAL_LABEL,
    duplicates_table,
    ecological_comparison,
    gaps_table,
    lag_outliers_table,
    lag_table,
    margin_scenarios,
    minute_counts_table,
    parse_check_table,
    post_17h_table,
    post_19h_summary,
    reconciliation_table,
    urn_model_table,
)
from .constants import LAG_QUANTILES, MODULE_NAME
from .loaders import (
    discover_finalists,
    load_candidate_munzona_totals,
    load_munzona_last_totalization,
    load_munzona_totals,
    load_section_votes,
    load_sections,
    load_votacao_secao_keys,
)
from .docs import generate_all
from .outputs import save_table, write_figures, write_flow_spec
from .timestamps import lag_seconds

logger = get_logger(MODULE_NAME)
PLACAR_TABLE = "desc_placar_presidente"


def main() -> int:
    config = load_config()
    np.random.seed(config["seed"])
    conn = connect()
    logger.info("carregando detalhe_votacao_secao (BR, Presidente)")
    sections = load_sections(conn)
    munzona_last = load_munzona_last_totalization(conn)
    finalists = discover_finalists(conn, turno=2)
    leader, runner = int(finalists["NR_VOTAVEL"].iloc[0]), int(finalists["NR_VOTAVEL"].iloc[1])
    logger.info("finalistas descobertos pelos votos: %s", finalists[["NR_VOTAVEL", "NM_VOTAVEL", "votos"]].to_dict("records"))
    votes = load_section_votes(conn, 2, [leader, runner])
    placar = pd.read_parquet(tables_dir() / f"{PLACAR_TABLE}.parquet")

    save_table("bu_timestamps_parse", parse_check_table(sections), "Checagem de parsing dos carimbos de BU",
               "Formato, nulos e parseabilidade de DT_RECEBIMENTO_BU_HOR_TSE / DT_PRIM_TOT_PARCIAL_HOR_TSE e valores de DS_ORIGEM_VOTO, por turno.",
               "coluna × turno", {"NR_TURNO": "turno", "column": "coluna", "n_rows": "linhas", "n_null_marker": "#NULO/vazios",
                                  "n_unparseable": "não parseáveis fora de nulos", "share_parseable": "fração parseável",
                                  "n_distinct_second": "carimbos distintos (segundo)", "min": "mínimo", "max": "máximo",
                                  "length_values": "comprimentos observados ou contagem de valores (DS_ORIGEM_VOTO)"},
               "pandas to_datetime com formato dd/mm/yyyy HH:MM:SS.")

    minutes = minute_counts_table(sections, munzona_last)
    save_table("recebimento_minuto", minutes, "Seções por minuto de recepção / totalização",
               "Contagem de seções por minuto de DT_RECEBIMENTO_BU_HOR_TSE, DT_PRIM_TOT_PARCIAL_HOR_TSE (nacional, UF, fuso) e de DT/HH_ULTIMA_TOTALIZACAO (mun/zona), por turno.",
               "evento × nível × grupo × turno × minuto",
               {"evento": "recebimento_bu | prim_tot_parcial | ultima_totalizacao_munzona", "nivel": "nacional|uf|fuso",
                "grupo": "BR, sigla da UF ou grupo de fuso", "NR_TURNO": "turno", "minuto": "minuto (hora TSE)",
                "n_secoes": "seções (ou linhas mun/zona)", "comparecimento": "Σ comparecimento das seções do minuto"},
               "floor ao minuto e contagem.", ["Fusos: horário oficial de votação é unificado em Brasília desde 2022; grupos de fuso são apenas descritivos."])

    gaps = gaps_table(sections)
    save_table("janela_suspensao", gaps, "Maior intervalo sem recepção de BU (17h–23h59, hora TSE)",
               "Maior gap entre recepções consecutivas de BUs de seções instaladas com comparecimento > 0, por turno, nacional, por fuso e por UF; conta BUs imediatamente antes e depois.",
               "turno × nível × grupo",
               {"gap_inicio": "última recepção antes do gap", "gap_fim": "primeira recepção após o gap", "duracao_s": "duração (s)",
                "duracao_min": "duração (min)", "n_recebidas_5min_antes": "BUs nos 5 min antes do gap",
                "n_recebidas_5min_depois": "BUs nos 5 min após o gap", "n_recebidas_antes_gap": "BUs recebidas até gap_inicio",
                "n_recebidas_apos_gap": "BUs recebidas de gap_fim em diante", "primeira_recepcao": "min", "ultima_recepcao": "max"},
               "find_gaps: diferenças entre carimbos únicos ordenados dentro da janela; maior intervalo.")
    national_gap = gaps[(gaps["NR_TURNO"] == 2) & (gaps["nivel"] == LEVEL_NACIONAL)].iloc[0]
    logger.info("janela empírica T2: %s → %s (%.1f min)", national_gap["gap_inicio"], national_gap["gap_fim"], national_gap["duracao_min"])

    save_table("lag_recepcao_totalizacao", lag_table(sections), "Lag recepção → primeira totalização parcial",
               "Quantis de (DT_PRIM_TOT_PARCIAL − DT_RECEBIMENTO_BU) em segundos por turno, nacional e por UF; contagem de lags negativos e acima de 1h.",
               "turno × grupo", {f"q{q:g}".replace(".", "_"): f"quantil {q}" for q in LAG_QUANTILES} |
               {"media_s": "média (s)", "n": "seções", "n_lag_negativo": "totalização antes da recepção (impossível)",
                "n_lag_acima_3600s": "lag > 1h"}, "quantile_cont sobre diferença de carimbos.")
    save_table("lag_outliers", lag_outliers_table(sections), "Seções com lag negativo ou > 1h",
               "Lista de seções cujo lag recepção→totalização é negativo ou superior a 1h.", "seção",
               {"lag_s": "segundos", "recebimento": "carimbo de recepção", "prim_tot_parcial": "carimbo de 1ª totalização"},
               "filtro sobre lag.")

    post17 = post_17h_table(sections)
    save_table("secoes_pos_17h", post17, "Seções por faixa de horário de recepção do BU",
               "Seções, aptos e comparecimento por faixa de DT_RECEBIMENTO_BU_HOR_TSE (nacional, UF, município), por turno.",
               "nível × turno × unidade × faixa",
               {"banda": "faixa horária (hora TSE)", "n_secoes": "seções", "aptos": "Σ aptos", "comparecimento": "Σ comparecimento",
                "taxa_comparecimento": "comparecimento/aptos"}, "corte por hora do carimbo.",
               ["Horário de recepção do BU ≠ horário de encerramento da seção ≠ horário de votação; uma seção fechada às 17h pode ter BU recebido às 20h."])
    save_table("secoes_pos_19h_resumo", post_19h_summary(sections), "Seções recebidas após 17h / 19h / 19h10 — resumo",
               "Contagem, aptos, comparecimento e taxa das seções instaladas cujo BU foi recebido após cada corte, por turno.", "turno × critério",
               {"criterio": "corte de horário", "n_secoes": "seções", "share_secoes": "fração das seções instaladas",
                "taxa_comparecimento": "taxa nas seções após o corte", "taxa_comparecimento_demais": "taxa nas demais"}, "corte por hora do carimbo.")

    ecological, merged = ecological_comparison(sections, votes, leader, runner)
    save_table("ecologica_pos19h", ecological, "Comparação ecológica: share do líder e comparecimento vs. horário de recepção, com EF de município",
               "OLS ponderado (votos válidos ou aptos) do share do candidato líder (ou da taxa de comparecimento) sobre indicador de recepção após o corte, com efeitos fixos de município e EP agrupados por município.",
               "tratamento × desfecho",
               {"beta_fe_municipio": "diferença dentro de município (pontos de share)", "se_cluster_municipio": "EP cluster município",
                "ic95_inf": "IC95% inferior", "ic95_sup": "IC95% superior", "diferenca_bruta": "diferença ponderada sem controles",
                "n_tratadas": "seções com recepção após o corte"},
               "within-estimator ponderado; cluster-robust por município.",
               ["Comparação ecológica entre seções agregadas; NÃO informa votos individuais nem prova efeito da prorrogação.",
                "O horário de recepção do BU é determinado pela logística de transmissão, não pelo horário de votação; a quase totalidade das seções do 2º turno foi recebida após 19h."])

    munzona_totals = load_munzona_totals(conn, 2)
    candidate_totals = load_candidate_munzona_totals(conn, 2)
    save_table("reconciliacao", reconciliation_table(sections, votes, munzona_totals, candidate_totals, placar, leader, runner),
               "Reconciliação de contagens e totais do 2º turno", "Seções, instaladas, carimbos, origem e Σ votos por candidato em três fontes; ver val_resumo para os checks completos.",
               "métrica", {"metrica": "métrica", "valor": "valor", "fonte": "fonte"}, "contagens diretas; cruzamento com val_resumo (DF01/DF02/BR=BRASIL).")

    scenarios = margin_scenarios(merged, leader, runner, pd.Timestamp(national_gap["gap_fim"]))
    save_table("impacto_margem", scenarios, "Margem oficial e cenários hipotéticos de exclusão",
               "Totais e margem do 2º turno (líder − segundo) nas seções com votos válidos; cenários hipotéticos de exclusão por horário de recepção; votos necessários para inverter.",
               "cenário", {"cenario": "rótulo", "votos_lider_cenario": f"votos do candidato {leader}", "votos_segundo_cenario": f"votos do candidato {runner}",
                           "margem_cenario": "líder − segundo", "n_secoes_excluidas": "seções excluídas",
                           "votos_trocados_para_inverter": "votos que teriam de migrar do líder para o segundo", "votos_adicionais_segundo_para_inverter": "votos adicionais ao segundo"},
               "somas aritméticas.", ["Cenários hipotéticos NÃO são estimativas de votos afetados; apenas aritmética de exclusão por carimbo de recepção."])

    save_table("duplicidade", duplicates_table(sections, load_votacao_secao_keys(conn)), "Duplicidade e cobertura de chaves de seção",
               "Chaves (turno, UF, município, zona, seção) duplicadas em detalhe_votacao_secao e votacao_secao; seções presentes em só uma das fontes.",
               "turno", {"n_so_detalhe": "em detalhe e não em votacao_secao", "n_so_votacao_secao": "em votacao_secao e não em detalhe"}, "merge outer por chave.")
    save_table("modelo_urna_tempo", urn_model_table(sections), "Horário de recepção por modelo de urna (descritivo)",
               "Minutos após 17h até a recepção do BU (p10/mediana/p90), lag mediano e distribuição por faixa, por modelo de urna e turno.",
               "turno × modelo", {"recebimento_min_apos_17h_mediana": "mediana de minutos após 17h"}, "descritivo; sem teste.",
               ["Modelo de urna é confundido com UF/porte; nenhuma inferência causal."])

    merged_lags = sections[["NR_TURNO"]].assign(lag_s=lag_seconds(sections["recebimento"], sections["prim_tot_parcial"]))
    write_figures(minutes, merged_lags, post17)
    write_flow_spec({"recepcao": national_gap.to_dict(), "totalizacao": munzona_totals.iloc[0].to_dict()})
    generate_all()
    logger.info("concluído")
    return 0


if __name__ == "__main__":
    sys.exit(main())
