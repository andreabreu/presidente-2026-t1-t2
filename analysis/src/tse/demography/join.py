from __future__ import annotations

import unicodedata

import duckdb
import pandas as pd

from ..config import load_config
from ..io import scan

PRESIDENT_SCOPE = "BR"
PRESIDENT_CARGO = 1
FIRST_ROUND = 1
EXTERIOR_UF = "ZZ"
CROSSWALK_FILE = "crosswalk_tse_ibge.parquet"
POPULATION_FILE = "ibge_populacao_municipal.parquet"
JOIN_BY_CODE = "codigo_tse"
JOIN_BY_NAME = "chave_nome_uf"
JOIN_BY_NAME_CORRECTED = "chave_nome_uf_corrigido"
JOIN_NONE = "sem_correspondencia"


def normalize_name_key(name: str, uf: str) -> str:
    stripped = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(character if character.isalnum() else " " for character in stripped.upper())
    return f"{' '.join(cleaned.split())}|{uf}"


def electorate_by_municipio(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    conn.register("det_pres_t1", scan("detalhe_votacao_munzona", PRESIDENT_SCOPE, turno=FIRST_ROUND, cargo=PRESIDENT_CARGO, conn=conn))
    return conn.sql(
        f"""
        select SG_UF, CD_MUNICIPIO, any_value(NM_MUNICIPIO) as NM_MUNICIPIO,
               sum(QT_APTOS)::BIGINT as QT_APTOS, sum(QT_COMPARECIMENTO)::BIGINT as QT_COMPARECIMENTO,
               sum(QT_ABSTENCOES)::BIGINT as QT_ABSTENCOES, count(*) as n_zonas
        from det_pres_t1
        where SG_UF <> '{EXTERIOR_UF}'
        group by SG_UF, CD_MUNICIPIO
        order by SG_UF, CD_MUNICIPIO
        """
    ).df()


def load_external() -> tuple[pd.DataFrame, pd.DataFrame]:
    external_dir = load_config()["external_dir"]
    return pd.read_parquet(external_dir / CROSSWALK_FILE), pd.read_parquet(external_dir / POPULATION_FILE)


def join_electorate_population(electorate: pd.DataFrame, crosswalk: pd.DataFrame, population: pd.DataFrame) -> pd.DataFrame:
    by_code = electorate.merge(
        crosswalk[["id_municipio_tse", "id_municipio_ibge"]], left_on="CD_MUNICIPIO", right_on="id_municipio_tse", how="left"
    ).drop(columns="id_municipio_tse")
    by_code["metodo_join"] = by_code["id_municipio_ibge"].notna().map({True: JOIN_BY_CODE, False: JOIN_NONE})
    unmatched = by_code["id_municipio_ibge"].isna()
    if unmatched.any():
        keys = [normalize_name_key(name, uf) for name, uf in zip(by_code.loc[unmatched, "NM_MUNICIPIO"], by_code.loc[unmatched, "SG_UF"])]
        by_name = population.drop_duplicates("chave_nome_uf").set_index("chave_nome_uf")["id_municipio_ibge"]
        fallback = pd.Series(keys, index=by_code.index[unmatched]).map(by_name)
        by_code.loc[unmatched, "id_municipio_ibge"] = fallback
        by_code.loc[fallback.notna().reindex(by_code.index, fill_value=False), "metodo_join"] = JOIN_BY_NAME
    by_code = _correct_code_matches_with_divergent_names(by_code, population)
    population_columns = ["id_municipio_ibge", "nome_municipio", "pop_total", "pop_total_ano", "pop_16mais", "pop_16mais_ano"]
    joined = by_code.merge(population[population_columns], on="id_municipio_ibge", how="left")
    joined["id_municipio_ibge"] = joined["id_municipio_ibge"].astype("Int64")
    joined["chave_nome_tse"] = [normalize_name_key(name, uf) for name, uf in zip(joined["NM_MUNICIPIO"], joined["SG_UF"])]
    joined["chave_nome_ibge"] = [normalize_name_key(name or "", uf) for name, uf in zip(joined["nome_municipio"].fillna(""), joined["SG_UF"])]
    joined["nome_divergente"] = joined["chave_nome_tse"] != joined["chave_nome_ibge"]
    return joined


def _correct_code_matches_with_divergent_names(by_code: pd.DataFrame, population: pd.DataFrame) -> pd.DataFrame:
    result = by_code.copy()
    ibge_name_by_id = population.set_index("id_municipio_ibge")["chave_nome_uf"]
    ibge_id_by_name = population.drop_duplicates("chave_nome_uf").set_index("chave_nome_uf")["id_municipio_ibge"]
    tse_keys = pd.Series([normalize_name_key(name, uf) for name, uf in zip(result["NM_MUNICIPIO"], result["SG_UF"])], index=result.index)
    matched_names = result["id_municipio_ibge"].map(ibge_name_by_id)
    divergent = (result["metodo_join"] == JOIN_BY_CODE) & (matched_names != tse_keys)
    exact_by_name = tse_keys.loc[divergent].map(ibge_id_by_name)
    correctable = exact_by_name.dropna()
    result.loc[correctable.index, "id_municipio_ibge"] = correctable
    result.loc[correctable.index, "metodo_join"] = JOIN_BY_NAME_CORRECTED
    return result


def coverage_report(joined: pd.DataFrame, population: pd.DataFrame) -> pd.DataFrame:
    total = len(joined)
    matched = joined["pop_total"].notna()
    ibge_missing = ~population["id_municipio_ibge"].isin(joined["id_municipio_ibge"].dropna())
    rows = [
        {"indicador": "municipios_tse_presidente_t1_sem_exterior", "valor": total},
        {"indicador": "municipios_com_populacao_ibge", "valor": int(matched.sum())},
        {"indicador": "cobertura_pct", "valor": round(matched.mean() * 100, 4)},
        {"indicador": "join_por_codigo_tse", "valor": int((joined["metodo_join"] == JOIN_BY_CODE).sum())},
        {"indicador": "join_por_chave_nome_uf", "valor": int((joined["metodo_join"] == JOIN_BY_NAME).sum())},
        {"indicador": "join_por_codigo_corrigido_pelo_nome", "valor": int((joined["metodo_join"] == JOIN_BY_NAME_CORRECTED).sum())},
        {"indicador": "join_por_codigo_corrigido_lista", "valor": "; ".join(joined.loc[joined["metodo_join"] == JOIN_BY_NAME_CORRECTED, "chave_nome_tse"])},
        {"indicador": "nomes_divergentes_mantidos", "valor": int(joined["nome_divergente"].sum())},
        {"indicador": "nomes_divergentes_mantidos_lista", "valor": "; ".join(joined.loc[joined["nome_divergente"], "chave_nome_tse"] + " ~ " + joined.loc[joined["nome_divergente"], "nome_municipio"].fillna(""))},
        {"indicador": "sem_correspondencia", "valor": int((joined["metodo_join"] == JOIN_NONE).sum())},
        {"indicador": "aptos_cobertos_pct", "valor": round(joined.loc[matched, "QT_APTOS"].sum() / joined["QT_APTOS"].sum() * 100, 4)},
        {"indicador": "municipios_ibge_sem_tse", "valor": int(ibge_missing.sum())},
        {"indicador": "municipios_ibge_sem_tse_lista", "valor": "; ".join(population.loc[ibge_missing, "chave_nome_uf"])},
        {"indicador": "municipios_sem_pop_16mais", "valor": int(joined["pop_16mais"].isna().sum())},
        {"indicador": "municipios_tse_sem_correspondencia_lista", "valor": "; ".join(joined.loc[~matched, "NM_MUNICIPIO"] + "|" + joined.loc[~matched, "SG_UF"])},
    ]
    report = pd.DataFrame(rows)
    report["valor"] = report["valor"].astype(str)
    return report
