from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

CD_CARGO_PRESIDENTE = 1
CD_CARGO_GOVERNADOR = 3
CD_CARGO_SENADOR = 5
CD_CARGO_DEPUTADO_FEDERAL = 6
CD_CARGO_DEPUTADO_ESTADUAL = 7
CD_CARGO_DEPUTADO_DISTRITAL = 8

SENATE_SEATS_RENEWED_2026 = 2
SINGLE_VOTE = 1

COMPARECIMENTO = "QT_COMPARECIMENTO"


@dataclass(frozen=True)
class LinearIdentity:
    """lhs == rhs, ambos combinações lineares inteiras de colunas.

    ``scale_comparecimento_by_seats`` multiplica QT_COMPARECIMENTO pelo número de
    votos que cada eleitor deposita no cargo (Senador 2026 renova 2/3: dois votos).
    """

    check_id: str
    description: str
    lhs: Mapping[str, int]
    rhs: Mapping[str, int]
    scale_comparecimento_by_seats: bool = False
    exact: bool = True
    hypothesis_id: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def columns(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys([*self.lhs, *self.rhs]))


def votes_per_voter(cd_cargo: int) -> int:
    return SENATE_SEATS_RENEWED_2026 if cd_cargo == CD_CARGO_SENADOR else SINGLE_VOTE


def linear_combination(row: Mapping[str, int], terms: Mapping[str, int], seats: int = SINGLE_VOTE,
                       scale_comparecimento: bool = False) -> int:
    total = 0
    for column, coefficient in terms.items():
        value = int(row[column])
        if scale_comparecimento and column == COMPARECIMENTO:
            value *= seats
        total += coefficient * value
    return total


def evaluate(identity: LinearIdentity, row: Mapping[str, int], cd_cargo: int) -> tuple[int, int]:
    seats = votes_per_voter(cd_cargo)
    expected = linear_combination(row, identity.lhs, seats, identity.scale_comparecimento_by_seats)
    observed = linear_combination(row, identity.rhs, seats, identity.scale_comparecimento_by_seats)
    return expected, observed


def residual(identity: LinearIdentity, row: Mapping[str, int], cd_cargo: int) -> int:
    expected, observed = evaluate(identity, row, cd_cargo)
    return observed - expected


def relative_delta(expected: float, observed: float) -> float | None:
    if expected == 0:
        return None
    return (observed - expected) / abs(expected)


def seats_sql_expression() -> str:
    return f"CASE WHEN CD_CARGO = {CD_CARGO_SENADOR} THEN {SENATE_SEATS_RENEWED_2026} ELSE {SINGLE_VOTE} END"


def linear_combination_sql(terms: Mapping[str, int], scale_comparecimento: bool = False) -> str:
    parts = []
    for column, coefficient in terms.items():
        expression = f"{column} * ({seats_sql_expression()})" if scale_comparecimento and column == COMPARECIMENTO else column
        parts.append(f"({coefficient}) * {expression}")
    return " + ".join(parts) if parts else "0"


def identity_sql(identity: LinearIdentity) -> tuple[str, str]:
    scale = identity.scale_comparecimento_by_seats
    return linear_combination_sql(identity.lhs, scale), linear_combination_sql(identity.rhs, scale)


def one(*columns: str) -> dict[str, int]:
    return {column: 1 for column in columns}


SECAO_IDENTITIES: tuple[LinearIdentity, ...] = (
    LinearIdentity(
        "BS01", "aptos = comparecimento + abstenções",
        one("QT_APTOS"), one("QT_COMPARECIMENTO", "QT_ABSTENCOES"), hypothesis_id="H01",
    ),
    LinearIdentity(
        "BS02", "comparecimento = nominais + legenda + brancos + nulos (um voto por eleitor)",
        one("QT_COMPARECIMENTO"), one("QT_VOTOS_NOMINAIS", "QT_VOTOS_LEGENDA", "QT_VOTOS_BRANCOS", "QT_VOTOS_NULOS"),
        exact=False, hypothesis_id="H02",
    ),
    LinearIdentity(
        "BS03", "comparecimento × votos_por_eleitor = nominais + legenda + brancos + nulos + anulados_apu_sep",
        one("QT_COMPARECIMENTO"),
        one("QT_VOTOS_NOMINAIS", "QT_VOTOS_LEGENDA", "QT_VOTOS_BRANCOS", "QT_VOTOS_NULOS", "QT_VOTOS_ANULADOS_APU_SEP"),
        scale_comparecimento_by_seats=True, hypothesis_id="H02",
    ),
)

MUNZONA_IDENTITIES: tuple[LinearIdentity, ...] = (
    LinearIdentity(
        "BM01", "aptos = comparecimento + abstenções",
        one("QT_APTOS"), one("QT_COMPARECIMENTO", "QT_ABSTENCOES"), exact=False, hypothesis_id="H03",
    ),
    LinearIdentity(
        "BM02", "aptos = comparecimento + abstenções + eleitores de seções não instaladas",
        one("QT_APTOS"), one("QT_COMPARECIMENTO", "QT_ABSTENCOES", "QT_ELEITORES_SECOES_NAO_INSTALADAS"),
        hypothesis_id="H03",
    ),
    LinearIdentity(
        "BM03", "comparecimento = válidos + brancos + total_nulos",
        one("QT_COMPARECIMENTO"), one("QT_TOTAL_VOTOS_VALIDOS", "QT_VOTOS_BRANCOS", "QT_TOTAL_VOTOS_NULOS"),
        exact=False, hypothesis_id="H03",
    ),
    LinearIdentity(
        "BM04", "comparecimento × votos_por_eleitor = QT_VOTOS",
        one("QT_COMPARECIMENTO"), one("QT_VOTOS"), scale_comparecimento_by_seats=True, hypothesis_id="H03",
    ),
    LinearIdentity(
        "BM05", "QT_VOTOS = válidos + brancos + total_nulos + anulados + anulados_subjud + anulados_apu_sep",
        one("QT_VOTOS"),
        one("QT_TOTAL_VOTOS_VALIDOS", "QT_VOTOS_BRANCOS", "QT_TOTAL_VOTOS_NULOS", "QT_TOTAL_VOTOS_ANULADOS",
            "QT_TOTAL_VOTOS_ANUL_SUBJUD", "QT_VOTOS_ANULADOS_APU_SEP"),
        hypothesis_id="H03",
    ),
    LinearIdentity(
        "BM06", "concorrentes = válidos + anulados + anulados_subjud",
        one("QT_VOTOS_CONCORRENTES"), one("QT_TOTAL_VOTOS_VALIDOS", "QT_TOTAL_VOTOS_ANULADOS", "QT_TOTAL_VOTOS_ANUL_SUBJUD"),
        hypothesis_id="H03",
    ),
    LinearIdentity(
        "BM07", "total_nulos = nulos + nulos_técnicos",
        one("QT_TOTAL_VOTOS_NULOS"), one("QT_VOTOS_NULOS", "QT_VOTOS_NULOS_TECNICOS"), hypothesis_id="H03",
    ),
    LinearIdentity(
        "BM08", "total_válidos = nominais_válidos + total_legenda_válidos",
        one("QT_TOTAL_VOTOS_VALIDOS"), one("QT_VOTOS_NOMINAIS_VALIDOS", "QT_TOTAL_VOTOS_LEG_VALIDOS"), hypothesis_id="H03",
    ),
    LinearIdentity(
        "BM09", "total_legenda_válidos = legenda_válidos + nominais_convertidos_em_legenda",
        one("QT_TOTAL_VOTOS_LEG_VALIDOS"), one("QT_VOTOS_LEG_VALIDOS", "QT_VOTOS_NOM_CONVR_LEG_VALIDOS"), hypothesis_id="H03",
    ),
    LinearIdentity(
        "BM10", "total_anulados = nominais_anulados + legenda_anulados",
        one("QT_TOTAL_VOTOS_ANULADOS"), one("QT_VOTOS_NOMINAIS_ANULADOS", "QT_VOTOS_LEGENDA_ANULADOS"), hypothesis_id="H03",
    ),
    LinearIdentity(
        "BM11", "total_anulados_subjud = nominais_subjud + legenda_subjud",
        one("QT_TOTAL_VOTOS_ANUL_SUBJUD"), one("QT_VOTOS_NOMINAIS_ANUL_SUBJUD", "QT_VOTOS_LEGENDA_ANUL_SUBJUD"),
        hypothesis_id="H03",
    ),
    LinearIdentity(
        "BM12", "total_seções = principais + agregadas + não_instaladas",
        one("QT_TOTAL_SECOES"), one("QT_SECOES_PRINCIPAIS", "QT_SECOES_AGREGADAS", "QT_SECOES_NAO_INSTALADAS"),
        exact=False, hypothesis_id="H03",
    ),
    LinearIdentity(
        "BM13", "total_seções = principais + agregadas (não instaladas já contadas em principais)",
        one("QT_TOTAL_SECOES"), one("QT_SECOES_PRINCIPAIS", "QT_SECOES_AGREGADAS"), hypothesis_id="H03",
    ),
)

PARTIDO_IDENTITIES: tuple[LinearIdentity, ...] = (
    LinearIdentity(
        "LP01", "total_legenda_válidos = legenda_válidos + nominais_convertidos_em_legenda (partido)",
        one("QT_TOTAL_VOTOS_LEG_VALIDOS"), one("QT_VOTOS_LEGENDA_VALIDOS", "QT_VOTOS_NOM_CONVR_LEG_VALIDOS"),
        hypothesis_id="H09",
    ),
)
