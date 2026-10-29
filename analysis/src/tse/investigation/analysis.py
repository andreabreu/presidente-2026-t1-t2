from __future__ import annotations

import pandas as pd

from .constants import (
    ANALYSIS_WINDOW_END,
    ANALYSIS_WINDOW_START,
    ELECTION_DATES,
    EXTENDED_CLOSING,
    EXTENSION_CONSISTENT_RECEPTION,
    LAG_ALERT_SECONDS,
    LAG_QUANTILES,
    OFFICIAL_CLOSING,
    ORIGEM_URNA,
    RECEPTION_BANDS,
    SECAO_INSTALADA,
    TURNOS,
)
from .estimators import WithinEstimate, scenario_totals, votes_to_flip, within_estimator
from .timestamps import (
    after_clock,
    count_by_minute,
    find_gaps,
    lag_quantiles,
    lag_seconds,
    parse_summary,
    reception_band,
    timezone_group,
)

NATIONAL_LABEL = "BR"
LEVEL_NACIONAL = "nacional"
LEVEL_UF = "uf"
LEVEL_FUSO = "fuso"
EVENT_RECEBIMENTO = "recebimento_bu"
EVENT_PRIM_TOT = "prim_tot_parcial"
EVENT_ULTIMA_TOT_MUNZONA = "ultima_totalizacao_munzona"


def window_bounds(turno: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    date = ELECTION_DATES[turno]
    return pd.Timestamp(f"{date} {ANALYSIS_WINDOW_START}"), pd.Timestamp(f"{date} {ANALYSIS_WINDOW_END}")


def installed_with_votes(sections: pd.DataFrame) -> pd.Series:
    return (sections["ST_SECAO_INSTALADA"] == SECAO_INSTALADA) & (sections["QT_COMPARECIMENTO"] > 0)


def parse_check_table(sections: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for turno in TURNOS:
        subset = sections[sections["NR_TURNO"] == turno]
        for column in ("DT_RECEBIMENTO_BU_HOR_TSE", "DT_PRIM_TOT_PARCIAL_HOR_TSE"):
            rows.append({"NR_TURNO": turno, **parse_summary(subset[column], column)})
        origem = subset["DS_ORIGEM_VOTO"].value_counts()
        rows.append({"NR_TURNO": turno, "column": "DS_ORIGEM_VOTO", "n_rows": int(len(subset)),
                     "length_values": "; ".join(f"{k}={v}" for k, v in origem.items())})
    return pd.DataFrame(rows)


def minute_counts_table(sections: pd.DataFrame, munzona: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for event, column in ((EVENT_RECEBIMENTO, "recebimento"), (EVENT_PRIM_TOT, "prim_tot_parcial")):
        base = sections.assign(fuso=timezone_group(sections["SG_UF"]), nivel_valor=NATIONAL_LABEL)
        for level, key in ((LEVEL_NACIONAL, "nivel_valor"), (LEVEL_UF, "SG_UF"), (LEVEL_FUSO, "fuso")):
            groups = base[["NR_TURNO", key]].rename(columns={key: "grupo"})
            counts = count_by_minute(base[column], groups)
            turnout = (pd.concat([groups, base[column].dt.floor("min").rename("minuto"), base["QT_COMPARECIMENTO"]], axis=1)
                       .dropna(subset=["minuto"]).groupby(["NR_TURNO", "grupo", "minuto"], observed=True)["QT_COMPARECIMENTO"].sum())
            counts = counts.merge(turnout.rename("comparecimento").reset_index(), on=["NR_TURNO", "grupo", "minuto"])
            frames.append(counts.assign(evento=event, nivel=level))
    munzona_counts = count_by_minute(munzona["ultima_totalizacao"], munzona[["NR_TURNO"]].assign(grupo=NATIONAL_LABEL))
    frames.append(munzona_counts.assign(comparecimento=pd.NA, evento=EVENT_ULTIMA_TOT_MUNZONA, nivel=LEVEL_NACIONAL))
    table = pd.concat(frames, ignore_index=True)
    return table[["evento", "nivel", "grupo", "NR_TURNO", "minuto", "n_secoes", "comparecimento"]].sort_values(
        ["evento", "nivel", "grupo", "NR_TURNO", "minuto"]).reset_index(drop=True)


def gaps_table(sections: pd.DataFrame) -> pd.DataFrame:
    rows = []
    valid = sections[installed_with_votes(sections)]
    for turno in TURNOS:
        subset = valid[valid["NR_TURNO"] == turno]
        start, end = window_bounds(turno)
        for level, key in ((LEVEL_NACIONAL, None), (LEVEL_FUSO, "fuso"), (LEVEL_UF, "SG_UF")):
            grouped = [(NATIONAL_LABEL, subset)] if key is None else list(
                subset.assign(fuso=timezone_group(subset["SG_UF"])).groupby(key, observed=True))
            for label, group in grouped:
                gaps = find_gaps(group["recebimento"], start, end, top=1)
                if gaps.empty:
                    continue
                gap = gaps.iloc[0]
                rows.append({"NR_TURNO": turno, "nivel": level, "grupo": label, "n_secoes_grupo": int(len(group)),
                             "gap_inicio": gap["gap_inicio"], "gap_fim": gap["gap_fim"], "duracao_s": gap["duracao_s"],
                             "duracao_min": gap["duracao_s"] / 60, "n_recebidas_5min_antes": gap["n_antes_5min"],
                             "n_recebidas_5min_depois": gap["n_depois_5min"],
                             "n_recebidas_antes_gap": int((group["recebimento"] <= gap["gap_inicio"]).sum()),
                             "n_recebidas_apos_gap": int((group["recebimento"] >= gap["gap_fim"]).sum()),
                             "primeira_recepcao": group["recebimento"].min(), "ultima_recepcao": group["recebimento"].max()})
    return pd.DataFrame(rows).sort_values(["NR_TURNO", "nivel", "duracao_s"], ascending=[True, True, False]).reset_index(drop=True)


def lag_table(sections: pd.DataFrame) -> pd.DataFrame:
    lags = lag_seconds(sections["recebimento"], sections["prim_tot_parcial"])
    base = sections.assign(lag_s=lags)
    rows = []
    for turno in TURNOS:
        subset = base[base["NR_TURNO"] == turno]
        groups = [(NATIONAL_LABEL, subset), *subset.groupby("SG_UF", observed=True)]
        for label, group in groups:
            rows.append({"NR_TURNO": turno, "grupo": label, **lag_quantiles(group["lag_s"], LAG_QUANTILES),
                         "n_lag_negativo": int((group["lag_s"] < 0).sum()),
                         f"n_lag_acima_{LAG_ALERT_SECONDS}s": int((group["lag_s"] > LAG_ALERT_SECONDS).sum())})
    return pd.DataFrame(rows)


def lag_outliers_table(sections: pd.DataFrame) -> pd.DataFrame:
    lags = lag_seconds(sections["recebimento"], sections["prim_tot_parcial"])
    flagged = sections.assign(lag_s=lags)
    flagged = flagged[(flagged["lag_s"] < 0) | (flagged["lag_s"] > LAG_ALERT_SECONDS)]
    columns = ["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO", "QT_APTOS", "QT_COMPARECIMENTO",
               "DS_ORIGEM_VOTO", "ST_SECAO_INSTALADA", "recebimento", "prim_tot_parcial", "lag_s"]
    return flagged[columns].sort_values("lag_s", ascending=False).reset_index(drop=True)


def post_17h_table(sections: pd.DataFrame) -> pd.DataFrame:
    base = sections.assign(banda=reception_band(sections["recebimento"]))
    rows = []
    for level, keys in ((LEVEL_NACIONAL, []), (LEVEL_UF, ["SG_UF"]), ("municipio", ["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO"])):
        grouped = base.groupby(["NR_TURNO", *keys, "banda"], observed=True, dropna=False)
        summary = grouped.agg(n_secoes=("NR_SECAO", "size"), aptos=("QT_APTOS", "sum"),
                              comparecimento=("QT_COMPARECIMENTO", "sum")).reset_index()
        summary["nivel"] = level
        if not keys:
            summary["SG_UF"] = NATIONAL_LABEL
        rows.append(summary)
    table = pd.concat(rows, ignore_index=True)
    table["taxa_comparecimento"] = table["comparecimento"] / table["aptos"]
    return table


def post_19h_summary(sections: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for turno in TURNOS:
        subset = sections[(sections["NR_TURNO"] == turno) & installed_with_votes(sections)]
        after_19 = after_clock(subset["recebimento"], EXTENDED_CLOSING)
        after_17 = after_clock(subset["recebimento"], OFFICIAL_CLOSING)
        after_ext = after_clock(subset["recebimento"], EXTENSION_CONSISTENT_RECEPTION)
        for label, mask in (("apos_17h", after_17), ("apos_19h", after_19),
                            (f"apos_{EXTENSION_CONSISTENT_RECEPTION:%Hh%M}", after_ext)):
            part = subset[mask]
            rows.append({"NR_TURNO": turno, "criterio": label, "n_secoes": int(len(part)),
                         "share_secoes": float(mask.mean()), "aptos": int(part["QT_APTOS"].sum()),
                         "comparecimento": int(part["QT_COMPARECIMENTO"].sum()),
                         "taxa_comparecimento": float(part["QT_COMPARECIMENTO"].sum() / part["QT_APTOS"].sum()) if len(part) else float("nan"),
                         "taxa_comparecimento_demais": float(subset.loc[~mask, "QT_COMPARECIMENTO"].sum() / subset.loc[~mask, "QT_APTOS"].sum()) if (~mask).any() else float("nan")})
    return pd.DataFrame(rows)


def ecological_comparison(sections: pd.DataFrame, votes: pd.DataFrame, leader: int, runner: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    second = sections[(sections["NR_TURNO"] == 2) & installed_with_votes(sections)]
    merged = second.merge(votes, on=["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"], how="inner")
    leader_col, runner_col = f"votos_{leader}", f"votos_{runner}"
    merged["validos"] = merged[leader_col] + merged[runner_col]
    merged = merged[merged["validos"] > 0]
    merged["share_lider"] = merged[leader_col] / merged["validos"]
    merged["municipio_id"] = merged["SG_UF"] + "-" + merged["CD_MUNICIPIO"].astype(str)
    treatments = {
        f"recebida_apos_{EXTENSION_CONSISTENT_RECEPTION:%Hh%M}": after_clock(merged["recebimento"], EXTENSION_CONSISTENT_RECEPTION),
        "recebida_apos_19h00": after_clock(merged["recebimento"], EXTENDED_CLOSING),
        "recebida_apos_20h00": after_clock(merged["recebimento"], pd.Timestamp("2026-10-25 20:00").time()),
        "recebida_apos_21h00": after_clock(merged["recebimento"], pd.Timestamp("2026-10-25 21:00").time()),
    }
    rows = [_estimate_row(name, merged, mask, "share_lider") for name, mask in treatments.items()]
    rows += [_estimate_row(name + "__taxa_comparecimento", merged.assign(taxa=merged["QT_COMPARECIMENTO"] / merged["QT_APTOS"]), mask, "taxa")
             for name, mask in treatments.items()]
    return pd.DataFrame(rows), merged


def _estimate_row(name: str, frame: pd.DataFrame, mask: pd.Series, outcome: str) -> dict:
    weights = frame["validos"] if outcome == "share_lider" else frame["QT_APTOS"]
    estimate: WithinEstimate = within_estimator(frame[outcome], mask, frame["municipio_id"], weights)
    raw_treated = float((frame.loc[mask, outcome] * weights[mask]).sum() / weights[mask].sum()) if mask.any() else float("nan")
    raw_control = float((frame.loc[~mask, outcome] * weights[~mask]).sum() / weights[~mask].sum()) if (~mask).any() else float("nan")
    return {"tratamento": name, "desfecho": outcome, "n_secoes": estimate.n_obs, "n_municipios": estimate.n_groups,
            "n_tratadas": estimate.n_treated, "media_ponderada_tratadas": raw_treated, "media_ponderada_controle": raw_control,
            "diferenca_bruta": raw_treated - raw_control, "beta_fe_municipio": estimate.beta,
            "se_cluster_municipio": estimate.se_cluster, "ic95_inf": estimate.ci_low, "ic95_sup": estimate.ci_high}


def reconciliation_table(sections: pd.DataFrame, votes: pd.DataFrame, munzona_totals: pd.DataFrame,
                         candidate_totals: pd.DataFrame, placar: pd.DataFrame, leader: int, runner: int) -> pd.DataFrame:
    second = sections[sections["NR_TURNO"] == 2]
    rows = [
        ("secoes_detalhe_secao", int(len(second)), "detalhe_votacao_secao BR"),
        ("secoes_instaladas", int((second["ST_SECAO_INSTALADA"] == SECAO_INSTALADA).sum()), "detalhe_votacao_secao BR"),
        ("secoes_nao_instaladas", int((second["ST_SECAO_INSTALADA"] != SECAO_INSTALADA).sum()), "detalhe_votacao_secao BR"),
        ("secoes_anuladas", int((second["ST_SECAO_ANULADA"] == SECAO_INSTALADA).sum()), "detalhe_votacao_secao BR"),
        ("secoes_com_carimbo_recebimento", int(second["recebimento"].notna().sum()), "detalhe_votacao_secao BR"),
        ("secoes_com_carimbo_prim_tot", int(second["prim_tot_parcial"].notna().sum()), "detalhe_votacao_secao BR"),
        ("secoes_origem_urna_eletronica", int((second["DS_ORIGEM_VOTO"] == ORIGEM_URNA).sum()), "detalhe_votacao_secao BR"),
        ("secoes_comparecimento_zero", int((second["QT_COMPARECIMENTO"] == 0).sum()), "detalhe_votacao_secao BR"),
        ("secoes_votacao_secao", int(len(votes)), "votacao_secao BR"),
        ("secoes_principais_munzona", int(munzona_totals["secoes_principais"].iloc[0]), "detalhe_votacao_munzona BRASIL"),
        ("secoes_agregadas_munzona", int(munzona_totals["secoes_agregadas"].iloc[0]), "detalhe_votacao_munzona BRASIL"),
        ("secoes_nao_instaladas_munzona", int(munzona_totals["secoes_nao_instaladas"].iloc[0]), "detalhe_votacao_munzona BRASIL"),
        ("comparecimento_detalhe_secao", int(second["QT_COMPARECIMENTO"].sum()), "detalhe_votacao_secao BR"),
        ("comparecimento_munzona", int(munzona_totals["comparecimento"].iloc[0]), "detalhe_votacao_munzona BRASIL"),
    ]
    for candidate in (leader, runner):
        rows.append((f"votos_{candidate}_votacao_secao", int(votes[f"votos_{candidate}"].sum()), "votacao_secao BR"))
        munzona_votes = candidate_totals.loc[candidate_totals["NR_CANDIDATO"] == candidate, "votos_validos"]
        rows.append((f"votos_{candidate}_candidato_munzona", int(munzona_votes.iloc[0]), "votacao_candidato_munzona BR"))
        placar_votes = placar.loc[(placar["NR_TURNO"] == 2) & (placar["NR_CANDIDATO"] == candidate), "votos"]
        rows.append((f"votos_{candidate}_desc_placar_presidente", int(placar_votes.iloc[0]), "desc_placar_presidente"))
    rows.append(("ultima_totalizacao_min", str(munzona_totals["ultima_tot_min"].iloc[0]), "detalhe_votacao_munzona BRASIL"))
    rows.append(("ultima_totalizacao_max", str(munzona_totals["ultima_tot_max"].iloc[0]), "detalhe_votacao_munzona BRASIL"))
    table = pd.DataFrame(rows, columns=["metrica", "valor", "fonte"])
    table["valor"] = table["valor"].astype(str)
    return table


def margin_scenarios(merged: pd.DataFrame, leader: int, runner: int, resume_end: pd.Timestamp) -> pd.DataFrame:
    leader_col, runner_col = f"votos_{leader}", f"votos_{runner}"
    official = scenario_totals(merged, pd.Series(False, index=merged.index), leader_col, runner_col)
    flip = votes_to_flip(official["votos_lider_cenario"], official["votos_segundo_cenario"])
    scenarios = {
        "oficial (todas as seções com votos válidos)": pd.Series(False, index=merged.index),
        "cenário hipotético (a): excluir seções recebidas após 19h00": after_clock(merged["recebimento"], EXTENDED_CLOSING),
        "cenário hipotético (b): excluir seções recebidas após a retomada empírica": merged["recebimento"] >= resume_end,
        f"cenário hipotético (d): excluir seções recebidas após {EXTENSION_CONSISTENT_RECEPTION:%Hh%M}": after_clock(merged["recebimento"], EXTENSION_CONSISTENT_RECEPTION),
    }
    rows = []
    for label, exclude in scenarios.items():
        result = scenario_totals(merged, exclude, leader_col, runner_col)
        rows.append({"cenario": label, **result, "n_secoes_mantidas": int(len(merged) - result["n_secoes_excluidas"])})
    rows.append({"cenario": "cenário hipotético (c): votos necessários para inverter a margem oficial", **flip})
    return pd.DataFrame(rows)


def duplicates_table(sections: pd.DataFrame, votacao_keys: pd.DataFrame) -> pd.DataFrame:
    key = ["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]
    detail_dups = sections[sections.duplicated(key, keep=False)]
    votacao_dups = votacao_keys[votacao_keys.duplicated(key, keep=False)]
    merged = sections[key + ["ST_SECAO_INSTALADA", "QT_COMPARECIMENTO", "DS_ORIGEM_VOTO"]].merge(
        votacao_keys, on=key, how="outer", indicator=True)
    rows = []
    for turno in TURNOS:
        part = merged[merged["NR_TURNO"] == turno]
        only_detail = part[part["_merge"] == "left_only"]
        rows.append({"NR_TURNO": turno, "n_chaves_duplicadas_detalhe": int(len(detail_dups[detail_dups["NR_TURNO"] == turno])),
                     "n_chaves_duplicadas_votacao_secao": int(len(votacao_dups[votacao_dups["NR_TURNO"] == turno])),
                     "n_votaveis_repetidos_votacao_secao": int(votacao_keys.loc[votacao_keys["NR_TURNO"] == turno, "n_votaveis_repetidos"].sum()),
                     "n_so_detalhe": int(len(only_detail)),
                     "n_so_detalhe_nao_instaladas": int((only_detail["ST_SECAO_INSTALADA"] != SECAO_INSTALADA).sum()),
                     "n_so_detalhe_instaladas_comparecimento_zero": int(((only_detail["ST_SECAO_INSTALADA"] == SECAO_INSTALADA) & (only_detail["QT_COMPARECIMENTO"] == 0)).sum()),
                     "n_so_votacao_secao": int((part["_merge"] == "right_only").sum()),
                     "n_em_ambos": int((part["_merge"] == "both").sum())})
    return pd.DataFrame(rows)


def urn_model_table(sections: pd.DataFrame) -> pd.DataFrame:
    base = sections[installed_with_votes(sections)].assign(banda=reception_band(sections["recebimento"]))
    rows = []
    for (turno, model), group in base.groupby(["NR_TURNO", "DS_MODELO_URNA"], observed=True):
        lags = lag_seconds(group["recebimento"], group["prim_tot_parcial"])
        minutes_after_close = (group["recebimento"] - pd.Timestamp(f"{ELECTION_DATES[turno]} {OFFICIAL_CLOSING}")).dt.total_seconds() / 60
        bands = group["banda"].value_counts(normalize=True)
        rows.append({"NR_TURNO": turno, "DS_MODELO_URNA": model, "n_secoes": int(len(group)),
                     "recebimento_min_apos_17h_p10": float(minutes_after_close.quantile(0.1)),
                     "recebimento_min_apos_17h_mediana": float(minutes_after_close.median()),
                     "recebimento_min_apos_17h_p90": float(minutes_after_close.quantile(0.9)),
                     "lag_mediana_s": float(lags.median()),
                     **{f"share_{label}": float(bands.get(label, 0.0)) for label, _, _ in RECEPTION_BANDS}})
    return pd.DataFrame(rows)
