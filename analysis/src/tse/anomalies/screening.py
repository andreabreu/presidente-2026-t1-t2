from __future__ import annotations

import numpy as np
import pandas as pd

from tse.anomalies.features import special_place_mask
from tse.anomalies.stats import aptos_bin_labels, benjamini_hochberg, grouped_reference_metrics, normal_two_sided_p

REFERENCE_KEYS = ["SG_UF", "faixa_aptos", "NR_TURNO"]
FLAG_SMALL = "secao_pequena"
FLAG_SPECIAL_PLACE = "local_especial"
FLAG_NOT_INSTALLED = "nao_instalada"
FLAG_ANNULLED = "secao_anulada"
FLAG_ZONE_WITH_AGGREGATED = "zona_com_agregadas"
FLAG_TRANSIT = "voto_transito"
FLAG_NON_URNA_ORIGIN = "origem_voto_nao_urna"
ORIGIN_URNA = "Urna Eletrônica"
YES = "Sim"


def annotate_sections(detail: pd.DataFrame, zones: pd.DataFrame, config: dict) -> pd.DataFrame:
    settings = config["anomalies"]
    frame = detail.copy()
    frame["faixa_aptos"] = aptos_bin_labels(frame["QT_APTOS"].to_numpy(), settings["aptos_bins"])
    frame["taxa_comparecimento"] = frame["QT_COMPARECIMENTO"] / frame["QT_APTOS"].replace(0, np.nan)
    frame["taxa_brancos_nulos"] = (frame["QT_VOTOS_BRANCOS"] + frame["QT_VOTOS_NULOS"]) / frame[
        "QT_COMPARECIMENTO"
    ].replace(0, np.nan)
    frame["taxa_nulos"] = frame["QT_VOTOS_NULOS"] / frame["QT_COMPARECIMENTO"].replace(0, np.nan)
    frame["reference_group_id"] = (
        frame["SG_UF"] + "|" + frame["faixa_aptos"].astype(str) + "|T" + frame["NR_TURNO"].astype(str)
    )
    frame = frame.merge(
        zones[["CD_MUNICIPIO", "NR_ZONA", "NR_TURNO", "QT_SECOES_AGREGADAS", "ST_VOTO_EM_TRANSITO"]],
        on=["CD_MUNICIPIO", "NR_ZONA", "NR_TURNO"],
        how="left",
    )
    frame["flags_exclusao"] = _exclusion_flags(frame, settings)
    frame["tem_flag_exclusao"] = frame["flags_exclusao"].map(bool)
    return frame


def _exclusion_flags(frame: pd.DataFrame, settings: dict) -> pd.Series:
    conditions = {
        FLAG_SMALL: frame["QT_APTOS"] < settings["min_aptos_tested"],
        FLAG_SPECIAL_PLACE: special_place_mask(frame["NM_LOCAL_VOTACAO"], settings["special_place_pattern"]),
        FLAG_NOT_INSTALLED: frame["ST_SECAO_INSTALADA"] != YES,
        FLAG_ANNULLED: frame["ST_SECAO_ANULADA"] == YES,
        FLAG_ZONE_WITH_AGGREGATED: frame["QT_SECOES_AGREGADAS"].fillna(0) > 0,
        FLAG_TRANSIT: frame["ST_VOTO_EM_TRANSITO"].fillna("N") == "S",
        FLAG_NON_URNA_ORIGIN: frame["DS_ORIGEM_VOTO"] != ORIGIN_URNA,
    }
    names = list(conditions)
    matrix = np.column_stack([conditions[name].to_numpy(dtype=bool) for name in names])
    flags = [[names[j] for j in np.flatnonzero(row)] for row in matrix]
    return pd.Series(flags, index=frame.index, dtype=object)


def testable_mask(frame: pd.DataFrame, config: dict) -> pd.Series:
    return (
        (frame["QT_APTOS"] >= config["anomalies"]["min_aptos_tested"])
        & (frame["ST_SECAO_INSTALADA"] == YES)
        & (frame["QT_COMPARECIMENTO"] > 0)
    )


def extreme_screen(frame: pd.DataFrame, metric: str, finding_type: str, config: dict) -> pd.DataFrame:
    tested = frame.loc[testable_mask(frame, config) & frame[metric].notna()].copy()
    reference = grouped_reference_metrics(tested, metric, REFERENCE_KEYS)
    tested = tested.join(reference)
    tested["p_valor_z"] = normal_two_sided_p(tested["z_mad"].to_numpy())
    tested["q_fdr"] = np.nan
    for _, index in tested.groupby("NR_TURNO").groups.items():
        tested.loc[index, "q_fdr"] = benjamini_hochberg(tested.loc[index, "p_valor_z"].to_numpy())
    tested["finding_type"] = finding_type
    tested["metric_value"] = tested[metric]
    tested["cauda"] = np.where(tested["z_mad"] >= 0, "alto", "baixo")
    return tested[
        [
            "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO", "CD_CARGO",
            "finding_type", "metric_value", "cauda", "QT_APTOS", "QT_COMPARECIMENTO", "z_mad",
            "p_empirico", "p_valor_z", "q_fdr", "n_referencia", "reference_group_id", "flags_exclusao", "NM_LOCAL_VOTACAO",
        ]
    ].rename(columns={"QT_APTOS": "n_eleitores"})
