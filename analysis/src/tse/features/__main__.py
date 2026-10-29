from __future__ import annotations

import pandas as pd
import plotly.express as px

from ..config import load_config
from ..io import connect
from ..tables import get_logger, write_figure, write_table
from . import depfed, governador, presidente

SCRIPT = "python -m tse.features"
MODULE = "features"
MUN_LEVEL = ["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO"]
UF_LEVEL = ["SG_UF"]

SCOREBOARD_COLUMNS = {
    "NR_TURNO": "turno",
    "NR_CANDIDATO": "número do candidato na urna",
    "NM_URNA_CANDIDATO": "nome de urna (consulta_cand scope=BR)",
    "SG_PARTIDO": "sigla do partido",
    "NM_PARTIDO": "nome do partido",
    "votos": "soma de QT_VOTOS_NOMINAIS_VALIDOS",
    "votos_validos_total": "total de votos válidos nominais no nível",
    "pct_validos": "votos / válidos × 100",
    "rank": "posição por votos no nível e turno",
}
WINNER_COLUMNS = {
    "vencedor_nr": "número do 1º colocado",
    "vencedor_nome": "nome de urna do 1º colocado",
    "vencedor_partido": "partido do 1º colocado",
    "vencedor_votos": "votos do 1º colocado",
    "vencedor_pct_validos": "% válidos do 1º colocado",
    "segundo_nr": "número do 2º colocado",
    "segundo_nome": "nome do 2º colocado",
    "segundo_pct_validos": "% válidos do 2º colocado",
    "votos_validos": "válidos nominais",
    "n_candidatos": "candidatos com votos > 0",
    "hhi": "índice Herfindahl-Hirschman das parcelas de votos válidos",
    "n_efetivo_candidatos": "1/HHI",
    "margem_votos": "votos 1º − 2º",
    "margem_pp": "pontos percentuais 1º − 2º",
}
SOURCE_CAVEAT = "Votos válidos = QT_VOTOS_NOMINAIS_VALIDOS de votacao_candidato_munzona (Presidente: scope=BR; demais: scope=BRASIL). Brancos/nulos excluídos do denominador."


def main() -> None:
    logger = get_logger(MODULE)
    config = load_config()["descriptive"]
    conn = connect()
    run_presidente(conn, logger)
    run_governador(conn, logger)
    run_depfed(conn, logger, config)
    logger.info("features concluído")


def run_presidente(conn, logger) -> None:
    presidente.register_sources(conn)
    cands = presidente.candidates(conn)
    national = presidente.national_scoreboard(conn, cands)
    write_table(
        national, "desc_placar_presidente",
        title_pt="Placar nacional — Presidente, 1º e 2º turnos",
        description_pt="Votos válidos nominais por candidato a Presidente, agregados nacionalmente a partir de votacao_candidato_munzona (scope=BR), com partido via consulta_cand.",
        script=SCRIPT, hypothesis_ids=[], unit="candidato × turno",
        columns={**SCOREBOARD_COLUMNS, "rank_turno1": "posição do candidato no 1º turno"},
        method="SQL DuckDB: soma de QT_VOTOS_NOMINAIS_VALIDOS por NR_TURNO × NR_CANDIDATO; join por NR_CANDIDATO com consulta_cand CD_CARGO=1.",
        caveats_pt=[SOURCE_CAVEAT, "Inclui votos do exterior (SG_UF=ZZ)."],
    )
    logger.info("placar nacional:\n%s", national[["NR_TURNO", "NM_URNA_CANDIDATO", "SG_PARTIDO", "votos", "pct_validos", "rank"]].to_string())

    board_uf = presidente.scoreboard_uf(conn, cands)
    write_table(
        board_uf, "desc_placar_presidente_uf",
        title_pt="Placar Presidente por UF", description_pt="Votos válidos por candidato a Presidente em cada UF (inclui ZZ = exterior), turnos 1 e 2.",
        script=SCRIPT, hypothesis_ids=[], unit="UF × candidato × turno", columns={"SG_UF": "UF (ZZ = exterior)", **SCOREBOARD_COLUMNS},
        method="SQL DuckDB: agregação por SG_UF × NR_TURNO × NR_CANDIDATO.", caveats_pt=[SOURCE_CAVEAT],
    )
    winners_uf = presidente.winners(board_uf, UF_LEVEL)
    write_table(
        winners_uf, "desc_vencedor_presidente_uf",
        title_pt="Vencedor, margem e concentração por UF — Presidente", description_pt="1º e 2º colocados, margem e HHI por UF e turno.",
        script=SCRIPT, hypothesis_ids=[], unit="UF × turno", columns={"SG_UF": "UF", "NR_TURNO": "turno", **WINNER_COLUMNS},
        method="Funções puras hhi/effective_number/margin sobre o placar por UF.", caveats_pt=[SOURCE_CAVEAT],
    )
    board_mun = presidente.scoreboard_mun(conn, cands)
    write_table(
        board_mun, "desc_placar_presidente_mun",
        title_pt="Placar Presidente por município", description_pt="Votos válidos por candidato a Presidente em cada município (CD_MUNICIPIO TSE), turnos 1 e 2.",
        script=SCRIPT, hypothesis_ids=[], unit="município × candidato × turno",
        columns={"SG_UF": "UF", "CD_MUNICIPIO": "código TSE do município", "NM_MUNICIPIO": "nome do município", **SCOREBOARD_COLUMNS},
        method="SQL DuckDB: agregação por município × NR_TURNO × NR_CANDIDATO (zonas somadas).", caveats_pt=[SOURCE_CAVEAT, "Municípios do exterior (ZZ) são consulados/cidades estrangeiras."],
    )
    winners_mun = presidente.winners(board_mun, MUN_LEVEL)
    write_table(
        winners_mun, "desc_vencedor_presidente_mun",
        title_pt="Vencedor, margem e concentração por município — Presidente", description_pt="1º e 2º colocados, margem (votos e p.p.), HHI e nº efetivo de candidatos por município e turno.",
        script=SCRIPT, hypothesis_ids=[], unit="município × turno",
        columns={"SG_UF": "UF", "CD_MUNICIPIO": "código TSE", "NM_MUNICIPIO": "nome", "NR_TURNO": "turno", **WINNER_COLUMNS},
        method="Funções puras hhi/effective_number/margin sobre o placar municipal.", caveats_pt=[SOURCE_CAVEAT],
    )
    changes = presidente.rank_changes(board_mun, MUN_LEVEL)
    write_table(
        changes, "desc_mudanca_rank_presidente_mun",
        title_pt="Mudança de posição 1º→2º turno por município — Presidente", description_pt="Para os candidatos presentes no 2º turno, posição e % válidos em cada turno por município e variação.",
        script=SCRIPT, hypothesis_ids=[], unit="município × candidato do 2º turno",
        columns={"SG_UF": "UF", "CD_MUNICIPIO": "código TSE", "NM_MUNICIPIO": "nome", "NR_CANDIDATO": "número", "NM_URNA_CANDIDATO": "nome de urna", "SG_PARTIDO": "partido",
                 "rank_t1": "posição no 1º turno", "rank_t2": "posição no 2º turno", "pct_validos_t1": "% válidos 1º turno", "pct_validos_t2": "% válidos 2º turno",
                 "votos_t1": "votos 1º turno", "votos_t2": "votos 2º turno", "mudou_lider": "posição diferente entre turnos", "delta_pct_validos": "p.p. 2º − 1º", "delta_votos": "votos 2º − 1º"},
        method="Join interno dos placares municipais de turno 1 e 2 por candidato.", caveats_pt=[SOURCE_CAVEAT, "Descritivo; variação de % válidos não é transferência individual de votos."],
    )
    figure = px.bar(
        winners_uf.loc[winners_uf["NR_TURNO"] == 2].sort_values("vencedor_pct_validos"),
        x="SG_UF", y="vencedor_pct_validos", color="vencedor_nome", hover_data=["margem_pp", "vencedor_votos"],
        title="Presidente 2º turno — % válidos do 1º colocado por UF (desc_vencedor_presidente_uf)",
    )
    write_figure(figure, "fig_presidente_vencedor_uf")
    logger.info("Presidente: %d municípios, %d linhas no placar municipal", winners_mun[["SG_UF", "CD_MUNICIPIO"]].drop_duplicates().shape[0], len(board_mun))


def run_governador(conn, logger) -> None:
    governador.register_sources(conn)
    board = governador.scoreboard_uf(conn)
    summary = governador.summary_uf(board)
    write_table(
        board, "desc_placar_governador_uf",
        title_pt="Placar Governador por UF e turno", description_pt="Votos válidos por candidato a Governador em cada UF (scope=BRASIL, CD_CARGO=3), turno 1 e turno 2 onde ocorreu.",
        script=SCRIPT, hypothesis_ids=[], unit="UF × candidato × turno",
        columns={"SG_UF": "UF", "NR_TURNO": "turno", "NR_CANDIDATO": "número", "NM_URNA_CANDIDATO": "nome de urna", "SG_PARTIDO": "partido", "DS_SIT_TOT_TURNO": "situação de totalização",
                 "votos": "QT_VOTOS_NOMINAIS_VALIDOS", "votos_validos_total": "válidos nominais na UF", "pct_validos": "% válidos", "rank": "posição"},
        method="SQL DuckDB: soma por SG_UF × NR_TURNO × NR_CANDIDATO.", caveats_pt=[SOURCE_CAVEAT, "UFs com 2º turno identificadas pelos dados (presença de NR_TURNO=2)."],
    )
    write_table(
        summary, "desc_governador_uf",
        title_pt="Governador — líder, margem e 2º turno por UF", description_pt="Líder de cada UF por turno, segundo colocado, margem, HHI e indicador de 2º turno.",
        script=SCRIPT, hypothesis_ids=[], unit="UF × turno",
        columns={"SG_UF": "UF", "NR_TURNO": "turno", "lider_nr": "número do líder", "lider_nome": "nome do líder", "lider_partido": "partido", "lider_votos": "votos", "lider_pct_validos": "% válidos",
                 "lider_situacao": "DS_SIT_TOT_TURNO do líder", "segundo_nome": "2º colocado", "segundo_partido": "partido do 2º", "segundo_pct_validos": "% válidos do 2º",
                 "votos_validos": "válidos", "n_candidatos": "candidatos com votos", "hhi": "HHI", "n_efetivo_candidatos": "1/HHI", "margem_votos": "1º − 2º votos", "margem_pp": "1º − 2º p.p.", "teve_segundo_turno": "UF com NR_TURNO=2 nos dados"},
        method="Funções puras de concentração sobre o placar por UF.", caveats_pt=[SOURCE_CAVEAT],
    )
    logger.info("Governador: %d UFs, %d com 2º turno", summary["SG_UF"].nunique(), summary.loc[summary["teve_segundo_turno"], "SG_UF"].nunique())


def run_depfed(conn, logger, config: dict) -> None:
    depfed.register_sources(conn)
    by_party = depfed.votes_by_party(conn)
    write_table(
        by_party, "desc_depfed_partido",
        title_pt="Deputado Federal — votos por partido (nominais + legenda)", description_pt="Votos nominais e de legenda válidos por partido, nacional e por UF, a partir de votacao_partido_munzona scope=BRASIL, CD_CARGO=6.",
        script=SCRIPT, hypothesis_ids=[], unit="partido × (BRASIL | UF)",
        columns={"nivel": "BRASIL ou UF", "SG_UF": "UF (BR para o total nacional)", "NR_PARTIDO": "número do partido", "SG_PARTIDO": "sigla", "SG_FEDERACAO": "federação",
                 "votos_nominais": "QT_VOTOS_NOMINAIS_VALIDOS", "votos_legenda": "QT_VOTOS_LEGENDA_VALIDOS", "votos_anulados_subjudice": "nominais + legenda anulados sub judice",
                 "votos_validos": "nominais + legenda", "votos_validos_total": "válidos no nível", "pct_validos": "% válidos", "pct_legenda_no_partido": "legenda / válidos do partido × 100", "rank": "posição no nível"},
        method="SQL DuckDB; cadeiras não calculadas.", caveats_pt=["Não calcula cadeiras nem quociente eleitoral.", "Partidos em federação são listados individualmente."],
    )
    top = depfed.top_candidates(conn, config["top_n_candidates_national"], config["top_n_candidates_uf"], config["detail_ufs"])
    write_table(
        top, "desc_depfed_top",
        title_pt="Deputado Federal — candidatos mais votados (nacional e SP/RJ/MG)", description_pt="Top candidatos por votos nominais válidos: recorte BRASIL e recortes por UF de detalhe.",
        script=SCRIPT, hypothesis_ids=[], unit="candidato",
        columns={"recorte": "BRASIL ou UF", "rank": "posição no recorte", "SG_UF": "UF do candidato", "SQ_CANDIDATO": "sequencial TSE", "NR_CANDIDATO": "número", "NM_URNA_CANDIDATO": "nome de urna",
                 "SG_PARTIDO": "partido", "DS_SIT_TOT_TURNO": "situação", "votos": "votos nominais válidos", "votos_validos_uf": "válidos nominais da UF", "pct_validos_uf": "% dos nominais da UF"},
        method="SQL DuckDB: soma por SQ_CANDIDATO; ordenação por votos.", caveats_pt=["Comparação nacional entre UFs com eleitorados muito diferentes é apenas descritiva."],
    )
    logger.info("DepFed: %d partidos nacionais; top nacional %s", (by_party["nivel"] == "BRASIL").sum(), top.loc[top["recorte"] == "BRASIL"].head(3)[["NM_URNA_CANDIDATO", "votos"]].to_dict("records"))


if __name__ == "__main__":
    main()
