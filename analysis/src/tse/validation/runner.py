from __future__ import annotations

import logging
from dataclasses import dataclass

import duckdb
import pandas as pd

from .checks import Check

logger = logging.getLogger("tse.validation")

COMPARISON_TABLE = "cmp_current"
CLASSE_DOCUMENTAL = "documental"
GROUP_COLUMNS = ("NR_TURNO", "CD_CARGO", "SG_UF")

DELTA_SQL = """
    observed - expected AS delta_abs,
    (observed - expected) / NULLIF(ABS(expected), 0) AS delta_rel
"""


@dataclass
class CheckResult:
    check: Check
    groups: pd.DataFrame
    violations: pd.DataFrame
    summary: pd.DataFrame


def run_check(conn: duckdb.DuckDBPyConnection, check: Check) -> CheckResult:
    logger.info("check %s: %s", check.check_id, check.tipo)
    conn.execute(f"CREATE OR REPLACE TEMP TABLE {COMPARISON_TABLE} AS {check.sql}")
    groups = conn.execute(group_summary_sql(check)).df()
    violations = conn.execute(violations_sql(check)).df()
    summary = conn.execute(summary_sql(check)).df()
    if check.n_rows_sql is not None:
        groups, summary = replace_tested_counts(conn, check, groups, summary)
    conn.execute(f"DROP TABLE {COMPARISON_TABLE}")
    logger.info("check %s: n_rows=%s n_violations=%s", check.check_id,
                int(summary["n_rows_tested"].iloc[0]), int(summary["n_violations"].iloc[0]))
    return CheckResult(check, groups, violations, summary)


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def check_columns_sql(check: Check) -> str:
    return (
        f"{literal(check.check_id)} AS check_id, {literal(check.hypothesis_id)} AS hypothesis_id, "
        f"{literal(check.table)} AS source_table, {literal(check.tipo)} AS tipo, {check.exact} AS identidade_exata"
    )


def group_summary_sql(check: Check) -> str:
    return f"""
        WITH deltas AS (SELECT *, {DELTA_SQL} FROM {COMPARISON_TABLE})
        SELECT {check_columns_sql(check)}, {", ".join(GROUP_COLUMNS)},
               COUNT(*) AS n_rows_tested,
               CAST(COALESCE(SUM(is_violation::INT), 0) AS BIGINT) AS n_violations,
               COALESCE(SUM(is_violation::INT), 0) / COUNT(*) AS share_violations,
               SUM(CASE WHEN is_violation THEN ABS(COALESCE(delta_abs, observed, expected)) ELSE 0 END) AS sum_abs_delta,
               MAX(CASE WHEN is_violation THEN ABS(COALESCE(delta_abs, observed, expected)) END) AS max_abs_delta,
               SUM(expected) AS sum_expected,
               SUM(CASE WHEN is_violation THEN ABS(COALESCE(delta_abs, observed, expected)) ELSE 0 END)
                   / NULLIF(SUM(ABS(expected)), 0) AS rel_magnitude,
               MAX(CASE WHEN is_violation THEN ABS(delta_rel) END) AS max_rel_delta
        FROM deltas
        GROUP BY ALL
        ORDER BY {", ".join(GROUP_COLUMNS)}
    """


def violations_sql(check: Check) -> str:
    return f"""
        SELECT {check_columns_sql(check)}, {literal(CLASSE_DOCUMENTAL)} AS classe,
               SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO, NR_TURNO, CD_CARGO, chave_extra,
               expected, observed, {DELTA_SQL}
        FROM {COMPARISON_TABLE}
        WHERE is_violation
        ORDER BY ABS(observed - expected) DESC NULLS FIRST, SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO
    """


def summary_sql(check: Check) -> str:
    return f"""
        WITH deltas AS (SELECT *, {DELTA_SQL} FROM {COMPARISON_TABLE})
        SELECT {check_columns_sql(check)},
               COUNT(*) AS n_rows_tested,
               CAST(COALESCE(SUM(is_violation::INT), 0) AS BIGINT) AS n_violations,
               COALESCE(SUM(is_violation::INT), 0) / NULLIF(COUNT(*), 0) AS share_violations,
               SUM(CASE WHEN is_violation THEN ABS(COALESCE(delta_abs, observed, expected)) ELSE 0 END) AS sum_abs_delta,
               MAX(CASE WHEN is_violation THEN ABS(COALESCE(delta_abs, observed, expected)) END) AS max_abs_delta,
               SUM(CASE WHEN is_violation THEN ABS(COALESCE(delta_abs, observed, expected)) ELSE 0 END)
                   / NULLIF(SUM(ABS(expected)), 0) AS rel_magnitude,
               MAX(CASE WHEN is_violation THEN ABS(delta_rel) END) AS max_rel_delta
        FROM deltas
    """


def replace_tested_counts(conn: duckdb.DuckDBPyConnection, check: Check, groups: pd.DataFrame,
                          summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Para checks pré-filtrados às violações, o denominador vem de uma consulta separada."""
    tested = conn.execute(check.n_rows_sql).df()
    counted = tested.merge(groups.drop(columns=["n_rows_tested"]), on=list(GROUP_COLUMNS), how="left")
    counted["n_violations"] = counted["n_violations"].fillna(0).astype("int64")
    counted["share_violations"] = counted["n_violations"] / counted["n_rows_tested"]
    counted = counted.assign(check_id=check.check_id, hypothesis_id=check.hypothesis_id, source_table=check.table,
                             tipo=check.tipo, identidade_exata=check.exact)[list(groups.columns)]
    summary = summary.assign(n_rows_tested=int(tested["n_rows_tested"].sum()))
    summary["share_violations"] = summary["n_violations"] / summary["n_rows_tested"]
    return counted, summary
