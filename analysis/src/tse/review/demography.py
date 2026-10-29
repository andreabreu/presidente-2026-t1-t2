from __future__ import annotations

import pandas as pd

PERCENT = 100.0


def crosswalk_rotations(review: pd.DataFrame, crosswalk: pd.DataFrame, population: pd.DataFrame) -> pd.DataFrame:
    """Para cada correção por nome, mostra o que o crosswalk original dizia e para qual nome IBGE apontava."""
    corrected = review[review.metodo_join == "chave_nome_uf_corrigido"][["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "id_municipio_ibge"]]
    original = crosswalk.rename(columns={"id_municipio_tse": "CD_MUNICIPIO", "id_municipio_ibge": "ibge_crosswalk"})[["CD_MUNICIPIO", "ibge_crosswalk"]]
    names = population.set_index("id_municipio_ibge")["nome_municipio"]
    frame = corrected.merge(original, on="CD_MUNICIPIO", how="left")
    frame["nome_ibge_crosswalk"] = frame.ibge_crosswalk.map(names)
    frame["nome_ibge_corrigido"] = frame.id_municipio_ibge.map(names)
    frame["correcao_coerente"] = frame.nome_ibge_corrigido.str.upper().str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii") == frame.NM_MUNICIPIO.str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii")
    return frame


def flag_rates_by_denominator(review: pd.DataFrame, national_share_16plus: float) -> pd.DataFrame:
    denominators = {
        "pop_16mais_censo_2022": review.pop_16mais,
        "pop_total_estimativa_2026": review.pop_total,
        "pop_total_2026_x_share16_nacional": review.pop_total * national_share_16plus,
    }
    rows = []
    for name, denominator in denominators.items():
        valid = denominator.notna() & (denominator > 0)
        flagged = review.QT_APTOS[valid] > denominator[valid]
        rows.append({
            "denominador": name, "n_municipios": int(valid.sum()), "share_flag": float(flagged.mean()),
            "share_aptos_em_municipios_flag": float(review.QT_APTOS[valid][flagged].sum() / review.QT_APTOS[valid].sum()),
            "razao_agregada": float(review.QT_APTOS[valid].sum() / denominator[valid].sum()),
            "mediana_razao": float((review.QT_APTOS[valid] / denominator[valid]).median()),
        })
    return pd.DataFrame(rows)


def flag_rate_by_porte(review: pd.DataFrame) -> pd.DataFrame:
    return review.groupby("porte").agg(n=("flag_aptos_maior_pop16", "size"), share_flag=("flag_aptos_maior_pop16", "mean"), mediana_razao=("aptos_pop_16mais", "median")).reset_index()


def national_share_16plus(population: pd.DataFrame) -> float:
    valid = population.pop_16mais.notna()
    return float(population.pop_16mais[valid].sum() / population.pop_total[valid].sum())
