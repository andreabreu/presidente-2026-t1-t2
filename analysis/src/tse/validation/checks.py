from __future__ import annotations

from dataclasses import dataclass

from .identities import (
    MUNZONA_IDENTITIES,
    PARTIDO_IDENTITIES,
    SECAO_IDENTITIES,
    LinearIdentity,
    identity_sql,
)
from .sources import CARGOS_COM_VOTO, sql_list

TABLE_BALANCO_SECAO = "val_balanco_secao"
TABLE_BALANCO_MUNZONA = "val_balanco_munzona"
TABLE_LEGENDA_PARTIDO = "val_legenda_partido"
TABLE_LIMITES_FISICOS = "val_limites_fisicos"
TABLE_AGREGACAO_NIVEIS = "val_agregacao_niveis"
TABLE_DIVERGENCIA_FONTES = "val_divergencia_fontes"
TABLE_BR_VS_BRASIL = "val_br_vs_brasil"
TABLE_COBERTURA_CAND = "val_cobertura_cand"
TABLE_TIMESTAMPS = "val_timestamps"

SECAO_KEYS = ("SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO", "CD_CARGO")
MUNZONA_KEYS = ("SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_TURNO", "CD_CARGO")
OUTPUT_KEYS = ("SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO", "CD_CARGO", "chave_extra")

LEVEL_KEYS = {
    "zona": ("SG_UF", "CD_MUNICIPIO", "NR_ZONA"),
    "municipio": ("SG_UF", "CD_MUNICIPIO"),
    "uf": ("SG_UF",),
    "brasil": (),
}

SECAO_COUNTERS = (
    "QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES", "QT_VOTOS_NOMINAIS",
    "QT_VOTOS_BRANCOS", "QT_VOTOS_NULOS", "QT_VOTOS_LEGENDA", "QT_VOTOS_ANULADOS_APU_SEP",
)
SECAO_INSTALADA = "Sim"
SECAO_ANULADA = "Sim"
DESTINO_LEGENDA_PATTERN = "%LEGENDA%"
TIMESTAMP_FORMAT = "%d/%m/%Y %H:%M:%S"

VIOLATION_DIFFERENT = "expected IS DISTINCT FROM observed"
VIOLATION_OBSERVED_ABOVE = "observed > expected"
VIOLATION_OBSERVED_BELOW = "observed < expected"
VIOLATION_ALWAYS = "TRUE"


@dataclass(frozen=True)
class Check:
    check_id: str
    hypothesis_id: str
    table: str
    tipo: str
    sql: str
    exact: bool = True
    n_rows_sql: str | None = None


def key_select(present: tuple[str, ...], alias: str = "", extra: str = "NULL") -> str:
    prefix = f"{alias}." if alias else ""
    parts = []
    for key in OUTPUT_KEYS[:-1]:
        parts.append(f"{prefix}{key} AS {key}" if key in present else f"NULL AS {key}")
    parts.append(f"CAST({extra} AS VARCHAR) AS chave_extra")
    return ", ".join(parts)


def comparison_sql(keys: str, expected: str, observed: str, source: str, violation: str, where: str = "TRUE") -> str:
    return f"""
        SELECT {keys},
               CAST({expected} AS DOUBLE) AS expected,
               CAST({observed} AS DOUBLE) AS observed,
               ({violation}) AS is_violation
        FROM ({source}) AS base
        WHERE {where}
    """


def identity_check(identity: LinearIdentity, view: str, keys: tuple[str, ...], table: str,
                   extra_key: str = "NULL") -> Check:
    lhs, rhs = identity_sql(identity)
    sql = comparison_sql(key_select(keys, extra=extra_key), lhs, rhs, f"SELECT * FROM {view}", VIOLATION_DIFFERENT)
    return Check(identity.check_id, identity.hypothesis_id, table, identity.description, sql, identity.exact)


def balance_checks() -> list[Check]:
    return [
        *(identity_check(item, "detalhe_secao", SECAO_KEYS, TABLE_BALANCO_SECAO) for item in SECAO_IDENTITIES),
        *(identity_check(item, "detalhe_munzona", MUNZONA_KEYS, TABLE_BALANCO_MUNZONA) for item in MUNZONA_IDENTITIES),
        *(identity_check(item, "partido_munzona", MUNZONA_KEYS, TABLE_LEGENDA_PARTIDO, extra_key="NR_PARTIDO")
          for item in PARTIDO_IDENTITIES),
    ]


def physical_limit_checks() -> list[Check]:
    secao = "SELECT * FROM detalhe_secao"
    least_counter = "LEAST(" + ", ".join(SECAO_COUNTERS) + ")"
    votes_by_section = f"""
        SELECT d.*, COALESCE(v.votos, 0) AS votos_secao
        FROM detalhe_secao d
        LEFT JOIN (
            SELECT {', '.join(SECAO_KEYS)}, SUM(QT_VOTOS) AS votos FROM votacao_secao GROUP BY ALL
        ) v USING ({', '.join(SECAO_KEYS)})
        WHERE d.ST_SECAO_INSTALADA <> '{SECAO_INSTALADA}'
    """
    return [
        Check("LF01", "H04", TABLE_LIMITES_FISICOS, "comparecimento <= aptos (seção)",
              comparison_sql(key_select(SECAO_KEYS), "QT_APTOS", "QT_COMPARECIMENTO", secao, VIOLATION_OBSERVED_ABOVE)),
        Check("LF02", "H04", TABLE_LIMITES_FISICOS, "nenhum contador QT_* negativo (seção)",
              comparison_sql(key_select(SECAO_KEYS), "0", least_counter, secao, VIOLATION_OBSERVED_BELOW)),
        Check("LF03", "H27", TABLE_LIMITES_FISICOS, "seção não instalada com comparecimento = 0",
              comparison_sql(key_select(SECAO_KEYS), "0", "QT_COMPARECIMENTO", secao, VIOLATION_DIFFERENT,
                             where=f"ST_SECAO_INSTALADA <> '{SECAO_INSTALADA}'")),
        Check("LF04", "H27", TABLE_LIMITES_FISICOS, "seção não instalada sem votos em votacao_secao",
              comparison_sql(key_select(SECAO_KEYS), "0", "votos_secao", votes_by_section, VIOLATION_DIFFERENT)),
        Check("LF05", "H27", TABLE_LIMITES_FISICOS, "seção anulada (listagem: comparecimento)",
              comparison_sql(key_select(SECAO_KEYS), "0", "QT_COMPARECIMENTO", secao, VIOLATION_ALWAYS,
                             where=f"ST_SECAO_ANULADA = '{SECAO_ANULADA}'")),
        Check("LF06", "H30", TABLE_LIMITES_FISICOS, "aptos = 0 implica comparecimento = 0 (seção)",
              comparison_sql(key_select(SECAO_KEYS), "0", "QT_COMPARECIMENTO", secao, VIOLATION_DIFFERENT,
                             where="QT_APTOS = 0")),
        Check("LF07", "H04", TABLE_LIMITES_FISICOS, "QT_VOTOS >= 0 (votacao_secao)",
              comparison_sql(key_select(SECAO_KEYS, extra="NR_VOTAVEL"), "0", "QT_VOTOS",
                             "SELECT * FROM votacao_secao", VIOLATION_OBSERVED_BELOW, where="QT_VOTOS < 0"),
              n_rows_sql="SELECT NR_TURNO, CD_CARGO, SG_UF, COUNT(*) AS n_rows_tested FROM votacao_secao GROUP BY ALL"),
        Check("LF08", "H04", TABLE_LIMITES_FISICOS, "comparecimento <= aptos (mun/zona)",
              comparison_sql(key_select(MUNZONA_KEYS), "QT_APTOS", "QT_COMPARECIMENTO",
                             "SELECT * FROM detalhe_munzona", VIOLATION_OBSERVED_ABOVE)),
    ]


def aggregated_pair_sql(left: str, left_keys: tuple[str, ...], left_metrics: dict[str, str],
                        right: str, right_keys: tuple[str, ...], right_metrics: dict[str, str],
                        level_keys: tuple[str, ...]) -> str:
    group_keys = (*level_keys, "NR_TURNO", "CD_CARGO")
    left_sums = ", ".join(f"SUM({expr}) AS l_{name}" for name, expr in left_metrics.items())
    right_sums = ", ".join(f"SUM({expr}) AS r_{name}" for name, expr in right_metrics.items())
    keys = ", ".join(group_keys)
    return f"""
        SELECT {", ".join(f"COALESCE(l.{k}, r.{k}) AS {k}" for k in group_keys)},
               {", ".join(f"l.l_{n}" for n in left_metrics)},
               {", ".join(f"r.r_{n}" for n in right_metrics)}
        FROM (SELECT {keys}, {left_sums} FROM {as_source(left)} GROUP BY ALL) l
        FULL JOIN (SELECT {keys}, {right_sums} FROM {as_source(right)} GROUP BY ALL) r USING ({keys})
    """


def as_source(table_or_query: str) -> str:
    text = table_or_query.strip()
    return f"({text})" if text.upper().startswith("SELECT") else text


SECAO_TO_MUNZONA_METRICS = {
    "QT_APTOS": ("QT_APTOS", "QT_APTOS", True),
    "QT_COMPARECIMENTO": ("QT_COMPARECIMENTO", "QT_COMPARECIMENTO", True),
    "QT_ABSTENCOES": ("QT_ABSTENCOES", "QT_ABSTENCOES", True),
    "QT_VOTOS_BRANCOS": ("QT_VOTOS_BRANCOS", "QT_VOTOS_BRANCOS", True),
    "QT_VOTOS_NULOS": ("QT_VOTOS_NULOS", "QT_VOTOS_NULOS", True),
    "QT_VOTOS_NULOS_vs_TOTAL_NULOS": ("QT_VOTOS_NULOS", "QT_TOTAL_VOTOS_NULOS", False),
    "N_SECOES_vs_PRINCIPAIS": ("1", "QT_SECOES_PRINCIPAIS", True),
    "N_SECOES_vs_TOTAL_SECOES": ("1", "QT_TOTAL_SECOES", False),
    "NOMINAIS_mais_LEGENDA_vs_CONCORRENTES_mais_TECNICOS": (
        "QT_VOTOS_NOMINAIS + QT_VOTOS_LEGENDA", "QT_VOTOS_CONCORRENTES + QT_VOTOS_NULOS_TECNICOS", True),
    "NOMINAIS_vs_VALIDOS_CONVR_ANULADOS_SUBJUD_TECNICOS": (
        "QT_VOTOS_NOMINAIS",
        "QT_VOTOS_NOMINAIS_VALIDOS + QT_VOTOS_NOM_CONVR_LEG_VALIDOS + QT_VOTOS_NOMINAIS_ANULADOS"
        " + QT_VOTOS_NOMINAIS_ANUL_SUBJUD + QT_VOTOS_NULOS_TECNICOS", False),
    "LEGENDA_vs_LEG_VALIDOS_ANULADOS_SUBJUD": (
        "QT_VOTOS_LEGENDA", "QT_VOTOS_LEG_VALIDOS + QT_VOTOS_LEGENDA_ANULADOS + QT_VOTOS_LEGENDA_ANUL_SUBJUD", False),
}


def aggregation_checks() -> list[Check]:
    checks = []
    for metric, (secao_expr, munzona_expr, exact) in SECAO_TO_MUNZONA_METRICS.items():
        levels = LEVEL_KEYS if exact else {"zona": LEVEL_KEYS["zona"]}
        for level, level_keys in levels.items():
            pair = aggregated_pair_sql("detalhe_secao", SECAO_KEYS, {"m": secao_expr},
                                       "detalhe_munzona", MUNZONA_KEYS, {"m": munzona_expr}, level_keys)
            sql = comparison_sql(key_select((*level_keys, "NR_TURNO", "CD_CARGO"), extra=f"'{metric}'"),
                                 "r_m", "l_m", pair, VIOLATION_DIFFERENT)
            checks.append(Check(f"AG_{level}_{metric}", "H05", TABLE_AGREGACAO_NIVEIS,
                                f"Σ detalhe_secao = detalhe_munzona [{level}] {metric}", sql, exact))
    return checks


def source_divergence_checks(branco_codes: list[int], nulo_codes: list[int]) -> list[Check]:
    checks = []
    candidate_votes = "SELECT * FROM votacao_secao WHERE TRY_CAST(SQ_CANDIDATO AS BIGINT) > 0"
    for level, level_keys in LEVEL_KEYS.items():
        pair = aggregated_pair_sql(candidate_votes, SECAO_KEYS, {"v": "QT_VOTOS"},
                                   "candidato_munzona", MUNZONA_KEYS, {"v": "QT_VOTOS_NOMINAIS"},
                                   (*level_keys, "SQ_CANDIDATO"))
        sql = comparison_sql(key_select((*level_keys, "NR_TURNO", "CD_CARGO"), extra="SQ_CANDIDATO"),
                             "COALESCE(r_v, 0)", "COALESCE(l_v, 0)", pair, VIOLATION_DIFFERENT)
        checks.append(Check(f"DF01_{level}", "H06", TABLE_DIVERGENCIA_FONTES,
                            f"Σ votacao_secao QT_VOTOS por candidato = candidato_munzona QT_VOTOS_NOMINAIS [{level}]", sql))

    nominal_not_legend = (
        f"SELECT * FROM candidato_munzona WHERE upper(NM_TIPO_DESTINACAO_VOTOS) NOT LIKE '{DESTINO_LEGENDA_PATTERN}'"
    )
    munzona_targets = {
        "DF02": ("candidato_munzona", "QT_VOTOS_NOMINAIS_VALIDOS", "QT_VOTOS_NOMINAIS_VALIDOS", True,
                 "Σ candidato QT_VOTOS_NOMINAIS_VALIDOS = detalhe_munzona QT_VOTOS_NOMINAIS_VALIDOS"),
        "DF03": ("candidato_munzona", "QT_VOTOS_NOMINAIS",
                 "QT_VOTOS_NOMINAIS_VALIDOS + QT_VOTOS_NOMINAIS_ANULADOS + QT_VOTOS_NOMINAIS_ANUL_SUBJUD", False,
                 "Σ candidato QT_VOTOS_NOMINAIS = detalhe_munzona válidos + anulados + anulados_subjud"),
        "DF04": (nominal_not_legend, "QT_VOTOS_NOMINAIS",
                 "QT_VOTOS_NOMINAIS_VALIDOS + QT_VOTOS_NOMINAIS_ANULADOS + QT_VOTOS_NOMINAIS_ANUL_SUBJUD", True,
                 "Σ candidato QT_VOTOS_NOMINAIS (destino ≠ legenda) = detalhe_munzona válidos + anulados + anulados_subjud"),
        "DF05": ("partido_munzona", "QT_TOTAL_VOTOS_LEG_VALIDOS", "QT_TOTAL_VOTOS_LEG_VALIDOS", True,
                 "Σ partido QT_TOTAL_VOTOS_LEG_VALIDOS = detalhe_munzona QT_TOTAL_VOTOS_LEG_VALIDOS"),
        "DF06": ("partido_munzona", "QT_VOTOS_NOMINAIS_VALIDOS", "QT_VOTOS_NOMINAIS_VALIDOS", True,
                 "Σ partido QT_VOTOS_NOMINAIS_VALIDOS = detalhe_munzona QT_VOTOS_NOMINAIS_VALIDOS"),
    }
    for check_id, (left, left_expr, right_expr, exact, tipo) in munzona_targets.items():
        pair = aggregated_pair_sql(left, MUNZONA_KEYS, {"v": left_expr},
                                   "detalhe_munzona", MUNZONA_KEYS, {"v": right_expr}, LEVEL_KEYS["zona"])
        sql = comparison_sql(key_select(MUNZONA_KEYS), "r_v", "l_v", pair, VIOLATION_DIFFERENT)
        checks.append(Check(check_id, "H07" if "partido" not in left else "H09", TABLE_DIVERGENCIA_FONTES, tipo, sql, exact))

    orphan_candidate_votes = """
        SELECT s.*
        FROM votacao_secao s
        ANTI JOIN (SELECT DISTINCT NR_TURNO, CD_CARGO, SQ_CANDIDATO FROM candidato_munzona) c
          USING (NR_TURNO, CD_CARGO, SQ_CANDIDATO)
        WHERE TRY_CAST(s.SQ_CANDIDATO AS BIGINT) > 0
    """
    legend_votes_without_party = f"""
        SELECT s.*
        FROM votacao_secao s
        ANTI JOIN (SELECT DISTINCT SG_UF, NR_TURNO, CD_CARGO, NR_PARTIDO FROM partido_munzona) p
          ON p.SG_UF = s.SG_UF AND p.NR_TURNO = s.NR_TURNO AND p.CD_CARGO = s.CD_CARGO AND p.NR_PARTIDO = s.NR_VOTAVEL
        WHERE TRY_CAST(s.SQ_CANDIDATO AS BIGINT) < 0 AND s.NR_VOTAVEL NOT IN ({sql_list(branco_codes + nulo_codes)})
    """
    technical_null_sources = {
        "DF08": (f"{orphan_candidate_votes} UNION ALL {legend_votes_without_party}", True,
                 "Σ votacao_secao (candidato ausente em candidato_munzona + legenda de partido ausente em partido_munzona)"
                 " = detalhe_munzona QT_VOTOS_NULOS_TECNICOS"),
        "DF09": (orphan_candidate_votes, False,
                 "Σ votacao_secao de SQ_CANDIDATO ausente em candidato_munzona = detalhe_munzona QT_VOTOS_NULOS_TECNICOS"),
    }
    for check_id, (source, exact, tipo) in technical_null_sources.items():
        pair = aggregated_pair_sql(source, SECAO_KEYS, {"v": "QT_VOTOS"},
                                   "detalhe_munzona", MUNZONA_KEYS, {"v": "QT_VOTOS_NULOS_TECNICOS"}, LEVEL_KEYS["zona"])
        checks.append(Check(check_id, "H06", TABLE_DIVERGENCIA_FONTES, tipo,
                            comparison_sql(key_select(MUNZONA_KEYS), "COALESCE(r_v, 0)", "COALESCE(l_v, 0)", pair,
                                           VIOLATION_DIFFERENT), exact))

    party_pair = aggregated_pair_sql("candidato_munzona", MUNZONA_KEYS, {"v": "QT_VOTOS_NOMINAIS_VALIDOS"},
                                     "partido_munzona", MUNZONA_KEYS, {"v": "QT_VOTOS_NOMINAIS_VALIDOS"},
                                     (*LEVEL_KEYS["zona"], "NR_PARTIDO"))
    checks.append(Check("LP02", "H09", TABLE_LEGENDA_PARTIDO,
                        "Σ candidato QT_VOTOS_NOMINAIS_VALIDOS por partido = partido_munzona QT_VOTOS_NOMINAIS_VALIDOS",
                        comparison_sql(key_select(MUNZONA_KEYS, extra="NR_PARTIDO"), "COALESCE(r_v, 0)",
                                       "COALESCE(l_v, 0)", party_pair, VIOLATION_DIFFERENT)))

    votavel_classes = {
        "BRANCOS": (f"NR_VOTAVEL IN ({sql_list(branco_codes)})", "QT_VOTOS_BRANCOS"),
        "NULOS": (f"NR_VOTAVEL IN ({sql_list(nulo_codes)})", "QT_VOTOS_NULOS"),
        "NOMINAIS": ("TRY_CAST(SQ_CANDIDATO AS BIGINT) > 0", "QT_VOTOS_NOMINAIS"),
        "LEGENDA": (f"TRY_CAST(SQ_CANDIDATO AS BIGINT) < 0 AND NR_VOTAVEL NOT IN ({sql_list(branco_codes + nulo_codes)})",
                    "QT_VOTOS_LEGENDA"),
        "TOTAL": ("TRUE", "QT_VOTOS_NOMINAIS + QT_VOTOS_LEGENDA + QT_VOTOS_BRANCOS + QT_VOTOS_NULOS"),
    }
    for name, (predicate, secao_expr) in votavel_classes.items():
        pair = aggregated_pair_sql(f"SELECT * FROM votacao_secao WHERE {predicate}", SECAO_KEYS, {"v": "QT_VOTOS"},
                                   "detalhe_secao", SECAO_KEYS, {"v": secao_expr}, (*LEVEL_KEYS["zona"], "NR_SECAO"))
        sql = comparison_sql(key_select(SECAO_KEYS, extra=f"'{name}'"), "COALESCE(r_v, 0)", "COALESCE(l_v, 0)",
                             pair, VIOLATION_DIFFERENT)
        checks.append(Check(f"DF07_{name}", "H10", TABLE_DIVERGENCIA_FONTES,
                            f"Σ votacao_secao ({name}) = detalhe_secao {secao_expr}", sql))
    return checks


def scope_pair_sql(dataset: str, scope_a: str, scope_b_filter: str, keys: tuple[str, ...], metric: str,
                   extra_key: str | None = None) -> str:
    join_keys = (*keys, extra_key) if extra_key else keys
    keys_sql = ", ".join(join_keys)
    return f"""
        SELECT {", ".join(f"COALESCE(a.{k}, b.{k}) AS {k}" for k in join_keys)},
               a.{metric} AS metric_a, b.{metric} AS metric_b
        FROM (SELECT * FROM raw_{dataset} WHERE scope = '{scope_a}') a
        FULL JOIN (SELECT * FROM raw_{dataset} WHERE {scope_b_filter}) b USING ({keys_sql})
    """


def br_vs_brasil_checks() -> list[Check]:
    presidente_brasil = "scope = 'BRASIL' AND CD_CARGO = 1"
    uf_scopes = "scope NOT IN ('BR', 'BRASIL', 'ZZ')"
    specs = [
        ("BB01", "votacao_candidato_munzona", "BR", presidente_brasil, MUNZONA_KEYS, "QT_VOTOS_NOMINAIS", "SQ_CANDIDATO",
         "candidato_munzona Presidente: BR = BRASIL (QT_VOTOS_NOMINAIS, chave a chave)"),
        ("BB02", "detalhe_votacao_munzona", "BR", presidente_brasil, MUNZONA_KEYS, "QT_COMPARECIMENTO", None,
         "detalhe_munzona Presidente: BR = BRASIL (QT_COMPARECIMENTO, chave a chave)"),
        ("BB03", "detalhe_votacao_munzona", "BR", presidente_brasil, MUNZONA_KEYS, "QT_APTOS", None,
         "detalhe_munzona Presidente: BR = BRASIL (QT_APTOS, chave a chave)"),
        ("BB04", "detalhe_votacao_secao", "BR", presidente_brasil, SECAO_KEYS, "QT_COMPARECIMENTO", None,
         "detalhe_secao Presidente: BR = BRASIL (QT_COMPARECIMENTO, chave a chave)"),
        ("BB05", "detalhe_votacao_secao", "BR", presidente_brasil, SECAO_KEYS, "QT_VOTOS_NOMINAIS", None,
         "detalhe_secao Presidente: BR = BRASIL (QT_VOTOS_NOMINAIS, chave a chave)"),
    ]
    checks = []
    for check_id, dataset, scope_a, filter_b, keys, metric, extra, tipo in specs:
        pair = scope_pair_sql(dataset, scope_a, filter_b, keys, metric, extra)
        sql = comparison_sql(key_select(keys, extra=extra or "NULL"), "metric_a", "metric_b", pair, VIOLATION_DIFFERENT)
        checks.append(Check(check_id, "H08", TABLE_BR_VS_BRASIL, tipo, sql))
    uf_pair = f"""
        SELECT {", ".join(f"COALESCE(a.{k}, b.{k}) AS {k}" for k in SECAO_KEYS)},
               a.QT_COMPARECIMENTO AS metric_a, b.QT_COMPARECIMENTO AS metric_b
        FROM (SELECT * FROM raw_detalhe_votacao_secao WHERE {uf_scopes} AND CD_CARGO <> 1) a
        FULL JOIN (SELECT * FROM raw_detalhe_votacao_secao WHERE scope = 'BRASIL' AND CD_CARGO <> 1) b
        USING ({", ".join(SECAO_KEYS)})
    """
    checks.append(Check("BB06", "H08", TABLE_BR_VS_BRASIL,
                        "detalhe_secao demais cargos: UF = BRASIL (QT_COMPARECIMENTO, chave a chave)",
                        comparison_sql(key_select(SECAO_KEYS), "metric_a", "metric_b", uf_pair, VIOLATION_DIFFERENT)))
    return checks


def candidate_coverage_checks() -> list[Check]:
    votes = """
        SELECT DISTINCT SG_UF, NR_TURNO, CD_CARGO, SQ_CANDIDATO, NR_CANDIDATO, SG_PARTIDO, DS_SIT_TOT_TURNO
        FROM candidato_munzona
    """
    joined = f"""
        SELECT v.*, k.SQ_CANDIDATO AS k_sq, k.NR_CANDIDATO AS k_nr, k.SG_PARTIDO AS k_partido,
               k.DS_SIT_TOT_TURNO AS k_sit
        FROM ({votes}) v
        LEFT JOIN consulta_cand k USING (NR_TURNO, CD_CARGO, SQ_CANDIDATO)
    """
    keys = key_select(("SG_UF", "NR_TURNO", "CD_CARGO"), extra="SQ_CANDIDATO")
    attribute_checks = [
        ("CC01", "SQ_CANDIDATO com votos existe em consulta_cand", "(k_sq IS NOT NULL)::INT"),
        ("CC02", "NR_CANDIDATO igual entre candidato_munzona e consulta_cand", "(NR_CANDIDATO = k_nr)::INT"),
        ("CC03", "SG_PARTIDO igual entre candidato_munzona e consulta_cand", "(SG_PARTIDO = k_partido)::INT"),
        ("CC04", "DS_SIT_TOT_TURNO igual entre candidato_munzona e consulta_cand", "(DS_SIT_TOT_TURNO = k_sit)::INT"),
    ]
    checks = [
        Check(check_id, "H29", TABLE_COBERTURA_CAND, tipo,
              comparison_sql(keys, "1", f"COALESCE({observed}, 0)", joined, VIOLATION_DIFFERENT))
        for check_id, tipo, observed in attribute_checks
    ]
    secao_votes = """
        SELECT v.SG_UF, v.NR_TURNO, v.CD_CARGO, v.SQ_CANDIDATO, v.NR_VOTAVEL, k.NR_CANDIDATO AS k_nr
        FROM (SELECT DISTINCT SG_UF, NR_TURNO, CD_CARGO, SQ_CANDIDATO, NR_VOTAVEL
              FROM votacao_secao WHERE TRY_CAST(SQ_CANDIDATO AS BIGINT) > 0) v
        LEFT JOIN consulta_cand k USING (NR_TURNO, CD_CARGO, SQ_CANDIDATO)
    """
    checks.append(Check("CC05", "H29", TABLE_COBERTURA_CAND,
                        "SQ_CANDIDATO de votacao_secao existe em consulta_cand com NR_VOTAVEL = NR_CANDIDATO",
                        comparison_sql(keys, "1", "COALESCE((NR_VOTAVEL = k_nr)::INT, 0)", secao_votes, VIOLATION_DIFFERENT)))
    registry_without_votes = f"""
        SELECT k.SG_UF, k.NR_TURNO, k.CD_CARGO, k.SQ_CANDIDATO, k.DS_SIT_TOT_TURNO, v.SQ_CANDIDATO AS v_sq
        FROM consulta_cand k
        LEFT JOIN (SELECT DISTINCT NR_TURNO, CD_CARGO, SQ_CANDIDATO FROM candidato_munzona) v
          USING (NR_TURNO, CD_CARGO, SQ_CANDIDATO)
        WHERE k.CD_CARGO IN ({sql_list(list(CARGOS_COM_VOTO))})
    """
    checks.append(Check("CC06", "H29", TABLE_COBERTURA_CAND,
                        "candidato de consulta_cand (cargos com voto) possui linhas em candidato_munzona",
                        comparison_sql(key_select(("SG_UF", "NR_TURNO", "CD_CARGO"),
                                                  extra="SQ_CANDIDATO || ' | ' || DS_SIT_TOT_TURNO"),
                                       "1", "(v_sq IS NOT NULL)::INT", registry_without_votes, VIOLATION_DIFFERENT),
                        exact=False))
    return checks


def epoch(date_column: str, time_column: str) -> str:
    return f"epoch(TRY_STRPTIME({date_column} || ' ' || {time_column}, '{TIMESTAMP_FORMAT}'))"


def epoch_single(column: str) -> str:
    return f"epoch(TRY_STRPTIME({column}, '{TIMESTAMP_FORMAT}'))"


def timestamp_checks() -> list[Check]:
    generation = epoch("DT_GERACAO", "HH_GERACAO")
    return [
        Check("TS01", "H24", TABLE_TIMESTAMPS, "detalhe_munzona: última totalização <= geração do arquivo",
              comparison_sql(key_select(MUNZONA_KEYS), generation, epoch("DT_ULTIMA_TOTALIZACAO", "HH_ULTIMA_TOTALIZACAO"),
                             "SELECT * FROM detalhe_munzona", VIOLATION_OBSERVED_ABOVE)),
        Check("TS02", "H24", TABLE_TIMESTAMPS, "detalhe_secao: recebimento do BU <= geração do arquivo",
              comparison_sql(key_select(SECAO_KEYS), generation, epoch_single("DT_RECEBIMENTO_BU_HOR_TSE"),
                             "SELECT * FROM detalhe_secao", VIOLATION_OBSERVED_ABOVE)),
        Check("TS03", "H24", TABLE_TIMESTAMPS, "detalhe_secao: primeira totalização parcial <= geração do arquivo",
              comparison_sql(key_select(SECAO_KEYS), generation, epoch_single("DT_PRIM_TOT_PARCIAL_HOR_TSE"),
                             "SELECT * FROM detalhe_secao", VIOLATION_OBSERVED_ABOVE)),
        Check("TS04", "H24", TABLE_TIMESTAMPS, "detalhe_secao: recebimento do BU <= primeira totalização parcial",
              comparison_sql(key_select(SECAO_KEYS), epoch_single("DT_PRIM_TOT_PARCIAL_HOR_TSE"),
                             epoch_single("DT_RECEBIMENTO_BU_HOR_TSE"), "SELECT * FROM detalhe_secao",
                             VIOLATION_OBSERVED_ABOVE), exact=False),
    ]


def all_checks(branco_codes: list[int], nulo_codes: list[int]) -> list[Check]:
    return [
        *balance_checks(),
        *physical_limit_checks(),
        *aggregation_checks(),
        *source_divergence_checks(branco_codes, nulo_codes),
        *br_vs_brasil_checks(),
        *candidate_coverage_checks(),
        *timestamp_checks(),
    ]
