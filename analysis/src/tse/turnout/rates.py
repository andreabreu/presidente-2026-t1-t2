from __future__ import annotations

import numpy as np
import pandas as pd

PERCENT = 100.0
RATE_COLUMNS = {
    "taxa_comparecimento": ("QT_COMPARECIMENTO", "QT_APTOS"),
    "taxa_abstencao": ("QT_ABSTENCOES", "QT_APTOS"),
    "taxa_brancos_aptos": ("QT_VOTOS_BRANCOS", "QT_APTOS"),
    "taxa_nulos_aptos": ("QT_VOTOS_NULOS", "QT_APTOS"),
    "taxa_brancos_comp": ("QT_VOTOS_BRANCOS", "QT_COMPARECIMENTO"),
    "taxa_nulos_comp": ("QT_VOTOS_NULOS", "QT_COMPARECIMENTO"),
    "taxa_validos_comp": ("QT_VOTOS_VALIDOS", "QT_COMPARECIMENTO"),
}


def safe_rate(numerator, denominator) -> np.ndarray:
    numerator = np.asarray(numerator, dtype=float)
    denominator = np.asarray(denominator, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        rate = np.where(denominator > 0, numerator / denominator * PERCENT, np.nan)
    return rate


def add_rates(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for name, (numerator, denominator) in RATE_COLUMNS.items():
        if numerator in result.columns and denominator in result.columns:
            result[name] = safe_rate(result[numerator], result[denominator])
    return result


def distribution_summary(frame: pd.DataFrame, value_column: str, group_columns: list[str], weight_column: str | None = None) -> pd.DataFrame:
    def summarize(group: pd.DataFrame) -> pd.Series:
        values = group[value_column].dropna()
        summary = {
            "n": int(values.size),
            "media": values.mean(),
            "mediana": values.median(),
            "desvio_padrao": values.std(ddof=1) if values.size > 1 else np.nan,
            "p01": values.quantile(0.01),
            "p05": values.quantile(0.05),
            "p25": values.quantile(0.25),
            "p75": values.quantile(0.75),
            "p95": values.quantile(0.95),
            "p99": values.quantile(0.99),
            "minimo": values.min(),
            "maximo": values.max(),
        }
        if weight_column is not None:
            weights = group.loc[values.index, weight_column].astype(float)
            summary["media_ponderada"] = np.average(values, weights=weights) if weights.sum() > 0 else np.nan
        return pd.Series(summary)

    if not group_columns:
        return summarize(frame).to_frame().T
    return frame.groupby(group_columns, sort=True).apply(summarize, include_groups=False).reset_index()


def top_and_bottom(frame: pd.DataFrame, value_column: str, n: int, id_columns: list[str]) -> pd.DataFrame:
    ordered = frame.dropna(subset=[value_column]).sort_values(value_column)
    bottom = ordered.head(n).assign(extremo="menor")
    top = ordered.tail(n).iloc[::-1].assign(extremo="maior")
    extremes = pd.concat([top, bottom], ignore_index=True)[id_columns + [value_column, "extremo"]]
    return extremes.rename(columns={value_column: "valor"}).assign(metrica=value_column)
