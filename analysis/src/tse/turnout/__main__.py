from __future__ import annotations

import pandas as pd
import plotly.express as px

from ..config import load_config
from ..hypotheses import update_status
from ..io import connect
from ..tables import get_logger, write_figure, write_table
from . import panel
from .rates import distribution_summary, top_and_bottom

SCRIPT = "python -m tse.turnout"
MODULE = "turnout"
COUNT_COLUMNS = {
    "QT_APTOS": "eleitores aptos (soma das zonas, cargo Presidente)",
    "QT_COMPARECIMENTO": "comparecimento",
    "QT_ABSTENCOES": "abstenções",
    "QT_VOTOS_BRANCOS": "votos brancos",
    "QT_VOTOS_NULOS": "QT_TOTAL_VOTOS_NULOS (inclui nulos técnicos)",
    "QT_VOTOS_NULOS_TECNICOS": "nulos técnicos",
    "QT_VOTOS_VALIDOS": "QT_TOTAL_VOTOS_VALIDOS",
    "QT_TOTAL_SECOES": "seções",
    "QT_SECOES_NAO_INSTALADAS": "seções não instaladas",
    "QT_ELEITORES_SECOES_NAO_INSTALADAS": "eleitores de seções não instaladas",
}
RATE_COLUMNS = {
    "taxa_comparecimento": "comparecimento / aptos × 100",
    "taxa_abstencao": "abstenções / aptos × 100",
    "taxa_brancos_aptos": "brancos / aptos × 100",
    "taxa_nulos_aptos": "nulos / aptos × 100",
    "taxa_brancos_comp": "brancos / comparecimento × 100",
    "taxa_nulos_comp": "nulos / comparecimento × 100",
    "taxa_validos_comp": "válidos / comparecimento × 100",
}
ROBUST_SUFFIXES = {
    "_ref_mediana": "mediana do estrato UF × faixa_aptos × turno",
    "_ref_mad": "MAD escalonado (×1,4826) do estrato",
    "_z_mad": "(valor − mediana) / MAD",
    "_p_empirico": "percentil empírico dentro do estrato",
    "_n_estrato": "tamanho do estrato",
}
TRANSIT_CAVEAT = "ST_VOTO_EM_TRANSITO: ver turnout_transito; linhas com 'S' seriam excluídas das taxas municipais/zonais."
OUTLIER_METRICS = ["taxa_comparecimento", "taxa_abstencao", "taxa_brancos_comp", "taxa_nulos_comp"]
MUN_IDS = ["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_TURNO", "QT_APTOS"]
HISTOGRAM_METRICS = ["taxa_comparecimento", "taxa_nulos_comp", "taxa_brancos_comp"]


def robust_columns(metrics: list[str]) -> dict[str, str]:
    return {f"{metric}{suffix}": f"{metric}: {text}" for metric in metrics for suffix, text in ROBUST_SUFFIXES.items()}


def main() -> None:
    logger = get_logger(MODULE)
    config = load_config()
    conn = connect()
    panel.register_sources(conn)
    transit = panel.transit_votes_summary(conn)
    write_table(
        transit, "turnout_transito",
        title_pt="Voto em trânsito — contagem por fonte e turno", description_pt="Linhas e totais de detalhe_votacao_munzona por valor de ST_VOTO_EM_TRANSITO.",
        script=SCRIPT, hypothesis_ids=[], unit="fonte × turno × flag",
        columns={"fonte": "dataset/scope", "NR_TURNO": "turno", "ST_VOTO_EM_TRANSITO": "flag TSE", "n_linhas": "linhas mun/zona", **COUNT_COLUMNS},
        method="SQL DuckDB group by.", caveats_pt=["Se nenhuma linha tiver 'S', o voto em trânsito está incorporado às zonas de origem/destino sem marcação separada neste pacote."],
    )
    logger.info("voto em trânsito:\n%s", transit[["fonte", "NR_TURNO", "ST_VOTO_EM_TRANSITO", "n_linhas", "QT_APTOS"]].to_string())

    uf = panel.by_uf(conn)
    write_table(
        uf, "turnout_uf",
        title_pt="Comparecimento, abstenção, brancos e nulos por UF — Presidente", description_pt="Agregado de detalhe_votacao_munzona scope=BR (cargo 1) por UF e turno; ZZ = exterior.",
        script=SCRIPT, hypothesis_ids=["H14"], unit="UF × turno", columns={"SG_UF": "UF", "NR_TURNO": "turno", **COUNT_COLUMNS, **RATE_COLUMNS},
        method="Soma por UF; taxas = funções puras em turnout/rates.py.", caveats_pt=[TRANSIT_CAVEAT],
    )
    mun = panel.by_municipio(conn, config["demography"]["min_strata_size"])
    write_table(
        mun, "turnout_mun",
        title_pt="Comparecimento, abstenção, brancos e nulos por município — Presidente", description_pt="Agregado por município (zonas somadas) e turno, com z-MAD e percentil empírico dentro de UF × faixa de aptos (quintis nacionais) para abstenção, nulos e brancos.",
        script=SCRIPT, hypothesis_ids=["H14"], unit="município × turno",
        columns={"SG_UF": "UF", "CD_MUNICIPIO": "código TSE", "NM_MUNICIPIO": "nome", "NR_TURNO": "turno", **COUNT_COLUMNS, **RATE_COLUMNS, "exterior": "SG_UF = ZZ",
                 "faixa_aptos": "quintil nacional de QT_APTOS por turno", **robust_columns(["taxa_abstencao", "taxa_nulos_comp", "taxa_brancos_comp"])},
        method="z-MAD e percentil empírico por estrato (UF × faixa_aptos × turno), estratos com n < min_strata_size ficam sem escore.",
        caveats_pt=[TRANSIT_CAVEAT, "Percentil empírico não é p-valor; sem FDR porque não há teste de hipótese formal nesta etapa."],
    )
    zona = panel.by_zona(conn)
    write_table(
        zona, "turnout_zona",
        title_pt="Comparecimento, abstenção, brancos e nulos por zona — Presidente", description_pt="Linha original de detalhe_votacao_munzona (município × zona) com taxas, ambos os turnos.",
        script=SCRIPT, hypothesis_ids=["H14"], unit="zona × turno",
        columns={"SG_UF": "UF", "CD_MUNICIPIO": "código TSE", "NM_MUNICIPIO": "nome", "NR_ZONA": "zona", "NR_TURNO": "turno", **COUNT_COLUMNS, **RATE_COLUMNS},
        method="Taxas por linha.", caveats_pt=[TRANSIT_CAVEAT],
    )
    national = pd.concat(
        [distribution_summary(mun.loc[(mun["NR_TURNO"] == turno) & ~mun["exterior"]], metric, [], "QT_APTOS").assign(NR_TURNO=turno, metrica=metric)
         for turno in sorted(mun["NR_TURNO"].unique()) for metric in RATE_COLUMNS],
        ignore_index=True,
    )
    write_table(
        national, "turnout_distribuicao",
        title_pt="Distribuição nacional das taxas municipais — Presidente", description_pt="Estatísticas descritivas (não ponderadas e média ponderada por aptos) das taxas municipais, por turno, excluindo exterior.",
        script=SCRIPT, hypothesis_ids=["H14"], unit="métrica × turno",
        columns={"metrica": "nome da taxa", "NR_TURNO": "turno", "n": "municípios", "media": "média simples", "mediana": "mediana", "desvio_padrao": "desvio padrão", "p01": "percentil 1", "p05": "percentil 5",
                 "p25": "percentil 25", "p75": "percentil 75", "p95": "percentil 95", "p99": "percentil 99", "minimo": "mínimo", "maximo": "máximo", "media_ponderada": "média ponderada por QT_APTOS"},
        method="Quantis empíricos sobre turnout_mun.", caveats_pt=["Média simples trata municípios pequenos e grandes igualmente; usar média ponderada para o agregado nacional."],
    )
    eligible = mun.loc[~mun["exterior"] & (mun["QT_APTOS"] >= config["turnout"]["min_aptos_ranking"])]
    outliers = pd.concat(
        [top_and_bottom(eligible.loc[eligible["NR_TURNO"] == turno], metric, config["turnout"]["top_bottom_n"], MUN_IDS)
         for turno in sorted(eligible["NR_TURNO"].unique()) for metric in OUTLIER_METRICS],
        ignore_index=True,
    )
    write_table(
        outliers, "turnout_outliers",
        title_pt="Municípios extremos por métrica de participação — Presidente", description_pt=f"Top e bottom {config['turnout']['top_bottom_n']} municípios por métrica e turno, entre municípios com aptos ≥ {config['turnout']['min_aptos_ranking']} (exterior excluído).",
        script=SCRIPT, hypothesis_ids=["H14"], unit="município × métrica × turno",
        columns={"SG_UF": "UF", "CD_MUNICIPIO": "código TSE", "NM_MUNICIPIO": "nome", "NR_TURNO": "turno", "QT_APTOS": "aptos (porte)", "metrica": "taxa", "valor": "valor da taxa (%)", "extremo": "maior ou menor"},
        method="Ordenação simples; não é teste estatístico.", caveats_pt=["Extremos em municípios pequenos são esperados pela variância; a coluna QT_APTOS indica o porte.", "Classe: estatístico/descritivo; requer confronto com BU para qualquer afirmação além da descrição."],
    )
    depfed = panel.depfed_by_uf(conn)
    write_table(
        depfed, "turnout_depfed_uf",
        title_pt="Participação por UF — Deputado Federal, 1º turno", description_pt="Agregado de detalhe_votacao_munzona scope=BRASIL (cargo 6) por UF.",
        script=SCRIPT, hypothesis_ids=[], unit="UF", columns={"SG_UF": "UF", "NR_TURNO": "turno", **COUNT_COLUMNS, **RATE_COLUMNS},
        method="Soma por UF; taxas puras.", caveats_pt=["Aptos do cargo 6 excluem o exterior (não vota para Deputado Federal)."],
    )
    sections = panel.section_size_by_uf(conn)
    write_table(
        sections, "desc_secao_tamanho",
        title_pt="Distribuição do tamanho das seções (QT_APTOS) por UF — Presidente", description_pt="Percentis de aptos por seção, contagem de seções com aptos zero e com comparecimento > aptos, por UF e turno (detalhe_votacao_secao scope=BR).",
        script=SCRIPT, hypothesis_ids=["H30"], unit="UF × turno",
        columns={"SG_UF": "UF", "NR_TURNO": "turno", "n_secoes": "seções", "n_instaladas": "ST_SECAO_INSTALADA = Sim", "n_aptos_zero": "seções com QT_APTOS = 0", "n_aptos_zero_com_votos": "QT_APTOS = 0 e QT_COMPARECIMENTO > 0",
                 "n_comparecimento_maior_aptos": "QT_COMPARECIMENTO > QT_APTOS", "aptos_media": "média", "aptos_mediana": "mediana", "aptos_desvio": "desvio padrão", "aptos_min": "mínimo", "aptos_p01": "p1", "aptos_p05": "p5",
                 "aptos_p25": "p25", "aptos_p75": "p75", "aptos_p95": "p95", "aptos_p99": "p99", "aptos_max": "máximo", "aptos_total": "soma de aptos"},
        method="Agregação SQL por UF; violações contadas por linha.", caveats_pt=["Seções agregadas em outra (ST_SECAO_INSTALADA = Não) aparecem com aptos pequenos e comparecimento 0."],
    )
    urn = panel.urn_model_by_uf(conn)
    write_table(
        urn, "desc_modelo_urna",
        title_pt="Descritivo por modelo de urna (CD_MODELO_URNA) e UF — Presidente", description_pt="Número de seções instaladas, aptos, médias de comparecimento/nulos/brancos por seção, por UF, turno e modelo de urna.",
        script=SCRIPT, hypothesis_ids=["H26"], unit="UF × turno × modelo",
        columns={"SG_UF": "UF", "NR_TURNO": "turno", "CD_MODELO_URNA": "código do modelo", "DS_MODELO_URNA": "descrição", "n_secoes": "seções instaladas", "QT_APTOS": "aptos", "QT_COMPARECIMENTO": "comparecimento", "QT_ABSTENCOES": "abstenções",
                 "QT_VOTOS_BRANCOS": "brancos", "QT_VOTOS_NULOS": "nulos", "media_taxa_comparecimento_secao": "média das taxas de comparecimento por seção (%)", "media_taxa_nulos_secao": "média das taxas de nulos/comparecimento por seção (%)",
                 "media_taxa_brancos_secao": "média das taxas de brancos/comparecimento por seção (%)", "aptos_medio_secao": "aptos médio por seção", "share_secoes_na_uf": "% das seções da UF com este modelo", **RATE_COLUMNS},
        method="Agregação SQL; apenas descritivo.", caveats_pt=["Alocação de modelos não é aleatória (correlaciona com UF e porte); nenhuma inferência causal. Comparação formal com controles fica para H26 em etapa posterior."],
    )
    for metric in HISTOGRAM_METRICS:
        figure = px.histogram(mun.loc[~mun["exterior"]], x=metric, color="NR_TURNO", barmode="overlay", nbins=100, title=f"{metric} por município — Presidente (turnout_mun)")
        write_figure(figure, f"fig_turnout_hist_{metric}")
    update_hypotheses()
    logger.info("turnout concluído: %d municípios, %d zonas", mun[["SG_UF", "CD_MUNICIPIO"]].drop_duplicates().shape[0], len(zona))


def update_hypotheses() -> None:
    update_status("H14", "computed", script=SCRIPT, table="turnout_mun")
    update_status("H26", "computed", script=SCRIPT, table="desc_modelo_urna")
    update_status("H30", "computed", script=SCRIPT, table="desc_secao_tamanho")


if __name__ == "__main__":
    main()
