from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict

import pandas as pd

from ..config import ANALYSIS_ROOT
from ..hypotheses import update_status
from ..io import connect
from .checks import Check, all_checks
from .descriptive import generation_timestamps, section_size_distribution, totalization_dates
from .outputs import GROUP_COLUMN_DOCS, SCRIPT, VIOLATION_COLUMN_DOCS, write_table
from .runner import CheckResult, run_check
from .sources import discover_votavel_codes, register_sources

LOG_FILE = ANALYSIS_ROOT / "logs" / "validation.log"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
logger = logging.getLogger("tse.validation")

TABLE_TITLES = {
    "val_balanco_secao": ("Identidades de balanço por seção",
                          "Para cada seção × turno × cargo de detalhe_votacao_secao, testa identidades aritméticas candidatas e reporta violações por turno/cargo/UF."),
    "val_balanco_munzona": ("Identidades de balanço por município/zona",
                            "Identidades aritméticas entre contadores de detalhe_votacao_munzona (escopo BRASIL)."),
    "val_legenda_partido": ("Identidades de voto de legenda por partido",
                            "Identidades internas de votacao_partido_munzona e consistência com votacao_candidato_munzona."),
    "val_limites_fisicos": ("Limites físicos e seções não instaladas/anuladas",
                            "Verificações de domínio: comparecimento ≤ aptos, não negatividade, seções não instaladas com votos, aptos = 0 com comparecimento."),
    "val_agregacao_niveis": ("Consistência de agregação seção → zona → município → UF → Brasil",
                             "Σ detalhe_votacao_secao comparado a detalhe_votacao_munzona em cada nível de agregação, por métrica."),
    "val_divergencia_fontes": ("Divergência entre fontes (seção × candidato × detalhe × partido)",
                               "Somas de votacao_secao vs votacao_candidato_munzona, candidato vs detalhe_munzona, partido vs detalhe_munzona e brancos/nulos de votacao_secao vs detalhe_votacao_secao."),
    "val_br_vs_brasil": ("BR vs BRASIL para Presidente e UF vs BRASIL para demais cargos",
                         "Igualdade linha a linha entre os escopos BR e BRASIL (Presidente) e entre arquivos por UF e BRASIL (demais cargos)."),
    "val_cobertura_cand": ("Cobertura do cadastro de candidatos",
                           "Todo SQ_CANDIDATO com votos existe em consulta_cand com os mesmos atributos; candidatos do cadastro sem votos listados."),
    "val_timestamps": ("Coerência temporal de carimbos",
                       "Última totalização, recebimento de BU e primeira totalização parcial comparados ao carimbo de geração do arquivo."),
}

METHOD_GROUPS = "DuckDB SQL sobre Parquet; comparação linha a linha; agregação por turno/cargo/UF; violação = lados distintos (ou desigualdade de domínio)."


def configure_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT,
                        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stderr)])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="tse.validation", description="Validação matemática dos arquivos TSE 2026")
    parser.add_argument("--only", nargs="*", default=None, help="check_ids a executar (default: todos)")
    parser.add_argument("--no-hypotheses-update", action="store_true", help="não atualizar hypotheses.yaml")
    return parser.parse_args()


def run_all(only: list[str] | None) -> tuple[list[CheckResult], dict[str, list[int]], dict[str, pd.DataFrame]]:
    conn = connect()
    register_sources(conn)
    codes = discover_votavel_codes(conn)
    logger.info("códigos NR_VOTAVEL descobertos: %s", codes)
    checks = all_checks(codes.get("branco", []), codes.get("nulo", []))
    if only:
        checks = [check for check in checks if check.check_id in set(only)]
    results = [run_check(conn, check) for check in checks]
    descriptive = {
        "val_timestamps_geracao": generation_timestamps(conn),
        "val_totalizacao_datas": totalization_dates(conn),
        "val_tamanho_secao": section_size_distribution(conn),
    }
    return results, codes, descriptive


def caveats_for(codes: dict[str, list[int]]) -> list[str]:
    return [
        "Presidente lido do escopo BR; demais cargos de escopos por UF (seção) e BRASIL (mun/zona); escopos nunca somados entre si.",
        f"Códigos de NR_VOTAVEL descobertos pelos dados: branco={codes.get('branco')}, nulo={codes.get('nulo')}; legenda = SQ_CANDIDATO negativo com nome de partido.",
        "Senador 2026 renova dois terços: cada eleitor deposita dois votos, logo comparecimento × 2 = total de votos nesse cargo.",
        "Identidades marcadas identidade_exata=False são candidatas/informativas: suas violações não entram em val_inconsistencias.",
    ]


def write_group_tables(results: list[CheckResult], codes: dict[str, list[int]]) -> None:
    by_table: dict[str, list[pd.DataFrame]] = defaultdict(list)
    hypotheses: dict[str, set[str]] = defaultdict(set)
    for result in results:
        by_table[result.check.table].append(result.groups)
        hypotheses[result.check.table].add(result.check.hypothesis_id)
    for table, frames in by_table.items():
        title, description = TABLE_TITLES[table]
        write_table(table, pd.concat(frames, ignore_index=True), title, description, sorted(hypotheses[table]),
                    GROUP_COLUMN_DOCS, METHOD_GROUPS, caveats_for(codes))


def write_consolidated_tables(results: list[CheckResult], codes: dict[str, list[int]]) -> pd.DataFrame:
    exact_violations = [r.violations for r in results if r.check.exact and not r.violations.empty]
    inconsistencias = pd.concat(exact_violations, ignore_index=True) if exact_violations else empty_violations(results)
    all_hypotheses = sorted({r.check.hypothesis_id for r in results})
    write_table("val_inconsistencias", inconsistencias, "Inconsistências linha a linha",
                "Toda linha que viola uma identidade exata ou um limite de domínio, com esperado, observado e deltas.",
                all_hypotheses, VIOLATION_COLUMN_DOCS, METHOD_GROUPS, caveats_for(codes))
    resumo = pd.concat([r.summary for r in results], ignore_index=True)
    write_table("val_resumo", resumo, "Resumo dos checks de validação",
                "Uma linha por check: linhas testadas, violações, participação e magnitude máxima.",
                all_hypotheses, GROUP_COLUMN_DOCS, METHOD_GROUPS, caveats_for(codes))
    return resumo


def empty_violations(results: list[CheckResult]) -> pd.DataFrame:
    return results[0].violations.iloc[0:0] if results else pd.DataFrame()


def write_descriptive_tables(descriptive: dict[str, pd.DataFrame], codes: dict[str, list[int]]) -> None:
    write_table("val_timestamps_geracao", descriptive["val_timestamps_geracao"], "Carimbos de geração por arquivo",
                "DT_GERACAO/HH_GERACAO distintos por dataset × escopo e janela de DT_ULTIMA_TOTALIZACAO.", ["H24"],
                {"dataset": "dataset", "scope": "escopo (UF, BR, BRASIL)", "n_rows": "linhas",
                 "n_distinct_geracao": "carimbos de geração distintos no arquivo",
                 "geracao_min": "menor carimbo", "geracao_max": "maior carimbo",
                 "totalizacao_min": "menor DT/HH_ULTIMA_TOTALIZACAO (texto)", "totalizacao_max": "maior DT/HH_ULTIMA_TOTALIZACAO",
                 "n_datas_totalizacao": "datas distintas de última totalização"},
                "DuckDB SQL; contagem de distintos e min/max.", caveats_for(codes))
    write_table("val_totalizacao_datas", descriptive["val_totalizacao_datas"], "Datas de última totalização",
                "Distribuição de DT_ULTIMA_TOTALIZACAO por turno em detalhe_votacao_munzona.", ["H24"],
                {"NR_TURNO": "turno", "DT_ULTIMA_TOTALIZACAO": "data", "n_munzona_cargo": "linhas mun/zona × cargo",
                 "n_uf": "UFs distintas", "comparecimento": "Σ QT_COMPARECIMENTO"},
                "DuckDB SQL; agregação por data.", caveats_for(codes))
    write_table("val_tamanho_secao", descriptive["val_tamanho_secao"], "Distribuição de aptos por seção (UF × turno)",
                "Percentis de QT_APTOS por UF e turno (linhas de Presidente, escopo BR) e contagens de seções atípicas.", ["H30"],
                {"SG_UF": "UF", "NR_TURNO": "turno", "n_secoes": "seções", "aptos_min": "mínimo", "aptos_max": "máximo",
                 "aptos_total": "Σ aptos", "n_aptos_zero": "seções com aptos = 0",
                 "n_aptos_zero_com_comparecimento": "seções com aptos = 0 e comparecimento > 0",
                 "n_nao_instaladas": "seções não instaladas", "n_origem_nao_urna": "seções com DS_ORIGEM_VOTO ≠ Urna Eletrônica",
                 **{f"p{int(p * 100):02d}": f"percentil {int(p * 100)} de QT_APTOS" for p in (0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99)}},
                "DuckDB quantile_cont por UF × turno.", caveats_for(codes))


def update_hypotheses(results: list[CheckResult]) -> None:
    tables_by_hypothesis: dict[str, set[str]] = defaultdict(set)
    for result in results:
        tables_by_hypothesis[result.check.hypothesis_id].add(result.check.table)
    for hypothesis_id, tables in sorted(tables_by_hypothesis.items()):
        update_status(hypothesis_id, "computed", script=SCRIPT, table=", ".join(sorted(tables | {"val_resumo", "val_inconsistencias"})))
        logger.info("hipótese %s marcada como computed", hypothesis_id)


def main() -> int:
    configure_logging()
    args = parse_args()
    results, codes, descriptive = run_all(args.only)
    write_group_tables(results, codes)
    resumo = write_consolidated_tables(results, codes)
    write_descriptive_tables(descriptive, codes)
    if not args.no_hypotheses_update and not args.only:
        update_hypotheses(results)
    with pd.option_context("display.max_rows", 200, "display.width", 250, "display.max_colwidth", 60):
        print(resumo[["check_id", "hypothesis_id", "identidade_exata", "n_rows_tested", "n_violations",
                      "share_violations", "max_abs_delta", "tipo"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
