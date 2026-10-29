from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px

from ..config import load_config
from ..hypotheses import update_status
from ..io import connect
from ..robust import add_stratified_robust_scores, quantile_bins
from ..tables import get_logger, write_figure, write_table
from .join import coverage_report, electorate_by_municipio, join_electorate_population, load_external

SCRIPT = "python -m tse.demography.metrics"
MODULE = "demography"
RATIO_COLUMNS = {
    "aptos_pop_total": ("QT_APTOS", "pop_total"),
    "aptos_pop_16mais": ("QT_APTOS", "pop_16mais"),
    "comparecimento_pop_16mais": ("QT_COMPARECIMENTO", "pop_16mais"),
}
STRATA = ["SG_UF", "porte"]
TOP_OUTLIERS_PER_METRIC = 50
YEAR_CAVEAT = "pop_total é estimativa IBGE 2026 e pop_16mais é Censo 2022; aptos são de outubro de 2026. Razões > 1 podem refletir crescimento populacional 2022→2026, eleitores domiciliados eleitoralmente em município diferente da residência, inscrição facultativa de 16–17 anos, e eleitores com inscrição não cancelada."
INTERPRETATION_CAVEAT = "Classe estatística/descritiva: nenhum valor aqui indica irregularidade por si; requer confronto com cadastro eleitoral e censo."


def safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.where(denominator > 0)


def add_ratios(joined: pd.DataFrame) -> pd.DataFrame:
    result = joined.copy()
    for name, (numerator, denominator) in RATIO_COLUMNS.items():
        result[name] = safe_ratio(result[numerator], result[denominator])
    return result


def add_porte(frame: pd.DataFrame, quantiles: list[float], labels: list[str]) -> pd.DataFrame:
    result = frame.copy()
    result["porte"] = quantile_bins(result["pop_total"], quantiles, labels)
    result.loc[result["pop_total"].isna(), "porte"] = "sem_pop"
    return result


def flag_excess(frame: pd.DataFrame, tolerance: float) -> pd.DataFrame:
    result = frame.copy()
    result["flag_aptos_maior_pop16"] = result["aptos_pop_16mais"] > 1 + tolerance
    result["excesso_aptos_pop16"] = (result["QT_APTOS"] - result["pop_16mais"]).where(result["flag_aptos_maior_pop16"])
    result["flag_comparecimento_maior_pop16"] = result["comparecimento_pop_16mais"] > 1 + tolerance
    return result


def municipal_metrics(joined: pd.DataFrame, config: dict, mad_threshold: float) -> pd.DataFrame:
    frame = add_porte(add_ratios(joined), config["porte_quantiles"], config["porte_labels"])
    frame = flag_excess(frame, config["aptos_pop16_tolerance"])
    for metric in RATIO_COLUMNS:
        frame = add_stratified_robust_scores(frame, metric, STRATA, config["min_strata_size"])
        frame[f"{metric}_outlier_mad"] = frame[f"{metric}_z_mad"].abs() > mad_threshold
    frame["classe"] = "estatistico"
    return frame


def uf_aggregates(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = frame.groupby("SG_UF", sort=True)
    aggregated = grouped.agg(
        n_municipios=("CD_MUNICIPIO", "size"),
        n_com_populacao=("pop_total", "count"),
        QT_APTOS=("QT_APTOS", "sum"),
        QT_COMPARECIMENTO=("QT_COMPARECIMENTO", "sum"),
        pop_total=("pop_total", "sum"),
        pop_16mais=("pop_16mais", "sum"),
        n_flag_aptos_maior_pop16=("flag_aptos_maior_pop16", "sum"),
        mediana_aptos_pop_total=("aptos_pop_total", "median"),
        mediana_aptos_pop_16mais=("aptos_pop_16mais", "median"),
        mediana_comparecimento_pop_16mais=("comparecimento_pop_16mais", "median"),
    ).reset_index()
    return add_ratios(aggregated)


def outlier_table(frame: pd.DataFrame, mad_threshold: float) -> pd.DataFrame:
    pieces = []
    base_columns = ["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "id_municipio_ibge", "porte", "QT_APTOS", "QT_COMPARECIMENTO", "pop_total", "pop_16mais", "classe"]
    for metric in RATIO_COLUMNS:
        z_column = f"{metric}_z_mad"
        selected = frame.loc[frame[z_column].abs() > mad_threshold].copy()
        selected["metrica"] = metric
        selected["valor"] = selected[metric]
        selected["ref_mediana"] = selected[f"{metric}_ref_mediana"]
        selected["z_mad"] = selected[z_column]
        selected["p_empirico"] = selected[f"{metric}_p_empirico"]
        selected["effect_size"] = selected["z_mad"]
        pieces.append(selected[base_columns + ["metrica", "valor", "ref_mediana", "z_mad", "p_empirico", "effect_size"]])
    flagged = frame.loc[frame["flag_aptos_maior_pop16"]].copy()
    flagged["metrica"] = "aptos_pop_16mais_maior_que_1"
    flagged["valor"] = flagged["aptos_pop_16mais"]
    flagged["ref_mediana"] = flagged["aptos_pop_16mais_ref_mediana"]
    flagged["z_mad"] = flagged["aptos_pop_16mais_z_mad"]
    flagged["p_empirico"] = flagged["aptos_pop_16mais_p_empirico"]
    flagged["effect_size"] = flagged["excesso_aptos_pop16"]
    pieces.append(flagged[base_columns + ["metrica", "valor", "ref_mediana", "z_mad", "p_empirico", "effect_size"]])
    outliers = pd.concat(pieces, ignore_index=True)
    outliers["abs_z"] = outliers["z_mad"].abs()
    return outliers.sort_values(["metrica", "abs_z"], ascending=[True, False]).drop(columns="abs_z").reset_index(drop=True)


def scatter_figure(frame: pd.DataFrame):
    plotted = frame.dropna(subset=["pop_16mais", "QT_APTOS"]).copy()
    plotted["rotulo"] = np.where(plotted["flag_aptos_maior_pop16"], plotted["NM_MUNICIPIO"] + "/" + plotted["SG_UF"], "")
    figure = px.scatter(
        plotted, x="pop_16mais", y="QT_APTOS", color="flag_aptos_maior_pop16", text="rotulo", log_x=True, log_y=True,
        hover_data=["SG_UF", "NM_MUNICIPIO", "aptos_pop_16mais", "porte"],
        title="Aptos (2026, Presidente 1º turno) vs população 16+ (Censo 2022) — demo_aptos_pop",
    )
    figure.update_traces(textposition="top center")
    limits = [plotted["pop_16mais"].min(), plotted["pop_16mais"].max()]
    figure.add_shape(type="line", x0=limits[0], y0=limits[0], x1=limits[1], y1=limits[1], line={"dash": "dash"})
    return figure


def main() -> None:
    logger = get_logger(MODULE)
    full_config = load_config()
    config = full_config["demography"]
    mad_threshold = full_config["thresholds"]["mad_z_outlier"]
    conn = connect()
    electorate = electorate_by_municipio(conn)
    crosswalk, population = load_external()
    joined = join_electorate_population(electorate, crosswalk, population)
    coverage = coverage_report(joined, population)
    write_table(
        coverage, "demo_join_cobertura",
        title_pt="Cobertura do join TSE × IBGE (município)", description_pt="Indicadores de casamento entre municípios TSE (Presidente 1º turno, sem exterior) e população IBGE via crosswalk por código e fallback por nome|UF.",
        script=SCRIPT, hypothesis_ids=["H20", "H21", "H22"], unit="indicador",
        columns={"indicador": "nome do indicador", "valor": "valor (número ou lista, como texto)"},
        method="Join por id_municipio_tse → id_municipio_ibge; fallback por chave_nome_uf normalizada (sem acentos, maiúsculas).",
        caveats_pt=["Crosswalk de 2018 (betafcc); municípios criados depois dependem do fallback por nome.", "Códigos cujo nome IBGE diverge do nome TSE e cujo nome TSE casa exatamente com outro município da mesma UF são corrigidos pelo nome (metodo_join = chave_nome_uf_corrigido)."],
    )
    logger.info("cobertura:\n%s", coverage.to_string())
    metrics = municipal_metrics(joined, config, mad_threshold)
    robust_columns = {
        f"{metric}{suffix}": f"{metric}: {text}"
        for metric in RATIO_COLUMNS
        for suffix, text in {"_ref_mediana": "mediana do estrato UF × porte", "_ref_mad": "MAD escalonado do estrato", "_z_mad": "z robusto", "_p_empirico": "percentil empírico no estrato", "_n_estrato": "n do estrato", "_outlier_mad": f"|z_mad| > {mad_threshold}"}.items()
    }
    write_table(
        metrics, "demo_aptos_pop",
        title_pt="Aptos e comparecimento vs população IBGE por município", description_pt="Razões aptos/pop_total, aptos/pop_16mais e comparecimento/pop_16mais com referência robusta (mediana, MAD) por UF × porte e flags.",
        script=SCRIPT, hypothesis_ids=["H20", "H21", "H22"], unit="município",
        columns={"SG_UF": "UF", "CD_MUNICIPIO": "código TSE", "NM_MUNICIPIO": "nome TSE", "QT_APTOS": "aptos Presidente 1º turno (zonas somadas)", "QT_COMPARECIMENTO": "comparecimento", "QT_ABSTENCOES": "abstenções", "n_zonas": "zonas no município",
                 "id_municipio_ibge": "código IBGE", "metodo_join": "codigo_tse | chave_nome_uf | chave_nome_uf_corrigido | sem_correspondencia", "chave_nome_tse": "nome TSE normalizado|UF", "chave_nome_ibge": "nome IBGE normalizado|UF", "nome_divergente": "nomes TSE e IBGE diferem após normalização (grafia ou renomeação)", "nome_municipio": "nome IBGE", "pop_total": "população estimada", "pop_total_ano": "ano da estimativa", "pop_16mais": "população 16+ Censo 2022", "pop_16mais_ano": "2022",
                 "aptos_pop_total": "QT_APTOS / pop_total", "aptos_pop_16mais": "QT_APTOS / pop_16mais", "comparecimento_pop_16mais": "QT_COMPARECIMENTO / pop_16mais",
                 "porte": f"faixa de pop_total por quantis nacionais {config['porte_quantiles']}", "flag_aptos_maior_pop16": f"aptos_pop_16mais > 1 + {config['aptos_pop16_tolerance']}", "excesso_aptos_pop16": "QT_APTOS − pop_16mais quando flag",
                 "flag_comparecimento_maior_pop16": "comparecimento_pop_16mais > 1", "classe": "classe do achado (estatistico)", **robust_columns},
        method="Razões simples; mediana/MAD por estrato UF × porte; percentil empírico = rank/n no estrato; estratos com n < min_strata_size sem escore.",
        caveats_pt=[YEAR_CAVEAT, INTERPRETATION_CAVEAT, "Sem FDR: não há p-valor paramétrico; p_empirico é percentil descritivo."],
    )
    uf = uf_aggregates(metrics)
    write_table(
        uf, "demo_aptos_pop_uf",
        title_pt="Aptos e comparecimento vs população IBGE por UF", description_pt="Somas por UF e razões agregadas, medianas municipais e contagem de municípios com aptos > pop 16+.",
        script=SCRIPT, hypothesis_ids=["H20", "H21", "H22"], unit="UF",
        columns={"SG_UF": "UF", "n_municipios": "municípios TSE", "n_com_populacao": "com população IBGE", "QT_APTOS": "aptos", "QT_COMPARECIMENTO": "comparecimento", "pop_total": "população 2026", "pop_16mais": "população 16+ 2022",
                 "n_flag_aptos_maior_pop16": "municípios com aptos > pop 16+", "mediana_aptos_pop_total": "mediana municipal", "mediana_aptos_pop_16mais": "mediana municipal", "mediana_comparecimento_pop_16mais": "mediana municipal",
                 "aptos_pop_total": "razão agregada", "aptos_pop_16mais": "razão agregada", "comparecimento_pop_16mais": "razão agregada"},
        method="Soma e mediana por UF sobre demo_aptos_pop.", caveats_pt=[YEAR_CAVEAT],
    )
    outliers = outlier_table(metrics, mad_threshold)
    write_table(
        outliers, "demo_outliers",
        title_pt="Municípios fora do padrão UF × porte nas razões demográficas", description_pt=f"Municípios com |z_mad| > {mad_threshold} em cada razão e municípios com aptos > pop 16+, ordenados por magnitude.",
        script=SCRIPT, hypothesis_ids=["H20", "H21", "H22"], unit="município × métrica",
        columns={"SG_UF": "UF", "CD_MUNICIPIO": "código TSE", "NM_MUNICIPIO": "nome", "id_municipio_ibge": "código IBGE", "porte": "faixa de população", "QT_APTOS": "aptos", "QT_COMPARECIMENTO": "comparecimento", "pop_total": "população 2026", "pop_16mais": "população 16+ 2022",
                 "classe": "estatistico", "metrica": "razão avaliada", "valor": "valor da razão", "ref_mediana": "mediana do estrato", "z_mad": "z robusto", "p_empirico": "percentil no estrato", "effect_size": "z_mad (razões) ou excesso absoluto de aptos (flag)"},
        method="Filtro por |z_mad| e por flag; sem teste formal.", caveats_pt=[YEAR_CAVEAT, INTERPRETATION_CAVEAT],
    )
    write_figure(scatter_figure(metrics), "fig_demo_aptos_vs_pop16")
    update_status("H20", "computed", script=SCRIPT, table="demo_aptos_pop")
    update_status("H21", "computed", script=SCRIPT, table="demo_aptos_pop")
    update_status("H22", "computed", script=SCRIPT, table="demo_aptos_pop")
    flagged = metrics.loc[metrics["flag_aptos_maior_pop16"]].sort_values("aptos_pop_16mais", ascending=False)
    logger.info("municípios com aptos > pop16: %d\n%s", len(flagged), flagged.head(10)[["SG_UF", "NM_MUNICIPIO", "QT_APTOS", "pop_16mais", "pop_total", "aptos_pop_16mais", "porte"]].to_string())


if __name__ == "__main__":
    main()
