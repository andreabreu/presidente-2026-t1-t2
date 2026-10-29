from __future__ import annotations

import argparse
import json
import logging
import time
import unicodedata
from pathlib import Path

import pandas as pd
import requests

from tse.config import ANALYSIS_ROOT, load_config

SIDRA_BASE_URL = "https://apisidra.ibge.gov.br/values"
IBGE_LOCALIDADES_MUNICIPIOS_URL = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado"
)
CROSSWALK_TSE_IBGE_URL = (
    "https://raw.githubusercontent.com/betafcc/Municipios-Brasileiros-TSE/"
    "master/municipios_brasileiros_tse.csv"
)

ESTIMATES_TABLE = 6579
ESTIMATES_VARIABLE = 9324

CENSUS_AGE_TABLE = 9514
CENSUS_POPULATION_VARIABLE = 93
CENSUS_SEX_TOTAL = 6794
CENSUS_AGE_DECLARATION_TOTAL = 113635
CENSUS_SINGLE_AGES_16_TO_19 = (6573, 6574, 6575, 6576)
CENSUS_FIVE_YEAR_GROUPS_20_TO_99 = (
    93087, 93088, 93089, 93090, 93091, 93092, 93093, 93094,
    93095, 93096, 93097, 93098, 49108, 49109, 60040, 60041,
)
CENSUS_AGE_100_PLUS = 6653
CENSUS_YEAR = 2022
CENSUS_16PLUS_METHOD = (
    "censo2022_t9514_soma_exata_idades_16-19_simples+grupos_quinquenais_20-99+100mais"
)

UF_CODES = (
    11, 12, 13, 14, 15, 16, 17,
    21, 22, 23, 24, 25, 26, 27, 28, 29,
    31, 32, 33, 35,
    41, 42, 43,
    50, 51, 52, 53,
)

REQUEST_TIMEOUT_SECONDS = 180
MAX_RETRIES = 4
RETRY_BACKOFF_SECONDS = 5

EXPECTED_MUNICIPALITIES = 5570
EXPECTED_POPULATION_RANGE = (203_000_000, 216_000_000)
EXPECTED_ADULT_SHARE_RANGE = (0.70, 0.85)

LOG_PATH = ANALYSIS_ROOT / "logs" / "ibge.log"
logger = logging.getLogger("tse.ibge")


def configure_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler()],
    )


def raw_dir() -> Path:
    path = load_config()["external_dir"] / "raw"
    path.mkdir(parents=True, exist_ok=True)
    return path


def fetch_with_retries(url: str) -> requests.Response:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            logger.warning("attempt %d failed for %s: %s", attempt, url, error)
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise RuntimeError("unreachable")


def download_to_raw(url: str, filename: str, force: bool = False) -> Path:
    target = raw_dir() / filename
    if target.exists() and not force:
        logger.info("cached %s", target.name)
        return target
    logger.info("GET %s", url)
    response = fetch_with_retries(url)
    target.write_bytes(response.content)
    logger.info("saved %s (%d bytes)", target.name, len(response.content))
    return target


def sidra_url(table: int, territory: str, variable: int, period: str, classifications: str = "") -> str:
    return f"{SIDRA_BASE_URL}/t/{table}/{territory}/v/{variable}/p/{period}{classifications}?formato=json"


def sidra_rows_to_frame(path: Path) -> pd.DataFrame:
    records = json.loads(path.read_text(encoding="utf-8"))
    header, body = records[0], records[1:]
    frame = pd.DataFrame(body).rename(columns=header)
    frame["Valor"] = pd.to_numeric(frame["Valor"], errors="coerce")
    return frame


def download_population_estimates(force: bool) -> Path:
    url = sidra_url(ESTIMATES_TABLE, "n6/all", ESTIMATES_VARIABLE, "last")
    return download_to_raw(url, f"sidra_{ESTIMATES_TABLE}_estimativas_municipios.json", force)


def census_age_classifications() -> str:
    categories = (*CENSUS_SINGLE_AGES_16_TO_19, *CENSUS_FIVE_YEAR_GROUPS_20_TO_99, CENSUS_AGE_100_PLUS)
    ages = ",".join(str(code) for code in categories)
    return f"/c2/{CENSUS_SEX_TOTAL}/c287/{ages}/c286/{CENSUS_AGE_DECLARATION_TOTAL}"


def download_census_ages_for_uf(uf_code: int, force: bool) -> Path:
    territory = f"n6/in%20n3%20{uf_code}"
    url = sidra_url(CENSUS_AGE_TABLE, territory, CENSUS_POPULATION_VARIABLE, str(CENSUS_YEAR), census_age_classifications())
    return download_to_raw(url, f"sidra_{CENSUS_AGE_TABLE}_censo2022_idades_uf{uf_code}.json", force)


def download_census_ages(force: bool) -> list[Path]:
    return [download_census_ages_for_uf(uf_code, force) for uf_code in UF_CODES]


def download_municipalities(force: bool) -> Path:
    return download_to_raw(IBGE_LOCALIDADES_MUNICIPIOS_URL, "ibge_localidades_municipios.json", force)


def download_crosswalk(force: bool) -> Path:
    return download_to_raw(CROSSWALK_TSE_IBGE_URL, "municipios_brasileiros_tse.csv", force)


def build_estimates_frame(path: Path) -> pd.DataFrame:
    frame = sidra_rows_to_frame(path)
    return pd.DataFrame({
        "id_municipio_ibge": frame["Município (Código)"].astype(int),
        "pop_total": frame["Valor"].astype("Int64"),
        "pop_total_ano": frame["Ano (Código)"].astype(int),
    })


def build_census_16plus_frame(paths: list[Path]) -> pd.DataFrame:
    frame = pd.concat([sidra_rows_to_frame(path) for path in paths], ignore_index=True)
    frame["id_municipio_ibge"] = frame["Município (Código)"].astype(int)
    aggregated = frame.groupby("id_municipio_ibge", as_index=False)["Valor"].sum(min_count=1)
    aggregated = aggregated.rename(columns={"Valor": "pop_16mais"})
    aggregated["pop_16mais"] = aggregated["pop_16mais"].round().astype("Int64")
    aggregated["pop_16mais_ano"] = CENSUS_YEAR
    aggregated["pop_16mais_metodo"] = CENSUS_16PLUS_METHOD
    return aggregated


def build_municipalities_frame(path: Path) -> pd.DataFrame:
    records = json.loads(path.read_text(encoding="utf-8"))
    frame = pd.DataFrame(records)
    return pd.DataFrame({
        "id_municipio_ibge": frame["municipio-id"].astype(int),
        "nome_municipio": frame["municipio-nome"],
        "sigla_uf": frame["UF-sigla"],
    })


def normalize_name(name: str) -> str:
    stripped = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return " ".join(stripped.upper().replace("'", " ").split())


def build_crosswalk_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str)
    crosswalk = pd.DataFrame({
        "id_municipio_ibge": frame["codigo_ibge"].astype(int),
        "id_municipio_tse": frame["codigo_tse"].astype(int),
        "nome": frame["nome_municipio"],
        "sigla_uf": frame["uf"],
    })
    crosswalk["chave_nome_uf"] = crosswalk["nome"].map(normalize_name) + "|" + crosswalk["sigla_uf"]
    return crosswalk


def assemble_population(estimates: pd.DataFrame, adults: pd.DataFrame, municipalities: pd.DataFrame) -> pd.DataFrame:
    merged = municipalities.merge(estimates, on="id_municipio_ibge", how="left")
    merged = merged.merge(adults, on="id_municipio_ibge", how="left")
    merged["pop_16mais_ano"] = merged["pop_16mais_ano"].astype("Int64")
    merged["chave_nome_uf"] = merged["nome_municipio"].map(normalize_name) + "|" + merged["sigla_uf"]
    columns = [
        "id_municipio_ibge", "nome_municipio", "sigla_uf", "pop_total", "pop_total_ano",
        "pop_16mais", "pop_16mais_ano", "pop_16mais_metodo", "chave_nome_uf",
    ]
    return merged[columns].sort_values("id_municipio_ibge").reset_index(drop=True)


def run_sanity_checks(population: pd.DataFrame, crosswalk: pd.DataFrame) -> None:
    row_count = len(population)
    total = int(population["pop_total"].sum())
    share = population["pop_16mais"] / population["pop_total"]
    share_in_range = share.between(*EXPECTED_ADULT_SHARE_RANGE).mean()
    missing_total = int(population["pop_total"].isna().sum())
    missing_adults = int(population["pop_16mais"].isna().sum())
    matched = population["id_municipio_ibge"].isin(crosswalk["id_municipio_ibge"]).sum()

    print(f"municipios: {row_count} (esperado ~{EXPECTED_MUNICIPALITIES})")
    print(f"pop_total soma: {total:,} ano={sorted(population['pop_total_ano'].dropna().unique())}")
    print(f"pop_total dentro de {EXPECTED_POPULATION_RANGE}: {EXPECTED_POPULATION_RANGE[0] <= total <= EXPECTED_POPULATION_RANGE[1]}")
    print(f"pop_16mais soma: {int(population['pop_16mais'].sum()):,}")
    print(f"razao pop_16mais/pop_total: min={share.min():.3f} mediana={share.median():.3f} max={share.max():.3f}")
    print(f"fracao de municipios com razao em {EXPECTED_ADULT_SHARE_RANGE}: {share_in_range:.3%}")
    print(f"faltantes: pop_total={missing_total} pop_16mais={missing_adults}")
    print(f"crosswalk: {len(crosswalk)} linhas, {matched}/{row_count} municipios IBGE casados por codigo")
    logger.info(
        "sanity rows=%d total=%d share_in_range=%.4f missing_total=%d missing_adults=%d crosswalk_matched=%d",
        row_count, total, share_in_range, missing_total, missing_adults, matched,
    )


def run_pipeline(force: bool) -> None:
    external_dir = load_config()["external_dir"]
    estimates_path = download_population_estimates(force)
    census_paths = download_census_ages(force)
    municipalities_path = download_municipalities(force)
    crosswalk_path = download_crosswalk(force)

    population = assemble_population(
        build_estimates_frame(estimates_path),
        build_census_16plus_frame(census_paths),
        build_municipalities_frame(municipalities_path),
    )
    crosswalk = build_crosswalk_frame(crosswalk_path)

    population_out = external_dir / "ibge_populacao_municipal.parquet"
    crosswalk_out = external_dir / "crosswalk_tse_ibge.parquet"
    population.to_parquet(population_out, index=False)
    crosswalk.to_parquet(crosswalk_out, index=False)
    logger.info("wrote %s (%d rows) and %s (%d rows)", population_out, len(population), crosswalk_out, len(crosswalk))
    run_sanity_checks(population, crosswalk)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download IBGE population data and TSE/IBGE crosswalk.")
    parser.add_argument("--force", action="store_true", help="re-download even if raw files exist")
    arguments = parser.parse_args()
    configure_logging()
    run_pipeline(arguments.force)


if __name__ == "__main__":
    main()
